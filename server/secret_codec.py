"""服务端可恢复密钥的带认证加解密。

OpenAPI 调用鉴权始终使用独立 SHA-256 摘要；本模块只服务管理员后续查看完整
Key 的产品需求。密文以版本前缀标识，便于未来平滑轮换算法或密钥。
"""

from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from .settings import get_settings


_FERNET_PREFIX = "fernet:v1:"


@lru_cache(maxsize=4)
def _fernet(secret: str) -> Fernet:
    derived = hashlib.sha256(f"mme-open-api-key:{secret}".encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_recoverable_secret(value: str) -> str:
    """把明文转换为不可直接读取且可校验完整性的版本化密文。"""
    if not value:
        return ""
    secret = get_settings().open_api_encryption_secret
    token = _fernet(secret).encrypt(value.encode("utf-8")).decode("ascii")
    return f"{_FERNET_PREFIX}{token}"


def decrypt_recoverable_secret(value: str) -> str:
    """解密当前密文；无前缀值按升级前的历史明文兼容读取。"""
    if not value:
        return ""
    if not value.startswith(_FERNET_PREFIX):
        return value
    token = value.removeprefix(_FERNET_PREFIX)
    try:
        return _fernet(get_settings().open_api_encryption_secret).decrypt(
            token.encode("ascii")
        ).decode("utf-8")
    except (InvalidToken, UnicodeError, ValueError):
        # SESSION_SECRET / 专用加密密钥被错误更换时，鉴权摘要仍然有效，但管理员
        # 不能再读取原文。返回空值让页面明确提示轮换，绝不返回损坏或伪造内容。
        return ""


def is_encrypted_recoverable_secret(value: str) -> bool:
    return bool(value and value.startswith(_FERNET_PREFIX))
