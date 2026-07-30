"""并发执行用例：多轮对话状态机 + 重试 + 留痕。

每个 TestCase 的 turns 是用户视角的输入序列（含可选的 system / assistant 预设）。
Runner 会顺序把每条 user turn 提交给 adapter，把 adapter 的回复 append 到对话历史，
形成完整的 ConversationTrace 供 judge 评估。

支持 N-runs 重复执行（参见 change harden-evaluation-determinism）：当 ``repeat=N>1``
时，每条 case 顺序跑 N 次（不同 ``#runI`` session_id），返回 ``list[list[ConversationTrace]]``
（外层 = case，内层 = 重复次数）。``repeat=1`` 时仍返回二维列表（内层长度 1）以保持类型一致。
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Sequence

from ..adapter.base import BaseAdapter, ChatRequest
from ..models import ChatMessage, ConversationTrace, TestCase
from ..observability import langfuse_tracing as lf
from ..observability.tracing import set_attribute, span
from ..retry import backoff_delay
from .user_simulator import SimulationState, UserSimulator

log = logging.getLogger(__name__)


def _extract_token_usage(raw: dict | None) -> dict[str, int]:
    """从 adapter 的 ``ChatResponse.raw`` 归一化抽取 token 用量（仅观测）。

    认 OpenAI 风格 usage 形状（``raw["usage"]`` 内的 prompt_tokens /
    completion_tokens / total_tokens，亦兼容 raw 顶层同名键）。认不出 / 缺失则返回
    ``{}``（占位，聚合时跳过），**绝不抛错**——观测降级而非中断评测。
    """
    if not isinstance(raw, dict):
        return {}
    usage = raw.get("usage")
    if not isinstance(usage, dict):
        # 兼容把 usage 键平铺在 raw 顶层的后端
        usage = raw if any(k in raw for k in ("prompt_tokens", "completion_tokens", "total_tokens")) else None
    if not isinstance(usage, dict):
        return {}

    def _int(key: str) -> int:
        val = usage.get(key)
        try:
            return int(val) if val is not None else 0
        except (TypeError, ValueError):
            return 0

    prompt = _int("prompt_tokens")
    completion = _int("completion_tokens")
    total = _int("total_tokens") or (prompt + completion)
    if prompt == 0 and completion == 0 and total == 0:
        return {}
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
    }


async def _run_one(
    case: TestCase,
    adapter: BaseAdapter,
    timeout_s: float,
    retry: int,
    session_suffix: str = "",
    backoff_base_s: float = 0.0,
    backoff_max_s: float = 40.0,
    run_idx: int = 0,
    run_name: str = "",
    user_simulator: UserSimulator | None = None,
) -> ConversationTrace:
    """跑一条用例的完整多轮对话。

    ``session_suffix``（如 ``"#run0"``）会拼接到 session_id 末尾，让 adapter 把
    N-runs 中不同次的同一条 case 视为独立会话而非续聊。
    """
    base_session = f"medeval-{case.sample_id}-{uuid.uuid4().hex[:8]}"
    session_id = f"{base_session}{session_suffix}"
    messages: list[dict[str, str]] = []
    chat_msgs: list[ChatMessage] = []
    raw_responses: list[dict] = []
    turn_latencies_ms: list[float] = []
    turn_token_usage: list[dict[str, int]] = []
    error: str | None = None
    cx_langfuse_trace_ids: list[str] = []
    cx_evaluation_share_url: str | None = None
    cx_literature_audits: list[dict] = []
    cx_literature_audit_error: str | None = None
    simulation_trace: list[dict] = []
    simulation_state: SimulationState | None = None
    if case.conversation is not None and user_simulator is None:
        # 未配置模型时，动态 Case 仍必须可通过规则与原 Benchmark 脚本运行。
        user_simulator = UserSimulator(enabled=False)
    # 原始 Case 上的用户档案 / Timeline 需要随评测结果固化：它们是 Agent
    # 的预置上下文，也是平台展示「用户档案和过往事实」及判断其是否注入的依据。
    # 使用 alias 保留 Case YAML 中的 ``Timeline`` 名称与自由 key，不展示
    # 仅供 cx-agent 使用的内部 long_term_memories 转换结果。
    case_initial_state = case.initial_state.model_dump(by_alias=True, exclude_none=True)
    evaluation_identity: dict = (
        {"initial_state": case_initial_state}
        if case_initial_state
        else {}
    )
    initial_state = case.initial_state.to_agent_payload()

    start = time.perf_counter()
    # bot 模型名（仅 openai_compat 等有 .model）；用于 Langfuse generation 标注。
    bot_model = getattr(adapter, "model", None)
    # 每条 case/run 是一条独立 Langfuse trace，按 session=run_name 分组（整段 run 可在
    # Langfuse Sessions 视图整体回放）；追踪关闭时为零开销 no-op。
    langfuse_trace_url: str | None = None
    with lf.conversation(
        f"case:{case.sample_id}",
        session_id=run_name or None,
        sample_id=case.sample_id,
        medeval_session=session_id,
        run_idx=run_idx,
    ) as conv:
        if conv is not None:
            # 进入 trace 后当场捕获其深链，落到 ConversationTrace 供平台用例明细跳转。
            langfuse_trace_url = lf.trace_url(lf.current_trace_id())
        # 动态 Case 的首轮来自 conversation.opening；普通 Case 保持已有 turns
        # 原样执行。队列让每次 Agent 回复后可以追加一条规则/脚本/模型用户消息。
        pending: list[tuple[object, dict[str, str]]] = []
        if case.conversation is not None:
            simulation_state = (
                await user_simulator.start(case)
                if user_simulator is not None
                else SimulationState()
            )
            pending.append((case.conversation.opening, {"source": "opening", "id": case.conversation.opening.id}))
        else:
            pending.extend((turn, {}) for turn in case.turns)

        user_turn_index = 0
        while pending:
            turn, simulation_event = pending.pop(0)
            chat_msgs.append(ChatMessage(role=turn.role, content=turn.content))
            if turn.role != "user":
                messages.append({"role": turn.role, "content": turn.content})
                continue

            user_turn_index += 1
            messages.append({"role": "user", "content": turn.content})
            if simulation_event:
                simulation_trace.append(
                    {
                        "turn": user_turn_index,
                        **simulation_event,
                        "content": turn.content,
                    }
                )
            metadata = {
                "eval_run_id": run_name,
                "sample_id": case.sample_id,
                "run_idx": run_idx,
            }
            if initial_state:
                metadata["initial_state"] = initial_state
            req = ChatRequest(
                messages=list(messages),
                session_id=session_id,
                metadata=metadata,
                images=turn.image_data_urls,
            )

            last_err: str | None = None
            turn_start = time.perf_counter()

            async def _maybe_backoff(attempt: int) -> None:
                # 仅在「还有下次尝试」且启用退避时等待；base<=0（默认）→ 立即重试（行为不变）。
                if attempt < retry and backoff_base_s > 0:
                    await asyncio.sleep(
                        backoff_delay(
                            attempt, base=backoff_base_s, factor=2.0, max_delay=backoff_max_s
                        )
                    )

            # tracing 默认 no-op、零开销；启用时每个 user turn 的 adapter 调用记一个
            # OTel span 与一个 Langfuse generation（input/output/model/usage/latency）。
            with span(
                "adapter.chat",
                sample_id=case.sample_id,
                turn_index=user_turn_index - 1,
                session_id=session_id,
            ) as sp, lf.generation(
                "adapter.chat",
                input=list(messages),
                model=bot_model,
                sample_id=case.sample_id,
                turn_index=user_turn_index - 1,
                session_id=session_id,
            ) as gen:
                for attempt in range(retry + 1):
                    try:
                        resp = await asyncio.wait_for(adapter.chat(req), timeout=timeout_s)
                    except asyncio.TimeoutError:
                        last_err = f"timeout after {timeout_s}s"
                        await _maybe_backoff(attempt)
                        continue
                    except Exception as e:
                        last_err = f"adapter exception: {e}"
                        await _maybe_backoff(attempt)
                        continue

                    if resp.error:
                        last_err = resp.error
                        await _maybe_backoff(attempt)
                        continue
                    messages.append({"role": "assistant", "content": resp.reply})
                    chat_msgs.append(ChatMessage(role="assistant", content=resp.reply))
                    raw_responses.append(resp.raw or {})
                    if isinstance(resp.raw, dict):
                        trace_id = resp.raw.get("cx_langfuse_trace_id")
                        if (
                            isinstance(trace_id, str)
                            and trace_id
                            and trace_id not in cx_langfuse_trace_ids
                        ):
                            cx_langfuse_trace_ids.append(trace_id)
                        account = resp.raw.get("evaluation_account")
                        context = resp.raw.get("evaluation_context")
                        if isinstance(account, dict):
                            for key, value in account.items():
                                evaluation_identity.setdefault(key, value)
                        if isinstance(context, dict):
                            profile = context.get("userProfile")
                            if isinstance(profile, dict):
                                evaluation_identity.setdefault("user_profile", profile)
                            cx_session = context.get("sessionId")
                            if isinstance(cx_session, str):
                                evaluation_identity["cx_session_id"] = cx_session
                        share_url = resp.raw.get("cx_evaluation_share_url")
                        if isinstance(share_url, str) and share_url:
                            # 多轮 Case 每轮都会冻结当时的完整会话，最后一轮即整段最终回放。
                            cx_evaluation_share_url = share_url
                    # token 用量：在裁剪 raw_responses 之前当场抽取，store_raw=on_error 也不丢
                    usage = _extract_token_usage(resp.raw)
                    turn_token_usage.append(usage)
                    # 该轮端到端耗时（含重试）：仅在成功取得回复时记录
                    turn_latency = (time.perf_counter() - turn_start) * 1000
                    turn_latencies_ms.append(turn_latency)
                    set_attribute(sp, "latency_ms", turn_latency)
                    set_attribute(sp, "attempts", attempt + 1)
                    lf.update_generation(
                        gen, output=resp.reply, usage=usage, latency_ms=turn_latency
                    )
                    last_err = None

                    # 完成一轮 Agent 回复后，由动态用户模拟器决定下一句。规则、
                    # 原 benchmark 脚本和模型补全均只会追加到当前 Case 的会话队列。
                    if (
                        case.conversation is not None
                        and simulation_state is not None
                        and user_turn_index < case.conversation.max_turns
                    ):
                        decision = (
                            await user_simulator.next_reply(
                                case,
                                simulation_state,
                                messages=list(messages),
                                agent_reply=resp.reply,
                            )
                            if user_simulator is not None
                            else None
                        )
                        if decision is not None:
                            simulation_state.trace.append(
                                {
                                    "turn": user_turn_index + 1,
                                    "source": decision.source,
                                    "id": decision.rule_id or decision.turn.id,
                                    "facts_added": decision.facts_added,
                                }
                            )
                            pending.append(
                                (
                                    decision.turn,
                                    {
                                        "source": decision.source,
                                        "id": decision.rule_id or decision.turn.id,
                                        "facts_added": decision.facts_added,
                                    },
                                )
                            )
                    break
                else:
                    set_attribute(sp, "error", last_err)
                    lf.update_generation(gen, error=last_err)
                    error = last_err
                    break

                if last_err is not None:
                    set_attribute(sp, "error", last_err)
                    lf.update_generation(gen, error=last_err)
                    error = last_err
                    break

    duration_ms = int((time.perf_counter() - start) * 1000)

    # 必须先拉审计、再释放隔离评测账号。账号下次领取会清空关联数据，而 Langfuse
    # 可能截断大型工具输出；这里的完整 Top-K snapshot 是 MME 长期审计的真相来源。
    fetch_literature_audits = getattr(adapter, "fetch_literature_audits", None)
    if callable(fetch_literature_audits):
        try:
            cx_literature_audits = await fetch_literature_audits(session_id)
        except Exception as exc:  # noqa: BLE001 - 观测增强失败不得覆盖评测结论
            cx_literature_audit_error = str(exc)

    await adapter.end_session(session_id)

    return ConversationTrace(
        messages=chat_msgs,
        raw_responses=raw_responses,
        duration_ms=duration_ms,
        turn_latencies_ms=turn_latencies_ms,
        turn_token_usage=turn_token_usage,
        error=error,
        langfuse_trace_url=langfuse_trace_url,
        langfuse_trace_ids=cx_langfuse_trace_ids,
        cx_evaluation_share_url=cx_evaluation_share_url,
        cx_literature_audits=cx_literature_audits,
        cx_literature_audit_error=cx_literature_audit_error,
        evaluation_identity=evaluation_identity,
        simulation_trace=simulation_trace,
        simulation_facts=simulation_state.facts if simulation_state is not None else {},
    )


async def run_cases(
    cases: Sequence[TestCase],
    adapter: BaseAdapter,
    concurrency: int = 4,
    timeout_s: float = 60,
    retry: int = 2,
    repeat: int = 1,
    on_progress=None,
    retry_backoff_base_s: float = 0.0,
    retry_backoff_max_s: float = 40.0,
    *,
    executor: str = "local",
    adapter_type: str = "",
    adapter_config: dict | None = None,
    ray_address: str = "",
    ray_num_workers: int = 0,
    resume_index: dict[tuple[str, int], ConversationTrace] | None = None,
    run_name: str = "",
    user_simulator: UserSimulator | None = None,
) -> list[list[ConversationTrace]]:
    """并发执行所有用例。

    返回 ``list[list[ConversationTrace]]``——外层顺序与 ``cases`` 一致、
    内层长度恒等于 ``repeat``。``on_progress(case, trace, run_index)`` 在每次
    (case, run) 完成后回调（兼容旧的 2 参数签名：缺省 ``run_index=0``）。

    ``executor='ray'`` 时改走分布式后端（worker 内按 ``adapter_type`` + ``adapter_config``
    自建 adapter，传入的 ``adapter`` 实例在 ray 路径下不参与对话）。其余参数语义不变。

    ``resume_index`` 给定时（断点续跑，仅 local 后端）：命中且无 error 的
    ``(sample_id, run_idx)`` 直接复用其留痕、**不调 adapter**，缺失/失败者照常执行。
    """
    if repeat < 1:
        raise ValueError(f"repeat must be a positive integer (got {repeat})")

    if executor == "ray":
        if any(case.conversation is not None for case in cases):
            raise RuntimeError("动态多轮 Case 暂仅支持 run.executor=local")
        if resume_index:
            raise RuntimeError(
                "断点续跑（resume）暂仅支持 run.executor=local；ray 后端逐 run 跳过需另行设计。"
            )
        from .ray_backend import run_cases_ray

        # ray.get 为阻塞调用：放进线程避免阻塞事件循环（run 阶段无其它协程并发）。
        return await asyncio.to_thread(
            run_cases_ray,
            cases,
            adapter_type,
            adapter_config or {},
            timeout_s=timeout_s,
            retry=retry,
            repeat=repeat,
            on_progress=on_progress,
            retry_backoff_base_s=retry_backoff_base_s,
            retry_backoff_max_s=retry_backoff_max_s,
            ray_address=ray_address,
            ray_num_workers=ray_num_workers,
        )

    sem = asyncio.Semaphore(concurrency)
    traces: list[list[ConversationTrace]] = [[] for _ in range(len(cases))]

    async def _wrap(i: int, case: TestCase):
        async with sem:
            for run_idx in range(repeat):
                # 断点续跑：命中已落盘的成功留痕则直接复用，不调 adapter。
                if resume_index is not None:
                    reused = resume_index.get((case.sample_id, run_idx))
                    if reused is not None and reused.error is None:
                        traces[i].append(reused)
                        if on_progress:
                            try:
                                on_progress(case, reused, run_idx)
                            except TypeError:
                                on_progress(case, reused)
                        continue
                suffix = f"#run{run_idx}" if repeat > 1 else ""
                try:
                    tr = await _run_one(
                        case,
                        adapter,
                        timeout_s,
                        retry,
                        suffix,
                        backoff_base_s=retry_backoff_base_s,
                        backoff_max_s=retry_backoff_max_s,
                        run_idx=run_idx,
                        run_name=run_name,
                        user_simulator=user_simulator,
                    )
                except Exception as e:
                    log.exception(
                        "Unhandled error in case %s (run %d)", case.sample_id, run_idx
                    )
                    tr = ConversationTrace(
                        messages=[], error=f"runner crashed: {e}"
                    )
                traces[i].append(tr)
                if on_progress:
                    try:
                        on_progress(case, tr, run_idx)
                    except TypeError:
                        # 兼容老的 2 参回调签名
                        on_progress(case, tr)

    await asyncio.gather(*(_wrap(i, c) for i, c in enumerate(cases)))
    return traces
