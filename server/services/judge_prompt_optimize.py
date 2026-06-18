"""判分模型 prompt 质检：用 config.yaml 默认 judges.llm 调 LLM 优化草稿。"""

from __future__ import annotations

import os

from fastapi import HTTPException

from medeval.config import load_config
from medeval.judges.llm_backend import backend_from_llm_cfg
from medeval.judges.prompt_template import DEFAULT_PROMPT_TEMPLATE, validate_judge_prompt_template

from ..settings import get_settings

_META_PROMPT = """\
你是医疗 chatbot 评测 prompt 工程师。请优化下方「待优化 Judge Prompt」，使其更清晰、可执行，保持医疗保守评测口径（从严、不同情分）。

优化结果 MUST 同时满足以下硬性格式（不合规视为失败）：
1. 正文 MUST 原样包含且仅将以下三处作为 Python format 占位符：{{conversation}}、{{rubric_text}}、{{tool_context}}
2. JSON 输出示例中的花括号 MUST 写成双花括号 {{ }}，不得出现其它单花括号字段名
3. MUST 在「输出要求」中明确要求模型仅输出 JSON，且结构含 scores、reasons、flags 三个顶层字段
4. 保持医疗 chatbot rubric 0~max 整数打分语境

仅输出 JSON 对象：{{"optimized_prompt": "<优化后的 prompt 正文>"}}，不要 markdown。

【待优化 Judge Prompt】
{draft}
"""


def _optimize_llm():
    llm = load_config(get_settings().config_path).judges.llm
    if not llm.enabled:
        raise HTTPException(status_code=503, detail="config.yaml 中 judges.llm 未启用，无法质检 prompt")
    if not (llm.api_key or os.environ.get(llm.api_key_env or "", "")):
        raise HTTPException(
            status_code=503,
            detail=f"judges.llm 未配置 API Key（环境变量 {llm.api_key_env}）",
        )
    return backend_from_llm_cfg(llm, owner="PromptOptimize"), llm


async def optimize_judge_prompt(draft: str) -> str:
    backend, llm = _optimize_llm()
    base = (draft or "").strip() or DEFAULT_PROMPT_TEMPLATE
    meta = _META_PROMPT.format(draft=base)
    try:
        data = await backend.chat_json(
            model=llm.model,
            prompt=meta,
            temperature=llm.temperature,
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Prompt 质检失败：{exc}") from exc
    optimized = str(data.get("optimized_prompt") or "").strip()
    if not optimized:
        raise HTTPException(status_code=422, detail="模型未返回有效 prompt")
    try:
        validate_judge_prompt_template(optimized)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"质检结果不符合系统格式：{exc}") from exc
    return optimized
