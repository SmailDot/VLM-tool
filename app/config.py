"""
Application configuration.

Values can be overridden by environment variables.
"""

from __future__ import annotations

import os

# VLM (LM Studio)
VLM_BASE_URL = os.getenv("VLM_BASE_URL", "http://localhost:1234/v1")
VLM_MODEL = os.getenv("VLM_MODEL", "LFT2.5-1.6b")

# LLM (Ollama)
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3:4b")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "45"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "400"))

LLM_SYSTEM_PROMPT = (
    "你是資深的板金製程工程師。"
    "你只負責判斷金屬加工製程 (如雷射切割、折彎、焊接、酸洗)。"
    "請忽略所有非製造相關的知識。"
    "你的輸出必須是嚴格的 JSON 格式。"
)
