"""平台运行期配置（环境变量可覆盖）。

单一真值源：路径、数据库连接串、并发上限。测试可通过环境变量或直接构造 ``Settings`` 覆盖。
"""

from __future__ import annotations

import os
import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

# 项目根：server/ 的上一级（含 config.yaml / cases / outputs）。
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 内置默认会话密钥（生产环境禁止沿用，单一信任源）。
DEFAULT_SESSION_SECRET = "dev-insecure-secret"
EXAMPLE_OPEN_API_ENCRYPTION_SECRET = "please-change-me-to-another-long-random-secret"


def _load_dotenv(path: Path) -> None:
    """零依赖加载 .env：仅对「尚未在环境中存在」的键生效（真实环境变量优先）。

    解析 KEY=VALUE，忽略空行/注释，去除值两端引号；值中允许空格（如 scope 列表）。
    """
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


# 启动时加载项目根的 .env（若存在）。测试用 monkeypatch 覆盖优先于此。
_load_dotenv(PROJECT_ROOT / ".env")


def _env_path(var: str, default: Path) -> Path:
    return Path(os.environ.get(var, str(default)))


@dataclass(frozen=True)
class Settings:
    # 用 default_factory 在实例化时读环境变量（测试可经 monkeypatch + cache_clear 覆盖）。
    project_root: Path = field(default_factory=lambda: PROJECT_ROOT)
    # 数据库：默认本地 SQLite，可经 MEDEVAL_DATABASE_URL 切 Postgres。
    database_url: str = field(
        default_factory=lambda: os.environ.get(
            "MEDEVAL_DATABASE_URL", f"sqlite:///{PROJECT_ROOT / 'medeval_platform.db'}"
        )
    )
    # 被测 bot 的基础 config.yaml（adapter 与八维/指南 judges 口径来源）。
    config_path: Path = field(
        default_factory=lambda: _env_path("MEDEVAL_CONFIG_PATH", PROJECT_ROOT / "config.yaml")
    )
    # 上传 benchmark 用例存储根目录。
    uploads_dir: Path = field(
        default_factory=lambda: _env_path(
            "MEDEVAL_UPLOADS_DIR", PROJECT_ROOT / "uploads" / "benchmarks"
        )
    )
    # 评测产物目录（与 CLI 共用）。
    outputs_dir: Path = field(
        default_factory=lambda: _env_path("MEDEVAL_OUTPUTS_DIR", PROJECT_ROOT / "outputs")
    )
    # 内置 benchmark 路径（相对 project_root）。
    builtin_cases_dir: str = "cases/benchmark"
    # 同时并发执行的评测任务上限。
    max_concurrent_jobs: int = field(
        default_factory=lambda: int(os.environ.get("MEDEVAL_MAX_CONCURRENT_JOBS", "3"))
    )
    # in_process：开发/测试兼容模式；database：API 只入队，由独立 Worker 执行。
    job_runner_mode: str = field(
        default_factory=lambda: os.environ.get("MEDEVAL_JOB_RUNNER", "in_process").strip().lower()
    )
    job_poll_seconds: float = field(
        default_factory=lambda: float(os.environ.get("MEDEVAL_JOB_POLL_SECONDS", "2"))
    )
    job_lease_seconds: int = field(
        default_factory=lambda: int(os.environ.get("MEDEVAL_JOB_LEASE_SECONDS", "90"))
    )
    job_heartbeat_seconds: int = field(
        default_factory=lambda: int(os.environ.get("MEDEVAL_JOB_HEARTBEAT_SECONDS", "10"))
    )
    # Web 多实例/蓝绿发布时可只让一个实例运行周期调度器。数据库 occurrence
    # 唯一约束仍作为最终幂等兜底。
    scheduler_enabled: bool = field(
        default_factory=lambda: os.environ.get(
            "MEDEVAL_SCHEDULER_ENABLED", "true"
        ).strip().lower() in {"1", "true", "yes", "on"}
    )
    worker_ready_file: Path = field(
        default_factory=lambda: _env_path(
            "MEDEVAL_WORKER_READY_FILE", Path("/tmp/mme-worker-ready")
        )
    )
    # --- 飞书 OAuth2 / 会话（per-user SSO 登录） ---
    # 自建应用凭证；未配置 app_id 时整套登录门禁关闭（dev 兜底，避免本地自锁）。
    feishu_app_id: str = field(
        default_factory=lambda: os.environ.get("FEISHU_APP_ID", "")
    )
    feishu_app_secret: str = field(
        default_factory=lambda: os.environ.get("FEISHU_APP_SECRET", "")
    )
    # 回调地址：开发态用前端同源（vite 代理 /api → 后端），保证 cookie 同源。
    feishu_redirect_uri: str = field(
        default_factory=lambda: os.environ.get(
            "FEISHU_REDIRECT_URI",
            "http://localhost:5173/api/auth/feishu/callback",
        )
    )
    # 申请的 scope；offline_access 是拿 refresh_token（免重复授权）的前提。
    feishu_scopes: str = field(
        default_factory=lambda: os.environ.get(
            "FEISHU_SCOPES",
            "offline_access contact:user.base:readonly drive:drive "
            "base:app:read base:table:read base:view:read base:record:read "
            "sheets:spreadsheet:read",
        )
    )
    # 仅这些飞书 open_id 可管理平台级密钥和敏感评测账号；逗号分隔。
    admin_open_ids_raw: str = field(
        default_factory=lambda: os.environ.get("MEDEVAL_ADMIN_OPEN_IDS", "")
    )
    # SIT 评测账号验证码必须由部署环境注入，格式为 {"+86...":"123456"}。
    evaluation_account_codes_json: str = field(
        default_factory=lambda: os.environ.get(
            "MEDEVAL_EVALUATION_ACCOUNT_CODES_JSON", "{}"
        )
    )
    # 登录成功后回跳的前端地址。
    frontend_url: str = field(
        default_factory=lambda: os.environ.get("FRONTEND_URL", "http://localhost:5173")
    )
    # 会话 cookie 签名密钥（生产必须配置）。
    session_secret: str = field(
        default_factory=lambda: os.environ.get("SESSION_SECRET", DEFAULT_SESSION_SECRET)
    )
    # OpenAPI Key 的可恢复密文主密钥。默认复用 SESSION_SECRET；生产建议单独注入
    # 一个长期稳定值，避免会话密钥轮换影响管理员查看既有 Key。
    open_api_encryption_secret: str = field(
        default_factory=lambda: (
            os.environ.get("MEDEVAL_OPEN_API_ENCRYPTION_SECRET", "").strip()
            or os.environ.get("SESSION_SECRET", DEFAULT_SESSION_SECRET)
        )
    )
    # 会话有效期（秒），默认 7 天。
    session_ttl_seconds: int = field(
        default_factory=lambda: int(os.environ.get("SESSION_TTL_SECONDS", str(7 * 24 * 3600)))
    )
    # 运行环境标识：development（默认）/ test / production。控制生产强校验与 cookie Secure。
    env: str = field(
        default_factory=lambda: os.environ.get("MEDEVAL_ENV", "development")
    )
    # 上传 benchmark 包大小上限（字节），默认 50 MiB；ZIP 内图片另有解压/单张限制。
    max_upload_bytes: int = field(
        default_factory=lambda: int(
            os.environ.get("MEDEVAL_MAX_UPLOAD_BYTES", str(50 * 1024 * 1024))
        )
    )
    # cx-agent 内部 Langfuse Trace 只读同步。与 MME 自身是否写 Langfuse 解耦；
    # 凭据仅在服务端环境变量中使用，不进入 Case 明细或配置快照。
    langfuse_host: str = field(
        default_factory=lambda: os.environ.get("LANGFUSE_HOST", "")
        or os.environ.get("LANGFUSE_BASE_URL", "")
    )
    langfuse_public_key: str = field(
        default_factory=lambda: os.environ.get("LANGFUSE_PUBLIC_KEY", "")
    )
    langfuse_secret_key: str = field(
        default_factory=lambda: os.environ.get("LANGFUSE_SECRET_KEY", "")
    )
    langfuse_sync_timeout_seconds: float = field(
        default_factory=lambda: float(os.environ.get("LANGFUSE_SYNC_TIMEOUT_SECONDS", "8"))
    )
    langfuse_sync_attempts: int = field(
        # cx-agent 的 Langfuse observation 可能在请求完成后延迟写入；默认给
        # 15 秒的指数退避窗口，而不是首次读空就把链路标为失败。
        default_factory=lambda: int(os.environ.get("LANGFUSE_SYNC_ATTEMPTS", "5"))
    )
    langfuse_sync_initial_backoff_seconds: float = field(
        default_factory=lambda: float(
            os.environ.get("LANGFUSE_SYNC_INITIAL_BACKOFF_SECONDS", "1")
        )
    )
    # 评测刚结束时，cx-agent 的 Langfuse trace 仍可能处于异步入库阶段。首次同步
    # 保持在主任务内完成；仅对未同步的用例，在任务成功后再后台补拉一次，避免列表
    # 长期显示“链路未同步”。
    langfuse_post_run_sync_delay_seconds: float = field(
        default_factory=lambda: float(
            os.environ.get("LANGFUSE_POST_RUN_SYNC_DELAY_SECONDS", "20")
        )
    )
    langfuse_post_run_sync_attempts: int = field(
        default_factory=lambda: int(
            os.environ.get("LANGFUSE_POST_RUN_SYNC_ATTEMPTS", "2")
        )
    )
    # DeepTrace 当前上线版本：仅定时评测在创建 run 名称时读取。Token 只允许通过
    # 运行环境注入，绝不落库、回传前端或进入评测配置快照。
    deeptrace_base_url: str = field(
        default_factory=lambda: os.environ.get(
            # DeepTrace 生产当前只开放 HTTP；必须保留域名访问以命中正确 Nginx Host。
            # 不可替换为解析出的内网 IP，否则会落到默认站点返回 404。
            "DEEPTRACE_BASE_URL", "http://deeptrace.senzco.com"
        ).rstrip("/")
    )
    deeptrace_space_key: str = field(
        default_factory=lambda: os.environ.get("DEEPTRACE_SPACE_KEY", "cx")
    )
    deeptrace_open_api_token: str = field(
        default_factory=lambda: os.environ.get("DEEPTRACE_OPEN_API_TOKEN", "")
    )
    deeptrace_timeout_seconds: float = field(
        default_factory=lambda: float(os.environ.get("DEEPTRACE_TIMEOUT_SECONDS", "8"))
    )

    @property
    def auth_required(self) -> bool:
        """是否强制登录：仅当配置了飞书应用密钥时开启（否则 dev 放行）。"""
        return bool(self.feishu_app_id and self.feishu_app_secret)

    @property
    def admin_open_ids(self) -> frozenset[str]:
        return frozenset(
            value.strip()
            for value in self.admin_open_ids_raw.split(",")
            if value.strip()
        )

    @property
    def evaluation_account_codes(self) -> dict[str, str]:
        try:
            value = json.loads(self.evaluation_account_codes_json or "{}")
        except ValueError:
            return {}
        if not isinstance(value, dict):
            return {}
        return {
            str(phone): str(code)
            for phone, code in value.items()
            if str(phone).strip() and str(code).strip()
        }

    @property
    def is_production(self) -> bool:
        return self.env.strip().lower() in ("production", "prod")

    def check_production_security(self) -> None:
        """生产环境安全前置校验：必须启用登录并使用非默认会话密钥。

        开发/测试环境仍可不配置飞书登录，保持本地直接访问行为不变；生产环境
        缺少任意飞书应用凭证时必须拒绝启动，避免认证中间件静默降级为全站放行。
        """
        if not self.is_production:
            return
        if not self.feishu_app_id or not self.feishu_app_secret:
            raise RuntimeError(
                "生产环境必须同时配置 FEISHU_APP_ID 和 FEISHU_APP_SECRET，禁止关闭登录校验。"
            )
        if self.session_secret == DEFAULT_SESSION_SECRET:
            raise RuntimeError(
                "生产环境禁止使用默认 SESSION_SECRET，请配置一个高强度随机密钥后再启动。"
            )
        if self.open_api_encryption_secret in {
            DEFAULT_SESSION_SECRET,
            EXAMPLE_OPEN_API_ENCRYPTION_SECRET,
        }:
            raise RuntimeError(
                "生产环境必须配置真实的 MEDEVAL_OPEN_API_ENCRYPTION_SECRET，"
                "禁止使用示例值。"
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
