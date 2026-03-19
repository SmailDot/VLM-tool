"""
FAISS-based dual vector store for RAG retrieval.

Manages two separate indices:
- Image embeddings (DINOv2, 768-dim)
- Text embeddings (multilingual sentence-transformers, 384-dim)

Supports add / search / remove / save / load operations.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

# Lazy-loaded heavy dependencies
_faiss = None
_SentenceTransformer = None


def _ensure_faiss():
    global _faiss
    if _faiss is None:
        import faiss
        _faiss = faiss
    return _faiss


def _ensure_sentence_transformer():
    global _SentenceTransformer
    if _SentenceTransformer is None:
        from sentence_transformers import SentenceTransformer
        _SentenceTransformer = SentenceTransformer
    return _SentenceTransformer


# ---------------------------------------------------------------------------
# Text Embedder (thin wrapper around sentence-transformers)
# ---------------------------------------------------------------------------

class TextEmbedder:
    """Compute text embeddings using a multilingual sentence-transformer model."""

    MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
    DIM = 384

    def __init__(self) -> None:
        self._model = None

    def _load(self):
        if self._model is None:
            ST = _ensure_sentence_transformer()
            self._model = ST(self.MODEL_NAME)
        return self._model

    def encode(self, text: str) -> np.ndarray:
        """Return L2-normalised 384-dim embedding for *text*."""
        model = self._load()
        vec = model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
        return vec.astype(np.float32)

    def encode_batch(self, texts: List[str]) -> np.ndarray:
        """Return (N, 384) L2-normalised embeddings."""
        model = self._load()
        vecs = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        return vecs.astype(np.float32)


# ---------------------------------------------------------------------------
# Dual FAISS Index
# ---------------------------------------------------------------------------

class DualVectorStore:
    """
    Two FAISS IndexFlatIP indices (inner-product on L2-normalised vectors
    ≡ cosine similarity) keyed by a shared integer ID list.

    Persistence: ``save()`` writes two ``.faiss`` files + one ``.npy`` id-map
    to a directory.  ``load()`` restores them.
    """

    IMAGE_DIM = 768   # DINOv2 ViT-Base
    TEXT_DIM = 384    # multilingual-MiniLM-L12-v2

    def __init__(self, store_dir: str = "knowledge_vectors") -> None:
        self._dir = Path(store_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

        faiss = _ensure_faiss()

        # Paths
        self._img_index_path = self._dir / "image.faiss"
        self._txt_index_path = self._dir / "text.faiss"
        self._ids_path = self._dir / "entry_ids.npy"

        # Try to load existing indices, or create empty ones
        if self._img_index_path.exists() and self._txt_index_path.exists():
            self._img_index = faiss.read_index(str(self._img_index_path))
            self._txt_index = faiss.read_index(str(self._txt_index_path))
            self._ids: List[str] = (
                np.load(str(self._ids_path), allow_pickle=True).tolist()
                if self._ids_path.exists() else []
            )
        else:
            self._img_index = faiss.IndexFlatIP(self.IMAGE_DIM)
            self._txt_index = faiss.IndexFlatIP(self.TEXT_DIM)
            self._ids = []

    # ---- mutators --------------------------------------------------------

    def add(
        self,
        entry_id: str,
        image_embedding: Optional[np.ndarray] = None,
        text_embedding: Optional[np.ndarray] = None,
    ) -> None:
        """Add one entry.  At least one embedding must be provided."""
        faiss = _ensure_faiss()

        if image_embedding is not None:
            vec = image_embedding.astype(np.float32).reshape(1, -1)
            self._img_index.add(vec)
        else:
            # Placeholder zero-vector (will have ~0 similarity with anything)
            self._img_index.add(np.zeros((1, self.IMAGE_DIM), dtype=np.float32))

        if text_embedding is not None:
            vec = text_embedding.astype(np.float32).reshape(1, -1)
            self._txt_index.add(vec)
        else:
            self._txt_index.add(np.zeros((1, self.TEXT_DIM), dtype=np.float32))

        self._ids.append(entry_id)

    def remove(self, entry_id: str) -> bool:
        """Remove entry by id.  Rebuilds indices (fine for <10 k entries)."""
        if entry_id not in self._ids:
            return False

        idx = self._ids.index(entry_id)
        self._ids.pop(idx)

        # Rebuild both indices without the removed row
        faiss = _ensure_faiss()

        n = self._img_index.ntotal
        if n > 0:
            all_img = np.vstack([self._img_index.reconstruct(i) for i in range(n)])
            all_txt = np.vstack([self._txt_index.reconstruct(i) for i in range(n)])
            all_img = np.delete(all_img, idx, axis=0)
            all_txt = np.delete(all_txt, idx, axis=0)

            self._img_index = faiss.IndexFlatIP(self.IMAGE_DIM)
            self._txt_index = faiss.IndexFlatIP(self.TEXT_DIM)
            if len(all_img) > 0:
                self._img_index.add(all_img)
                self._txt_index.add(all_txt)

        return True

    # ---- queries ---------------------------------------------------------

    def search(
        self,
        image_embedding: Optional[np.ndarray] = None,
        text_embedding: Optional[np.ndarray] = None,
        top_k: int = 3,
        image_weight: float = 0.4,
        text_weight: float = 0.6,
    ) -> List[Tuple[str, float]]:
        """
        Hybrid search.  Returns ``[(entry_id, combined_score), ...]``
        sorted descending by score.

        If only one embedding is provided the other channel contributes 0.
        """
        if self._img_index.ntotal == 0:
            return []

        k = min(top_k, self._img_index.ntotal)

        # Image channel
        img_scores = np.zeros(self._img_index.ntotal, dtype=np.float32)
        if image_embedding is not None:
            q = image_embedding.astype(np.float32).reshape(1, -1)
            # Search all entries for accurate ranking
            scores_i, indices_i = self._img_index.search(q, self._img_index.ntotal)
            for rank in range(len(indices_i[0])):
                j = indices_i[0][rank]
                if j >= 0:
                    img_scores[j] = max(scores_i[0][rank], 0.0)

        # Text channel
        txt_scores = np.zeros(self._txt_index.ntotal, dtype=np.float32)
        if text_embedding is not None:
            q = text_embedding.astype(np.float32).reshape(1, -1)
            scores_t, indices_t = self._txt_index.search(q, self._txt_index.ntotal)
            for rank in range(len(indices_t[0])):
                j = indices_t[0][rank]
                if j >= 0:
                    txt_scores[j] = max(scores_t[0][rank], 0.0)

        # Weighted combination
        combined = image_weight * img_scores + text_weight * txt_scores
        top_indices = np.argsort(-combined)[:k]

        results: List[Tuple[str, float]] = []
        for i in top_indices:
            score = float(combined[i])
            if score > 0:
                results.append((self._ids[i], score))
        return results

    # ---- persistence -----------------------------------------------------

    def save(self) -> None:
        """Write indices and id-map to disk."""
        faiss = _ensure_faiss()
        faiss.write_index(self._img_index, str(self._img_index_path))
        faiss.write_index(self._txt_index, str(self._txt_index_path))
        np.save(str(self._ids_path), np.array(self._ids, dtype=object))

    def __len__(self) -> int:
        return self._img_index.ntotal
