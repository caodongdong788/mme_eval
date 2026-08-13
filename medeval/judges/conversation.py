"""Judge 共用的对话文本渲染。"""

from __future__ import annotations

from ..models import ConversationTrace


def format_conversation(trace: ConversationTrace) -> str:
    lines: list[str] = []
    turn_index = 0
    evidence_index = 0
    for message in trace.messages:
        if message.role == "system":
            lines.append(f"[系统提示] {message.content}")
        elif message.role == "user":
            turn_index += 1
            lines.append(f"[turn {turn_index} · 用户] {message.content}")
        else:
            evidence_index += 1
            lines.append(
                f"[turn {max(turn_index, 1)} · bot · 证据 B{evidence_index}] "
                f"{message.content}"
            )
    return "\n".join(lines)
