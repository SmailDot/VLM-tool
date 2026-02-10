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
            payload["context"] = {"predictions": minimal_predictions}

        messages: List[ChatCompletionMessageParam] = [
            {"role": "system", "content": LLM_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "請將以下口語指令解析為 JSON。\n"
                    "輸出格式：{\"actions\":[...],\"rag_knowledge\":\"...\"}\n\n"
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
