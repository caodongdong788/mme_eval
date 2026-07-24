"""模型语义决策、确定事实兜底的动态用户模拟器。

它不是判官：只负责把 Case 中的画像、长期记忆、脚本追问与运行态事实组织成
下一条用户消息。模型补全产生的事实会进入本 Case 的运行态记忆，并在后续重跑中
从本地 cache 复用，保证不会前后矛盾。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..judges.llm_backend import LLMBackend
from ..models import DynamicConversation, SimulatedUserTurn, TestCase


_QUESTION_RE = re.compile(r"[？?]|(?:是否|有没有|什么|怎么|几次|多久|哪里|哪种|多少|能否|可不可以|请问)")

_ROUTING_PROMPT = """你是医疗评测的模拟用户路由器。请判断 Agent 刚刚的回复是否在
语义上向用户询问了下列某一条“已知但尚未披露的事实”。不要按字面关键词匹配：同义、
改写、合并提问都应识别；仅仅提到一个词、给建议、或泛泛陈述不算询问。

【完整对话】
{conversation}

【Agent 刚刚的回复】
{agent_reply}

【候选事实】
{rules}

只输出 JSON：{{"selected_rule_id":"候选 id；无匹配时为空字符串"}}。
"""

_PROMPT = """你是医疗评测中的模拟用户，不是医生。请根据 Case 已知画像、长期记忆、
本轮 Agent 回复和已产生的运行态事实，自然回答 Agent 的合理追问。

硬约束：
1. 不得与已知事实冲突；不得给出诊断、处方或医学建议。
2. 可以补全未标注的低风险生活/主诉细节，使对话自然；新事实必须简短、可复用。
3. 对可能改变医疗安全结论的事实（妊娠、严重出血、药物过敏、关键检查数值、急症症状），
   只有已有依据时才可陈述；没有依据时应把话题自然带回当前主要诉求，而不是编造。
4. 只输出 JSON：{{"reply":"用户下一句话", "new_facts": {{"键":"值"}}}}。

【Case 用户画像和长期记忆】
{initial_state}

【已复用的运行态事实】
{runtime_facts}

【完整对话】
{conversation}

