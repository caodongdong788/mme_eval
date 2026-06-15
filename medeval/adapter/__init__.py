"""Adapter 包：抽象 chatbot 调用接口，方便切换不同实现。

类型分发的单一真值源是 ``registry``：导入下面的 adapter 类会触发各自的
``@register_adapter`` 装饰器登记。``build_adapter`` / ``supported_adapter_types`` /
``config_key_for`` 均从注册表派生（``config.py`` 的校验亦复用同一份清单）。
"""

from .base import BaseAdapter, ChatRequest, ChatResponse
from .http import HttpAdapter
from .openai_compat import OpenAICompatAdapter
from .registry import (
    build_adapter,
    config_key_for,
    register_adapter,
    supported_adapter_types,
)

__all__ = [
    "BaseAdapter",
    "ChatRequest",
    "ChatResponse",
    "HttpAdapter",
    "OpenAICompatAdapter",
    "build_adapter",
    "config_key_for",
    "register_adapter",
    "supported_adapter_types",
]
