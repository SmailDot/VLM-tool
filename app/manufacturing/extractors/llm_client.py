"""
LLM (Logic Language Model) Client for instruction parsing and reasoning.

Uses OpenAI-compatible API (Ollama) to parse natural language instructions
into structured JSON actions for manufacturing process updates.
"""

from __future__ import annotations

from typing import Optional, Dict, Any, List
import json
import re

try:
    from openai import OpenAI
    from openai.types.chat import ChatCompletionMessageParam
except ImportError:
    raise ImportError(
        "OpenAI SDK not installed. Run: pip install openai>=1.0.0"
    )

from ...config import (
    LLM_BASE_URL,
    LLM_MODEL,
    LLM_SYSTEM_PROMPT,
    LLM_TIMEOUT,
    LLM_MAX_TOKENS
)


class LLMClient:
    """
    Client for LLM inference via OpenAI-compatible API (Ollama).
    """

    def __init__(
        self,
        base_url: str = LLM_BASE_URL,
        api_key: str = "not-needed",
        model: str = LLM_MODEL,
        timeout: int = LLM_TIMEOUT,
        max_retries: int = 2
    ) -> None:
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries

        try:
            self.client = OpenAI(
                base_url=base_url,
                api_key=api_key,
                timeout=timeout,
                max_retries=max_retries
            )
        except Exception as e:
            print(f"Warning: Failed to initialize LLM client: {e}")
            self.client = None

    def is_available(self) -> bool:
        if self.client is None:
            return False

        try:
            self.client.models.list()
            return True
        except Exception as e:
            print(f"LLM service unavailable: {e}")
            print("提示：請確認 Ollama 已啟動，或前往 D:\\AI_Models 進行確認")
            return False

    def parse_instruction(
        self,
        instruction: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Parse natural language instruction into structured actions.

        Args:
            instruction: User input text.
            context: Optional context for parsing.

        Returns:
            Parsed JSON dict or None if failed.
        """
        if self.client is None:
            print("Error: LLM client not initialized")
            return None

        payload = {
            "instruction": instruction,
            "context": context or {}
        }

        if context and "predictions" in context:
            minimal_predictions = []
            for item in context.get("predictions", []):
                if isinstance(item, dict):
                    minimal_predictions.append({
                        "process_id": item.get("process_id"),
                        "process_name": item.get("process_name")
                    })
            payload_context = {"predictions": minimal_predictions}
            available = context.get("available_processes") if isinstance(context, dict) else None
            if isinstance(available, list) and available:
                payload_context["available_processes"] = available
            payload["context"] = payload_context

        messages: List[ChatCompletionMessageParam] = [
            {"role": "system", "content": LLM_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "請將以下口語指令解析為 JSON。\n"
                    "你可以自由理解自然語言，不要硬套規則。\n"
                    "使用者可能會提供一份完整的製程分析報告。\n"
                    "請掃描文字中提到的所有製程代碼（格式如 [C01], C01, K01）。\n"
                    "如果使用者描述了該製程存在的理由（例如『因為有板金輪廓』），請視為 add。\n"
                    "如果使用者說『不需要』、『移除』或『錯誤』，請視為 remove。\n"
                    "必須精準提取 reason（理由）。\n"
                    "target_id 必須是純代碼（例如 C01），不要包含括號；若看到 [C01] 請自動去除括號。\n"
                    "若語句是條件式或不確定，請不要產生 action，而寫入 rag_knowledge。\n"
                    "actions 只能包含 add/remove，target_id 優先從 available_processes 選擇；若無法對應可用 target_name。\n"
                    "輸出格式：{\"actions\":[{\"type\":\"add|remove\",\"target_id\":\"C01\",\"target_name\":\"雷射切割\",\"reason\":\"...\"}],\"rag_knowledge\":\"...\"}\n\n"
                    "範例：\n"
                    "User Input: 這裡看到了折彎線，所以要有 [D01] 折彎。但是 [F01] 焊接是不對的，因為沒看到符號。\n"
                    "Output: {\n"
                    "  \"actions\": [\n"
                    "    {\"type\": \"add\", \"target_id\": \"D01\", \"reason\": \"看到了折彎線\"},\n"
                    "    {\"type\": \"remove\", \"target_id\": \"F01\", \"reason\": \"沒看到符號\"}\n"
                    "  ],\n"
                    "  \"rag_knowledge\": \"若有折彎線則需 D01；若無焊接符號則不應有 F01。\"\n"
                    "}\n\n"
                    f"{json.dumps(payload, ensure_ascii=False)}"
                )
            }
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.0,
                max_tokens=LLM_MAX_TOKENS
            )

            content = response.choices[0].message.content
            if content is None:
                return None

            try:
                return json.loads(content)
            except json.JSONDecodeError:
                raw_content = content.strip()
                if "```json" in raw_content:
                    raw_content = raw_content.split("```json")[1].split("```")[0].strip()
                elif raw_content.startswith("```"):
                    raw_content = raw_content.strip("`").strip()

                match = re.search(r"\{.*\}", raw_content, re.DOTALL)
                if match:
                    try:
                        return json.loads(match.group(0))
                    except json.JSONDecodeError:
                        pass

                return {
                    "error": "parse_error",
                    "raw_response": content
                }
        except Exception as e:
            print(f"Error during LLM instruction parse: {e}")
            print(f"Endpoint: {self.base_url}")
            print(f"Model: {self.model}")
            print("提示：請確認 Ollama 已啟動，或前往 D:\\AI_Models 進行確認")
            return None
