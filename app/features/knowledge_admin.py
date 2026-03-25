"""Knowledge base admin feature slice.

Provides CRUD + statistics for the RAG knowledge base.
All functions are stateless — they instantiate KnowledgeBaseManager on each
call, so they can be imported and used as independent puzzle-pieces.
"""

from typing import Any, Dict, List, Optional

from app.knowledge.manager import KnowledgeBaseManager


def list_kb_entries() -> List[Dict[str, Any]]:
    """Return all knowledge base entries."""
    return KnowledgeBaseManager().db


def delete_kb_entry(entry_id: str) -> bool:
    """Delete an entry from the knowledge base (JSON + FAISS)."""
    kb = KnowledgeBaseManager()
    # Remove from FAISS index
    try:
        vs = kb._get_vector_store()
        vs.remove(entry_id)
        vs.save()
    except Exception as e:
        print(f"Warning: FAISS removal failed for {entry_id}: {e}")
    # Remove from JSON DB
    original_len = len(kb.db)
    kb.db = [e for e in kb.db if e.get("id") != entry_id]
    if len(kb.db) < original_len:
        kb._save_db()
        return True
    return False


def get_kb_stats() -> Dict[str, Any]:
    """Compute summary statistics for the knowledge base.

    Returns a dict with:
        total_entries: number of KB entries
        unique_images: distinct image hashes
        avg_desc_length: average description character count
        vocab_coverage: count of each geometry term across all entries
        earliest / latest: timestamp range
    """
    kb = KnowledgeBaseManager()
    entries = kb.db
    if not entries:
        return {"total_entries": 0}

    hashes = {e.get("image_hash", "") for e in entries}
    desc_lengths = []
    vocab_counts: Dict[str, int] = {}

    from app.manufacturing.schema import TIER1_VOCABULARY
    _vocab = TIER1_VOCABULARY

    for entry in entries:
        desc = (
            entry.get("features", {}).get("raw_vlm_description", "")
            or entry.get("reasoning", "")
        )
        desc_lengths.append(len(desc))
        desc_lower = desc.lower()
        for term in _vocab:
            if term.lower() in desc_lower:
                vocab_counts[term] = vocab_counts.get(term, 0) + 1

    timestamps = [e.get("timestamp", "") for e in entries if e.get("timestamp")]
    timestamps.sort()

    return {
        "total_entries": len(entries),
        "unique_images": len(hashes - {""}),
        "avg_desc_length": round(sum(desc_lengths) / len(desc_lengths)) if desc_lengths else 0,
        "vocab_coverage": dict(sorted(vocab_counts.items(), key=lambda x: x[1], reverse=True)),
        "earliest": timestamps[0] if timestamps else "",
        "latest": timestamps[-1] if timestamps else "",
    }


def get_rag_metrics_history() -> list:
    """Return RAG effectiveness metrics across all KB entries."""
    return KnowledgeBaseManager().get_rag_metrics_history()


def update_kb_entry_description(
    entry_id: str,
    original_features: Dict[str, Any],
    edited_desc: Optional[str],
) -> None:
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
        reindex_text=True,
    )
