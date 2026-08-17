"""medeval 配置 schema —— 整棵 config.yaml 的类型化单一真值源。

参见 OpenSpec change ``2026-06-02-typed-config-validation``。

要点：
  * 结构化节点统一 ``extra="forbid"``，旧四模块和 score profile 配置会直接报错。
  * 跨字段校验 adapter.type 子块及 Azure LLM 必填连接信息。
  * ``load_config`` 把 ``ValidationError`` 渲染成定位到键路径的友好报错（``ConfigError``）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class _Strict(BaseModel):
    """结构化节点基类：禁止未声明字段（抓拼错）。"""

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# run / cases


class StatsCfg(_Strict):
    """报告层 bootstrap 置信区间配置（参见 change enhance-eval-engine）。

    纯度量：仅影响报告呈现，绝不参与判分/否决。``enabled`` 默认开启但零行为风险；
    给定 ``seed`` 保证 report.json 可复现、可 diff。
    """

    enabled: bool = True
    bootstrap_resamples: int = Field(1000, ge=0)
    confidence: float = Field(0.95, gt=0.0, lt=1.0)
    seed: int = 0


class RetentionCfg(_Strict):
    """胖产物滚动清理策略（参见 change persist-traces-rejudge）。

    只清理胖产物（traces.jsonl.gz / transcripts.xlsx / 残留 partial），
    report.json 永久保留以保证跨版本 diff 不断链。
    """

    enabled: bool = True
    keep_last: int = Field(20, ge=0)  # 保留最近 N 个 run 的胖产物；0 = 全留
    ttl_days: int | None = None  # 超期（按 report.json mtime）的 run 清胖产物；None = 不按时限
    keep_tagged: bool = True  # 含 KEEP sentinel 文件的 run 目录永久豁免


class RunCfg(_Strict):
    name: str = "eval-run"
    description: str = ""
    output_dir: str = "outputs"
    concurrency: int = 4
    # LLM 判官并发（与 bot 分离）。
    judge_concurrency: int = Field(2, ge=1)
    # 判官 API 两次调用之间的最小间隔（秒），缓和 QPM；0 = 仅受 judge_concurrency 约束。
    llm_min_interval_s: float = Field(0.5, ge=0.0)
    # 单次 cx-agent 请求的超时与重试策略。即使 Case 有总预算，单请求仍沿用
    # 既有的失败重试机制，避免瞬时网络/上游故障直接导致整题失败。
    timeout_s: float = 90.0
    retry: int = 2
    # 一次完整 Case 尝试（对话 + LLM 判分）的总预算。首次仅在判分失败时才会
    # 整题重跑一次，因此单题累计最多为 2 * case_timeout_s。
    case_timeout_s: float = Field(600.0, gt=0.0)
    repeat: int = Field(1, ge=1)
    # single_turn：沿用 main 的固定 turns 执行；multi_turn：启用 conversation
    # 与动态用户模拟器。页面发起 Run 时可覆盖，且随 config_snapshot 固化。
    evaluation_mode: Literal["single_turn", "multi_turn"] = "single_turn"
    # 重试间指数退避：base<=0（默认）= 关闭，保持立即重试行为；>0 时按 backoff_delay 等待。
    retry_backoff_base_s: float = 0.0
    retry_backoff_max_s: float = 40.0
    # 报告层统计（bootstrap 置信区间），默认开启、纯度量。
    stats: StatsCfg = Field(default_factory=StatsCfg)
    # 执行后端（参见 change enhance-eval-engine）：local（默认，单进程 asyncio 并发）
    # 或 ray（分布式，需安装可选依赖 medeval[ray]）。两后端产物结构一致。
    executor: Literal["local", "ray"] = "local"
    ray_address: str = ""  # 连接已有 ray 集群；留空 = 本地起一个
    ray_num_workers: int = Field(0, ge=0)  # 0 = 由 ray 自行决定 CPU 数
    # 会话留痕落盘（参见 change persist-traces-rejudge）：默认开启，支持离线重判 / 断点续跑。
    persist_traces: bool = True
    # raw_responses 瘦身：never=永不存 / on_error=仅报错轮次留全量（默认）/ always=全留。
    # 离线重判只读 messages 文本，故 on_error 对重判无损、显著省盘。
    store_raw: Literal["never", "on_error", "always"] = "on_error"
    # 胖产物滚动清理策略（run 收尾自动触发、亦可 `medeval prune` 手动触发）。
    retention: RetentionCfg = Field(default_factory=RetentionCfg)


class CasesCfg(_Strict):
    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# adapter（字段集严格对齐 adapter 构造函数，保证 Adapter(**model_dump) 不多不缺）


class OpenAICompatCfg(_Strict):
    base_url: str = ""
    model: str = "gpt-4o-mini"
    api_key_env: str = "OPENAI_API_KEY"
    api_key: str = ""
    temperature: float = 0.0
    max_tokens: int = 1024
    system_prompt: str = ""
    extra_body: dict[str, Any] = Field(default_factory=dict)  # 自由叶子
    timeout_s: float = 60.0


class HttpCfg(_Strict):
    base_url: str = ""
    endpoint: str = "/chat"
    method: str = "POST"
    headers: dict[str, str] = Field(default_factory=dict)  # 自由叶子
    body_template: str = '{"messages": {{messages}}, "session_id": "{{session_id}}"}'
    response_path: str = "reply"
    timeout_s: float = 60.0


class CxAgentCfg(_Strict):
    base_url: str = "http://localhost:3000"
    test_token_env: str = "CX_AGENT_TEST_TOKEN"
    test_token: str = ""
    timeout_s: float = 120.0
    isolated_accounts: bool = False
    # 隔离评测账号池容量。账号由 cx-agent 租约服务实际分配；MME 在本进程内预先限流，
    # 避免多个评测任务同时抢空账号池。
    stateless_account_capacity: int = Field(default=8, ge=1)
    stateful_account_capacity: int = Field(default=8, ge=1)
    # 单个评测任务在同一账号池最多同时占用的账号数，避免大任务独占整个池。
    per_run_account_limit: int = Field(default=2, ge=1)
    # 仅影响 cx-agent 测试接口是否向模型暴露医学文献 RAG 工具；不影响画像、长期记忆或聊天历史。
    enable_rag: bool = False


class AdapterCfg(_Strict):
    # type 不写死 Literal：已支持类型由 adapter 注册表单一提供（开闭扩展，单一真值源）。
    type: str
    openai_compat: OpenAICompatCfg | None = None
    http: HttpCfg | None = None
    cx_agent: CxAgentCfg | None = None

    @model_validator(mode="after")
    def _check_subblock(self):
        # 惰性导入：触发 medeval.adapter 包加载 → 各 adapter 类 @register_adapter 完成注册。
        from .adapter import config_key_for, supported_adapter_types

        supported = supported_adapter_types()
        if self.type not in supported:
            raise ValueError(
                f"adapter.type={self.type!r} 不被支持。可选：{', '.join(supported)}"
            )
        key = config_key_for(self.type)  # 'http' | 'openai_compat'
        if key and getattr(self, key, None) is None:
            raise ValueError(f"adapter.type={self.type!r} 但缺少 adapter.{key} 子块")
        return self


# ---------------------------------------------------------------------------
# judges


class _LLMClientCfg(_Strict):
    """三个走 LLM 的判官共享的调用配置基类。"""

    enabled: bool = False
    provider: Literal["openai", "azure"] = "openai"
    model: str = "gpt-4o-mini"
    api_key_env: str = "OPENAI_API_KEY"
    api_key: str = ""
    base_url: str = ""
    api_version: str = ""
    default_headers: dict[str, str] = Field(default_factory=dict)  # 自由叶子
    temperature: float = 0.0
    enable_thinking: bool | None = None

    @model_validator(mode="after")
    def _check_azure(self):
        # 仅在启用时强校验（与"client 只在 enabled 时构建"的运行期行为一致）。
        if self.enabled and self.provider == "azure":
            if not self.base_url:
                raise ValueError("provider='azure' 时必须配置 base_url（azure_endpoint）")
            if not self.api_version:
                raise ValueError("provider='azure' 时必须配置 api_version（如 '2024-02-01'）")
        return self


class EightDimensionCfg(_LLMClientCfg):
    pass


class GuidelineCfg(_LLMClientCfg):
    pass


class JudgesCfg(_Strict):
    eight_dimension: EightDimensionCfg = Field(default_factory=EightDimensionCfg)
    guideline: GuidelineCfg = Field(default_factory=GuidelineCfg)


class UserSimulatorCfg(_LLMClientCfg):
    """动态多轮 Case 的用户模拟模型。

    规则和原 Benchmark 脚本不依赖该模型；只有 Agent 的合理追问未被 Case
    显式覆盖时才调用。生成的运行态事实默认缓存在 output_dir 下，供后续重跑复用。
    """

    cache_subdir: str = ".simulation_cache"


# ---------------------------------------------------------------------------
# reporter / thresholds


class LarkCfg(_Strict):
    enabled: bool = False
    parent_folder_token: str = ""
    include_failed_samples: bool = True


class ReporterCfg(_Strict):
    formats: list[str] = Field(default_factory=lambda: ["markdown"])
    diff_against: str = ""
    lark: LarkCfg = Field(default_factory=LarkCfg)


class ThresholdsCfg(_Strict):
    medical_safety_pass_rate: float | None = None
    overall_pass_rate: float | None = None


# ---------------------------------------------------------------------------
# 顶层


class OtelCfg(_Strict):
    """OpenTelemetry tracing 配置（参见 change enhance-eval-engine）。默认关闭、no-op 兜底。"""

    enabled: bool = False
    endpoint: str = ""
    service_name: str = "medeval"


class LangfuseCfg(_Strict):
    """被测 bot 全链路 Langfuse 追踪配置（参见 change add-langfuse-bot-tracing）。

    默认关闭、软依赖、no-op 兜底。凭据仅从环境变量读取（``public_key_env`` /
    ``secret_key_env``），绝不落 config 快照或留痕。仅追踪被测 bot，judge 调用不纳入。
    """

    enabled: bool = False
    host: str = ""
    public_key_env: str = "LANGFUSE_PUBLIC_KEY"
    secret_key_env: str = "LANGFUSE_SECRET_KEY"
    sample_rate: float = 1.0
    debug: bool = False


class ObservabilityCfg(_Strict):
    otel: OtelCfg = Field(default_factory=OtelCfg)
    langfuse: LangfuseCfg = Field(default_factory=LangfuseCfg)


class CostConfig(_Strict):
    """成本/Token 观测的单价配置（参见 change add-token-cost-observability）。

    纯观测：单价随 config_snapshot 落盘，让报告 diff 能区分"用量变化"vs"单价调整"。
    ``input_per_million`` / ``output_per_million`` 均为 0（默认）= 未配置单价，
    此时只统计 token、cost 显示 N/A，绝不参与任何评分/否决。
    """

    currency: str = "USD"
    input_per_million: float = Field(0.0, ge=0.0)   # 每百万 prompt token 单价
    output_per_million: float = Field(0.0, ge=0.0)  # 每百万 completion token 单价


class Config(_Strict):
    run: RunCfg = Field(default_factory=RunCfg)
    cases: CasesCfg = Field(default_factory=CasesCfg)
    adapter: AdapterCfg  # 必填：adapter.type 必须显式声明
    judges: JudgesCfg = Field(default_factory=JudgesCfg)
    user_simulator: UserSimulatorCfg = Field(default_factory=UserSimulatorCfg)
    reporter: ReporterCfg = Field(default_factory=ReporterCfg)
    thresholds: ThresholdsCfg = Field(default_factory=ThresholdsCfg)
    observability: ObservabilityCfg = Field(default_factory=ObservabilityCfg)
    cost: CostConfig = Field(default_factory=CostConfig)

    def public_snapshot(self) -> dict[str, Any]:
        """可持久化、可通过 API 返回的配置快照，递归移除明文凭据。"""
        return redact_config_secrets(self.model_dump(mode="json"))


_SECRET_CONFIG_KEYS = frozenset({"api_key", "test_token"})


def redact_config_secrets(value: Any) -> Any:
    """递归删除配置中的明文密钥；保留对应的 ``*_env`` 名称以便复现。"""
    if isinstance(value, dict):
        return {
            key: redact_config_secrets(item)
            for key, item in value.items()
            if key not in _SECRET_CONFIG_KEYS
        }
    if isinstance(value, list):
        return [redact_config_secrets(item) for item in value]
    return value


class ConfigError(Exception):
    """配置加载/校验失败（已渲染成对用户友好的多行报错）。"""


def _format_validation_error(path: Path, e: ValidationError) -> str:
    lines = [f"配置校验失败（{path}）："]
    for err in e.errors():
        loc = ".".join(str(x) for x in err.get("loc", ())) or "(root)"
        lines.append(f"  - {loc}: {err.get('msg', '')}")
    return "\n".join(lines)


def parse_config(raw: dict[str, Any], source: str | Path = "<dict>") -> Config:
    """校验一个已加载的配置 dict，失败抛 ConfigError（含键路径）。"""
    try:
        return Config.model_validate(raw or {})
    except ValidationError as e:
        raise ConfigError(_format_validation_error(Path(str(source)), e)) from e


def load_config(path: Path) -> Config:
    """读取并校验 config.yaml；非法配置抛 ConfigError（友好键路径报错）。"""
    with Path(path).open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    if not isinstance(raw, dict):
        raise ConfigError(f"配置根节点必须是映射（mapping），实际为 {type(raw).__name__}：{path}")
    return parse_config(raw, source=path)
