"""
Instruction Parser for Teacher Mode.

Converts natural language corrections into structured actions via LLM.
"""

from __future__ import annotations

from typing import Optional, Dict, Any

from ..extractors import LLMClient


class InstructionParser:
    """
    Parse user instructions into JSON actions and RAG knowledge.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        self.llm_client = llm_client or LLMClient()

    def parse(
        self,
        instruction: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Parse instruction into structured actions.

        Returns:
            Dict with "actions" and optional "rag_knowledge".
        """
        if not instruction.strip():
            return None

        if not self.llm_client.is_available():
            return None

        parsed = self.llm_client.parse_instruction(instruction, context=context)
        if not parsed:
            return parsed

        actions = parsed.get("actions", [])
        if isinstance(actions, list):
            for action in actions:
                if isinstance(action, dict) and "target_id" in action:
                    target_id = action.get("target_id")
                    if isinstance(target_id, str):
                        action["target_id"] = target_id.replace("[", "").replace("]", "").strip()

        return parsed
