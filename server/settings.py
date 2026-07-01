"""平台运行期配置（环境变量可覆盖）。

单一真值源：路径、数据库连接串、并发上限。测试可通过环境变量或直接构造 ``Settings`` 覆盖。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

# 项目根：server/ 的上一级（含 config.yaml / cases / outputs）。
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 内置默认会话密钥（生产环境禁止沿用，单一信任源）。
DEFAULT_SESSION_SECRET = "dev-insecure-secret"


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
    # 被测 bot 的基础 config.yaml（adapter/judges/scoring 等口径来源）。
    config_path: Path = field(
        default_factory=lambda: _env_path("MEDEVAL_CONFIG_PATH", PROJECT_ROOT / "config.yaml")
    )
    # 上传 benchmark 用例存储根目录。
    uploads_dir: Path = field(
        default_factory=lambda: _env_path(
            "MEDEVAL_UPLOADS_DIR", PROJECT_ROOT / "uploads" / "benchmarks"
        )
    )
    # 评测产物目录（与 CLI 共用，双写兼容）。
    outputs_dir: Path = field(
        default_factory=lambda: _env_path("MEDEVAL_OUTPUTS_DIR", PROJECT_ROOT / "outputs")
    )
    # 内置 benchmark 路径（相对 project_root）。
    builtin_cases_dir: str = "cases/breast_cancer"
    # 同时并发执行的评测任务上限。
    max_concurrent_jobs: int = field(
        default_factory=lambda: int(os.environ.get("MEDEVAL_MAX_CONCURRENT_JOBS", "2"))
    )
    # 单个线上评测批次内，case 级 LLM judge 并发数。
    online_eval_case_concurrency: int = field(
        default_factory=lambda: int(os.environ.get("MEDEVAL_ONLINE_EVAL_CASE_CONCURRENCY", "4"))
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
    # 登录成功后回跳的前端地址。
    frontend_url: str = field(
        default_factory=lambda: os.environ.get("FRONTEND_URL", "http://localhost:5173")
    )
    # 会话 cookie 签名密钥（生产必须配置）。
    session_secret: str = field(
        default_factory=lambda: os.environ.get("SESSION_SECRET", DEFAULT_SESSION_SECRET)
    )
    # 会话有效期（秒），默认 7 天。
    session_ttl_seconds: int = field(
        default_factory=lambda: int(os.environ.get("SESSION_TTL_SECONDS", str(7 * 24 * 3600)))
    )
    # 运行环境标识：development（默认）/ test / production。控制生产强校验与 cookie Secure。
    env: str = field(
        default_factory=lambda: os.environ.get("MEDEVAL_ENV", "development")
    )
    # 上传 benchmark 单文件大小上限（字节），默认 5 MiB。
    max_upload_bytes: int = field(
        default_factory=lambda: int(
            os.environ.get("MEDEVAL_MAX_UPLOAD_BYTES", str(5 * 1024 * 1024))
        )
    )

    @property
    def auth_required(self) -> bool:
        """是否强制登录：仅当配置了飞书应用密钥时开启（否则 dev 放行）。"""
        return bool(self.feishu_app_id and self.feishu_app_secret)

    @property
    def is_production(self) -> bool:
        return self.env.strip().lower() in ("production", "prod")

    def check_production_security(self) -> None:
        """生产环境安全前置校验：默认会话密钥禁止上线。

        仅在生产环境且 ``session_secret`` 仍为内置默认值时抛出，阻止以不安全密钥启动；
        开发/测试环境（默认）始终通过，保持现有本地启动行为不变。
        """
        if self.is_production and self.session_secret == DEFAULT_SESSION_SECRET:
            raise RuntimeError(
                "生产环境禁止使用默认 SESSION_SECRET，请配置一个高强度随机密钥后再启动。"
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
