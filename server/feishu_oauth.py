"""飞书 OAuth2 授权码流程纯函数封装（无状态，便于单测）。

接口（2026-06 核实）：
  - 授权页：https://accounts.feishu.cn/open-apis/authen/v1/authorize
  - 换/刷新 token：POST https://open.feishu.cn/open-apis/authen/v2/oauth/token
  - 用户信息：GET https://open.feishu.cn/open-apis/authen/v1/user_info

注意：拿 ``refresh_token`` 必须在飞书后台开通 ``offline_access`` 权限。有效期一律取飞书
返回的 ``expires_in`` / ``refresh_token_expires_in``，不要硬编码。
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

AUTHORIZE_URL = "https://accounts.feishu.cn/open-apis/authen/v1/authorize"
TOKEN_URL = "https://open.feishu.cn/open-apis/authen/v2/oauth/token"
USER_INFO_URL = "https://open.feishu.cn/open-apis/authen/v1/user_info"

_TIMEOUT = 30.0


class FeishuOAuthError(RuntimeError):
    """飞书 OAuth 接口返回非零 code 或网络异常。"""


@dataclass(frozen=True)
class TokenBundle:
    access_token: str
    expires_in: int
    refresh_token: str
    refresh_token_expires_in: int
    scope: str = ""


@dataclass(frozen=True)
class UserInfo:
    open_id: str
    name: str
    avatar_url: str = ""


def _client() -> httpx.Client:
    """可在测试中 monkeypatch 以注入 MockTransport。"""
    return httpx.Client(timeout=_TIMEOUT)


def build_authorize_url(
    *, app_id: str, redirect_uri: str, scope: str, state: str
) -> str:
    query = urlencode(
        {
            "client_id": app_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "state": state,
        }
    )
    return f"{AUTHORIZE_URL}?{query}"


def _post_token(payload: dict) -> TokenBundle:
    with _client() as client:
        resp = client.post(TOKEN_URL, json=payload)
    return _parse_token(resp)


def _parse_token(resp: httpx.Response) -> TokenBundle:
    try:
        data = resp.json()
    except Exception as e:  # noqa: BLE001
        raise FeishuOAuthError(f"token 响应非 JSON：{e}") from e
    if data.get("code", 0) != 0:
        raise FeishuOAuthError(
            f"飞书 token 接口返回 code={data.get('code')} msg={data.get('msg')}"
        )
    return TokenBundle(
        access_token=data.get("access_token", ""),
        expires_in=int(data.get("expires_in", 0)),
        refresh_token=data.get("refresh_token", ""),
        refresh_token_expires_in=int(data.get("refresh_token_expires_in", 0)),
        scope=data.get("scope", ""),
    )


def exchange_code(
    *, app_id: str, app_secret: str, code: str, redirect_uri: str
) -> TokenBundle:
    return _post_token(
        {
            "grant_type": "authorization_code",
            "client_id": app_id,
            "client_secret": app_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        }
    )


def refresh_token(*, app_id: str, app_secret: str, refresh_token: str) -> TokenBundle:
    return _post_token(
        {
            "grant_type": "refresh_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "refresh_token": refresh_token,
        }
    )


def get_user_info(access_token: str) -> UserInfo:
    with _client() as client:
        resp = client.get(
            USER_INFO_URL, headers={"Authorization": f"Bearer {access_token}"}
        )
    try:
        data = resp.json()
    except Exception as e:  # noqa: BLE001
        raise FeishuOAuthError(f"user_info 响应非 JSON：{e}") from e
    if data.get("code", 0) != 0:
        raise FeishuOAuthError(
            f"飞书 user_info 返回 code={data.get('code')} msg={data.get('msg')}"
        )
    d = data.get("data", data)
    return UserInfo(
        open_id=d.get("open_id", ""),
        name=d.get("name", ""),
        avatar_url=d.get("avatar_url", ""),
    )