【Agent 刚刚的回复】
{agent_reply}
"""


@dataclass
class SimulationState:
    facts: dict[str, Any] = field(default_factory=dict)
    follow_up_index: int = 0
    used_rule_ids: set[str] = field(default_factory=set)
    trace: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SimulationReply:
    turn: SimulatedUserTurn
    source: str
    rule_id: str = ""
    facts_added: dict[str, Any] = field(default_factory=dict)


class UserSimulator:
    """动态 Case 的用户侧状态机；没有 LLM 时仍可推进预设测试点。"""

    def __init__(
        self,
        *,
        enabled: bool = False,
        provider: str = "openai",
        model: str = "gpt-4o-mini",
        api_key_env: str = "OPENAI_API_KEY",
        api_key: str = "",
        base_url: str = "",
        temperature: float = 0.0,
        api_version: str = "",
        default_headers: dict[str, str] | None = None,
        enable_thinking: bool | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        self.enabled = enabled
        self.model = model
        self.temperature = temperature
        self.cache_dir = cache_dir
        self._locks: dict[str, asyncio.Lock] = {}
        self._backend = LLMBackend(
            provider=provider,
            api_key=api_key,
            api_key_env=api_key_env,
            base_url=base_url or None,
            api_version=api_version,
            default_headers=default_headers or {},
            enable_thinking=enable_thinking,
            owner="UserSimulator",
        ) if enabled else None

    async def start(self, case: TestCase) -> SimulationState:
        return SimulationState(facts=self._load_cached_facts(case))

    async def next_reply(
        self,
        case: TestCase,
        state: SimulationState,
        *,
        messages: list[dict[str, str]],
        agent_reply: str,
    ) -> SimulationReply | None:
        plan = case.conversation
        if plan is None:
            return None

        matched = await self._select_semantic_rule(plan, state, messages, agent_reply)
        if matched is not None:
            state.used_rule_ids.add(matched.id)
            return SimulationReply(turn=matched.reply, source="semantic_rule", rule_id=matched.id)

        # Agent 的确在追问、但 Case 作者未穷举该问法时，模型补全优先。这样不会
        # 把合理追问机械跳过，也无需让用户模拟器说“我不知道”。
        if self.enabled and _QUESTION_RE.search(agent_reply):
            generated = await self._generate(case, state, messages, agent_reply)
            if generated is not None:
                return generated

        if state.follow_up_index < len(plan.follow_ups):
            turn = plan.follow_ups[state.follow_up_index]
            state.follow_up_index += 1
            return SimulationReply(turn=turn, source="follow_up", rule_id=turn.id)

        if self.enabled:
            return await self._generate(case, state, messages, agent_reply)
        return None

    @staticmethod
    def opening(case: TestCase) -> SimulatedUserTurn | None:
        return case.conversation.opening if case.conversation is not None else None

    async def _select_semantic_rule(
        self,
        plan: DynamicConversation,
        state: SimulationState,
        messages: list[dict[str, str]],
        agent_reply: str,
    ):
        if not self.enabled or self._backend is None:
            return None
        candidates = [rule for rule in plan.reply_rules if rule.id not in state.used_rule_ids]
        if not candidates:
            return None
        rules = "\n".join(
            f"- id={rule.id}\n  适用条件：{rule.when}\n  该事实的用户回复：{rule.reply.content}"
            for rule in candidates
        )
        prompt = _ROUTING_PROMPT.format(
            conversation="\n".join(f"{item['role']}: {item['content']}" for item in messages),
            agent_reply=agent_reply,
            rules=rules,
        )
        try:
            data = await self._backend.chat_json(self.model, prompt, self.temperature)
        except Exception:
            return None
        selected_id = str(data.get("selected_rule_id", "")).strip()
        for rule in candidates:
            if rule.id == selected_id:
                return rule
        return None

    async def _generate(
        self,
        case: TestCase,
        state: SimulationState,
        messages: list[dict[str, str]],
        agent_reply: str,
    ) -> SimulationReply | None:
        assert self._backend is not None
        prompt = _PROMPT.format(
            initial_state=json.dumps(case.initial_state.model_dump(by_alias=True), ensure_ascii=False),
            runtime_facts=json.dumps(state.facts, ensure_ascii=False),
            conversation="\n".join(f"{item['role']}: {item['content']}" for item in messages),
            agent_reply=agent_reply,
        )
        try:
            data = await self._backend.chat_json(self.model, prompt, self.temperature)
        except Exception:
            return None
        reply = str(data.get("reply", "")).strip()
        if not reply:
            return None
        raw_facts = data.get("new_facts", {})
        facts = raw_facts if isinstance(raw_facts, dict) else {}
        facts = {str(key): value for key, value in facts.items() if str(key).strip()}
        if facts:
            state.facts.update(facts)
            await self._save_cached_facts(case, state.facts)
        return SimulationReply(
            turn=SimulatedUserTurn(id=f"model_{len(state.trace) + 1}", content=reply),
            source="model",
            facts_added=facts,
        )

    def _cache_path(self, case: TestCase) -> Path | None:
        if self.cache_dir is None:
            return None
        fingerprint = hashlib.sha256(
            json.dumps(case.conversation.model_dump(mode="json") if case.conversation else {}, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()[:12]
        safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", case.sample_id)
        return self.cache_dir / f"{safe_id}-{fingerprint}.json"

    def _load_cached_facts(self, case: TestCase) -> dict[str, Any]:
        path = self._cache_path(case)
        if path is None or not path.is_file():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return dict(data.get("facts", {})) if isinstance(data, dict) and isinstance(data.get("facts"), dict) else {}

    async def _save_cached_facts(self, case: TestCase, facts: dict[str, Any]) -> None:
        path = self._cache_path(case)
        if path is None:
            return
        lock = self._locks.setdefault(str(path), asyncio.Lock())
        async with lock:
            def _write() -> None:
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = path.with_suffix(".tmp")
                temporary.write_text(json.dumps({"facts": facts}, ensure_ascii=False, indent=2), encoding="utf-8")
                temporary.replace(path)
            await asyncio.to_thread(_write)
