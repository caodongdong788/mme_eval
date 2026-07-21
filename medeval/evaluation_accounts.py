"""cx-agent 隔离评测账号的可登录凭据展示。"""

from __future__ import annotations

import os


EVALUATION_TEST_LOGIN_ACCOUNTS = {
    "00000000-0000-0000-0000-000000000101": "+8610000000101",
    "00000000-0000-0000-0000-000000000102": "+8610000000102",
    "00000000-0000-0000-0000-000000000103": "+8610000000103",
    "00000000-0000-0000-0000-000000000201": "+8610000000201",
    "00000000-0000-0000-0000-000000000202": "+8610000000202",
    "00000000-0000-0000-0000-000000000203": "+8610000000203",
}


def _verification_codes() -> dict[str, str]:
    """读取仅存于服务端环境变量中的测试验证码，不进入代码仓库。"""
    result: dict[str, str] = {}
    for item in os.environ.get("CX_AGENT_EVALUATION_LOGIN_CODES", "").split(","):
        account, separator, code = item.strip().partition("=")
        if separator and account and code:
            result[account] = code
    return result


def evaluation_account_credentials(
    test_user_id: object,
    *,
    login_account: object = None,
) -> dict[str, str]:
    """由内部 UUID 解析测试登录账号，并按环境配置补充验证码。"""
    user_id = str(test_user_id or "")
    account = str(login_account or EVALUATION_TEST_LOGIN_ACCOUNTS.get(user_id) or "")
    if not account:
        return {}
    credentials = {"login_account": account}
    if code := _verification_codes().get(account):
        credentials["verification_code"] = code
    return credentials
