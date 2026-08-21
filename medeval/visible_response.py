"""将适配器原始响应归一为最终用户可见的文本。"""

from __future__ import annotations

import re

from .models import ChatMessage, ConversationTrace


# CX 对话页会隐藏 Markdown 标题开头的 ``[护理]`` 这类内部分类标签；评测必须
# 使用同一份用户可见文本，不能把被隐藏的标签计入标题重复或措辞类规则。
_CX_HIDDEN_HEADING_LABEL_RE = re.compile(
    r"(?m)^(#{1,6}[ \t]+)\[(?=[^\]\r\n]*[^\d\s\]])[^\]\r\n]{1,32}\][ \t]+"
)


def normalize_cx_agent_visible_text(value: str) -> str:
    """移除 CX 页面不展示的 Markdown 标题内部分类标签。

    只处理标题开头的短方括号标签，不影响正文中的引用编号（如 ``[1]``）、
    普通方括号文本或 Markdown 链接。
    """
    return _CX_HIDDEN_HEADING_LABEL_RE.sub(r"\1", value or "")


def normalize_cx_agent_visible_trace(trace: ConversationTrace) -> ConversationTrace:
    """返回用于判分的 CX 用户可见对话副本，保留原始事件审计数据。"""
    messages = [
        message.model_copy(
            update={"content": normalize_cx_agent_visible_text(message.content)}
        )
        if message.role == "assistant"
        else message
        for message in trace.messages
    ]
    return trace.model_copy(update={"messages": messages})
