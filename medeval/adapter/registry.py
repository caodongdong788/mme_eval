"""Adapter 注册表 —— adapter 类型分发的单一真值源。

参见 OpenSpec change ``2026-06-02-adapter-plugin-registry``。

新增/接入一个 adapter 只需在其类定义处声明一次::

    @register_adapter("mybot", config_key="mybot")
    class MyBotAdapter(BaseAdapter):
        ...

即可被 ``build_adapter`` 与配置校验（``config.py``）同时识别——无需修改本文件的
分发逻辑，也无需在配置 schema 中另行登记类型名。"已支持类型清单"由 ``_REGISTRY``
单一提供，杜绝"工厂支持但配置拒绝"之类的漂移。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .base import BaseAdapter


@dataclass(frozen=True)
class _Entry:
    factory: Callable[[dict | None], BaseAdapter]
    config_key: str  # 该类型从 adapter 配置中取哪个子块作为构造 kwargs


_REGISTRY: dict[str, _Entry] = {}


def register_adapter(*type_names: str, config_key: str):
    """类装饰器：把 type 名（含 alias）登记到注册表。

    重复登记同一 type 名 → ``ValueError``（避免静默覆盖造成分发歧义）。
    """
    if not type_names:
        raise ValueError("register_adapter 至少需要一个 type 名")

    def deco(cls: type[BaseAdapter]) -> type[BaseAdapter]:
        entry = _Entry(
            factory=lambda section: cls(**(section or {})),
            config_key=config_key,
        )
        for name in type_names:
            if name in _REGISTRY:
                raise ValueError(
                    f"adapter type {name!r} 已被注册（指向 "
                    f"{_REGISTRY[name].factory}），禁止重复注册。"
                )
            _REGISTRY[name] = entry
        return cls

    return deco


def supported_adapter_types() -> list[str]:
    """已注册的全部 adapter 类型名（含 alias），排序返回。"""
    return sorted(_REGISTRY)


def config_key_for(adapter_type: str) -> str | None:
    """返回该类型期望的 adapter 配置子块键；未注册 → None。"""
    entry = _REGISTRY.get(adapter_type)
    return entry.config_key if entry else None


def build_adapter(adapter_type: str, config: dict) -> BaseAdapter:
    """根据配置构造 adapter 实例（查注册表分发，开闭扩展）。

    Fail-fast：``adapter_type`` 为空 / None / 不在注册表中时直接抛错。
    历史上的 ``mock`` 适配器已删除（见 OpenSpec change ``drop-mock-adapter``），
    框架不再提供 dummy bot 兜底，避免在评测中产生看似通过的"假成功"。
    """
    if not adapter_type:
        raise ValueError(
            "config.adapter.type is required. Supported: "
            f"{', '.join(supported_adapter_types())}. "
            "MockAdapter 已下线，请配置真实的 chatbot adapter。"
        )
    entry = _REGISTRY.get(adapter_type)
    if entry is None:
        raise ValueError(
            f"Unknown adapter type: {adapter_type!r}. "
            f"Supported: {', '.join(supported_adapter_types())}. "
            "自定义 adapter 请用 @register_adapter 装饰器注册。"
        )
    return entry.factory(config.get(entry.config_key))
