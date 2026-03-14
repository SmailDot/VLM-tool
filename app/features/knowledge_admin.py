"""Knowledge base admin feature slice."""

from typing import Any, Dict, List

from app.knowledge.manager import KnowledgeBaseManager


def list_kb_entries() -> List[Dict[str, Any]]:
    """Return all knowledge base entries."""
    return KnowledgeBaseManager().db


def update_kb_entry_description(entry_id: str, original_features: Dict[str, Any], edited_desc: str) -> None:
    """Update entry description fields used by RAG retrieval."""
    edited_desc_text = (edited_desc or "").strip()
    features = dict(original_features or {})
    features["raw_vlm_description"] = edited_desc_text
    KnowledgeBaseManager().update_entry(
        entry_id,
        {
            "features": features,
            "reasoning": edited_desc_text,
        },
    )
