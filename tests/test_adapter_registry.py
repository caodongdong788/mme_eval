"""Adapter 注册表单测（change 2026-06-02-adapter-plugin-registry）。

覆盖：
  - 注册集合含 http + 4 个 openai_compat alias
  - config_key_for 映射
  - build_adapter 命中（别名取对应 section）/ 空·None·未知 fail-fast 文案
  - 重复注册同名 type → ValueError
"""

from __future__ import annotations

import asyncio

import pytest

from medeval.adapter import (
    CxAgentAdapter,
    HttpAdapter,
    OpenAICompatAdapter,
    build_adapter,
    config_key_for,
    register_adapter,
    supported_adapter_types,
)


def test_registry_contains_builtin_types():
    types = supported_adapter_types()
    for t in ("http", "openai_compat", "openai", "doubao", "ark", "cx_agent"):
        assert t in types
    # 排序返回
    assert types == sorted(types)


def test_config_key_for():
    assert config_key_for("http") == "http"
    assert config_key_for("cx_agent") == "cx_agent"
    assert config_key_for("doubao") == "openai_compat"
    assert config_key_for("openai_compat") == "openai_compat"
    assert config_key_for("nonexistent") is None


def test_build_adapter_http():
    a = build_adapter("http", {"http": {"base_url": "http://x"}})
    assert isinstance(a, HttpAdapter)


def test_build_adapter_cx_agent(monkeypatch):
    monkeypatch.setenv("CX_AGENT_TEST_TOKEN", "token-1")
    a = build_adapter("cx_agent", {"cx_agent": {"base_url": "http://cx.local"}})
    assert isinstance(a, CxAgentAdapter)
    assert a.base_url == "http://cx.local"
    asyncio.run(a.close())


def test_build_adapter_alias_resolves_to_openai_compat():
    cfg = {"openai_compat": {"api_key": "sk-test", "base_url": "http://x", "model": "m"}}
    for alias in ("openai_compat", "openai", "doubao", "ark"):
        a = build_adapter(alias, cfg)
        assert isinstance(a, OpenAICompatAdapter)


def test_build_adapter_failfast_empty_and_none():
    with pytest.raises(ValueError, match="config.adapter.type is required"):
        build_adapter("", {})
    with pytest.raises(ValueError, match="config.adapter.type is required"):
        build_adapter(None, {})  # type: ignore[arg-type]


def test_build_adapter_unknown_type():
    with pytest.raises(ValueError, match="Unknown adapter type"):
        build_adapter("mock", {})
    with pytest.raises(ValueError, match="Unknown adapter type"):
        build_adapter("nonexistent_xyz", {})


def test_duplicate_registration_rejected():
    with pytest.raises(ValueError, match="已被注册"):

        @register_adapter("http", config_key="http")
        class _Dup(HttpAdapter):
            pass


def test_register_adapter_requires_a_name():
    with pytest.raises(ValueError, match="至少需要一个 type 名"):

        @register_adapter(config_key="x")
        class _NoName(HttpAdapter):
            pass
