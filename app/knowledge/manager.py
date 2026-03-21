"""
Knowledge Base Manager for RAG cases.

Stores image features, corrected processes, and expert reasoning.
Supports FAISS-based semantic retrieval (image + text embeddings).
"""

from __future__ import annotations

import re as _re
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from pathlib import Path
import json
import re
import shutil
import hashlib

import numpy as np


class KnowledgeBaseManager:
    """
    Manage knowledge base entries for manufacturing process recognition.

    Each entry stores:
    - image copy (local storage)
    - extracted features (VLM analysis)
    - corrected process IDs
    - expert reasoning

    Retrieval uses a dual FAISS vector store (image DINOv2 768-dim +
    text multilingual-MiniLM 384-dim) with SHA-256 exact-match fast path.
    """

    def __init__(
        self,
        db_path: str = "knowledge_db.json",
        image_storage_dir: str = "knowledge_images"
    ) -> None:
        self.db_path = Path(db_path)
        self.image_storage_dir = Path(image_storage_dir)
        self.image_storage_dir.mkdir(parents=True, exist_ok=True)
        self.db: List[Dict[str, Any]] = self._load_db()

        # Lazy-loaded components (heavy models)
        self._vector_store = None
        self._text_embedder = None
        self._image_embedder = None

    # ------------------------------------------------------------------
    # Lazy loaders
    # ------------------------------------------------------------------

    def _get_vector_store(self):
        if self._vector_store is None:
            from app.knowledge.vector_store import DualVectorStore
            self._vector_store = DualVectorStore()
        return self._vector_store

    def _get_text_embedder(self):
        if self._text_embedder is None:
            from app.knowledge.vector_store import TextEmbedder
            self._text_embedder = TextEmbedder()
        return self._text_embedder

    def _get_image_embedder(self):
        if self._image_embedder is None:
            from app.manufacturing.extractors.embeddings import VisualEmbedder
            self._image_embedder = VisualEmbedder()
        return self._image_embedder

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_db(self) -> List[Dict[str, Any]]:
        if not self.db_path.exists():
            return []
        try:
            with self.db_path.open("r", encoding="utf-8") as file:
                return json.load(file)
        except Exception:
            return []

    def _save_db(self) -> None:
        with self.db_path.open("w", encoding="utf-8") as file:
            json.dump(self.db, file, ensure_ascii=False, indent=2)

    def _calculate_hash(self, image_path: str) -> str:
        h = hashlib.sha256()
        with open(image_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    # ------------------------------------------------------------------
    # Embedding helpers
    # ------------------------------------------------------------------

    def _compute_image_embedding(
        self, image_path: str
    ) -> Optional[np.ndarray]:
        """Compute DINOv2 embedding from an image file path."""
        try:
            embedder = self._get_image_embedder()
            return embedder.extract_from_file(image_path)
        except Exception as e:
            print(f"Warning: image embedding failed: {e}")
            return None

    def _compute_image_embedding_from_array(
        self, image: np.ndarray
    ) -> Optional[np.ndarray]:
        """Compute DINOv2 embedding from a BGR numpy array."""
        try:
            embedder = self._get_image_embedder()
            return embedder.extract(image)
        except Exception as e:
            print(f"Warning: image embedding failed: {e}")
            return None

    def _compute_text_embedding(self, text: str) -> Optional[np.ndarray]:
        """Compute sentence-transformer embedding from text."""
        if not text or not text.strip():
            return None
        try:
            embedder = self._get_text_embedder()
            return embedder.encode(text)
        except Exception as e:
            print(f"Warning: text embedding failed: {e}")
            return None

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add_entry(
        self,
        image_path: str,
        features: Dict[str, Any],
        correct_processes: List[str],
        reasoning: str,
        tags: Optional[List[str]] = None,
        bom_context: str = "",
        rag_metrics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Add or update a knowledge entry (dedup by image hash).

        If an entry with the same SHA-256 hash already exists, the latest
        entry is UPDATED in-place (description, reasoning, timestamp) and
        a version link is recorded. Old duplicate entries are marked
        ``superseded`` and removed from FAISS to keep the index clean.

        Args:
            rag_metrics: Optional RAG effectiveness scores computed at
                         HITL save time (v1_distance, v2_distance, improvement).
        """
        if not Path(image_path).exists():
            raise FileNotFoundError(f"Source image not found: {image_path}")

        image_hash = self._calculate_hash(image_path)
        timestamp = datetime.now()

        # ── Dedup: find existing entries with same hash ──────────────
        existing = [e for e in self.db if e.get("image_hash") == image_hash]

        if existing:
            # Update the LATEST existing entry instead of creating a new one
            latest = existing[-1]
            prev_desc = (
                latest.get("features", {}).get("raw_vlm_description", "")
                or latest.get("reasoning", "")
            )
            # Record version history
            version_history = latest.get("version_history", [])
            version_history.append({
                "timestamp": latest.get("timestamp", ""),
                "description_snapshot": prev_desc[:200],
            })

            # Merge updates
            latest["features"] = features
            latest["reasoning"] = reasoning
            latest["correct_processes"] = correct_processes
            latest["bom_context"] = bom_context
            latest["updated_at"] = timestamp.isoformat()
            latest["version_history"] = version_history
            latest["version_count"] = len(version_history) + 1
            if rag_metrics:
                latest["rag_metrics"] = rag_metrics
            if tags:
                latest["tags"] = tags

            # Mark older duplicates as superseded + remove from FAISS
            for old_entry in existing[:-1]:
                if old_entry.get("status") != "superseded":
                    old_entry["status"] = "superseded"
                    old_entry["superseded_by"] = latest["id"]
                    try:
                        vs = self._get_vector_store()
                        vs.remove(old_entry["id"])
                        vs.save()
                    except Exception:
                        pass

            self._save_db()
            # Re-index the latest entry's text embedding
            self._reindex_entry_text(latest["id"], latest)
            print(f"Info: KB dedup — updated existing entry {latest['id']} (v{latest['version_count']})")
            return latest

        # ── New entry (no hash match) ────────────────────────────────
        filename = f"{timestamp.strftime('%Y%m%d_%H%M%S')}_{Path(image_path).name}"
        target_path = self.image_storage_dir / filename
        shutil.copy2(image_path, target_path)

        entry_id = filename.split(".")[0]

        entry = {
            "id": entry_id,
            "timestamp": timestamp.isoformat(),
            "image_rel_path": str(target_path),
            "image_hash": image_hash,
            "features": features,
            "correct_processes": correct_processes,
            "reasoning": reasoning,
            "bom_context": bom_context,
            "tags": tags or [],
            "version_count": 1,
        }
        if rag_metrics:
            entry["rag_metrics"] = rag_metrics

        self.db.append(entry)
        self._save_db()

        # --- Index embeddings in FAISS ---
        try:
            desc_text = features.get("raw_vlm_description", "") or reasoning
            img_emb = self._compute_image_embedding(str(target_path))
            txt_emb = self._compute_text_embedding(desc_text)

            vs = self._get_vector_store()
            vs.add(entry_id, image_embedding=img_emb, text_embedding=txt_emb)
            vs.save()
        except Exception as e:
            print(f"Warning: vector indexing failed (entry saved to JSON): {e}")

        return entry

    def update_entry(
        self,
        entry_id: str,
        new_data: Dict[str, Any],
        reindex_text: bool = False,
    ) -> bool:
        """Update an existing entry and optionally re-index its text embedding.

        Args:
            entry_id: The entry to update.
            new_data: Fields to merge into the entry.
            reindex_text: If True, recompute the text embedding in FAISS
                          from the updated description so that semantic
                          search stays in sync with the edited text.
        """
        for i, entry in enumerate(self.db):
            if entry.get("id") == entry_id:
                self.db[i].update(new_data)
                self.db[i]["updated_at"] = datetime.now().isoformat()
                self._save_db()

                if reindex_text:
                    self._reindex_entry_text(entry_id, self.db[i])

                return True
        return False

    def _reindex_entry_text(self, entry_id: str, entry: Dict[str, Any]) -> None:
        """Remove old vector and re-add with updated text embedding."""
        try:
            desc = (
                entry.get("features", {}).get("raw_vlm_description", "")
                or entry.get("reasoning", "")
            )
            txt_emb = self._compute_text_embedding(desc)

            # Reuse existing image embedding (reconstruct from FAISS)
            vs = self._get_vector_store()
            img_emb = None
            if entry_id in vs._ids:
                idx = vs._ids.index(entry_id)
                img_emb = vs._img_index.reconstruct(idx)
                vs.remove(entry_id)
            else:
                # Entry not in FAISS yet — compute image embedding
                img_path = entry.get("image_rel_path", "")
                if img_path and Path(img_path).exists():
                    img_emb = self._compute_image_embedding(img_path)

            vs.add(entry_id, image_embedding=img_emb, text_embedding=txt_emb)
            vs.save()
        except Exception as e:
            print(f"Warning: text re-indexing failed for {entry_id}: {e}")

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    # Minimum combined similarity score for FAISS results.
    # Below this threshold, the match is too weak to be useful as RAG
    # context and may mislead the VLM instead of helping it.
    MIN_SIMILARITY = 0.35

    def retrieve_similar(
        self,
        current_features: Dict[str, Any],
        image_path: str = "",
        top_k: int = 3,
        raw_vlm_text: str = "",
        query_image: Optional[np.ndarray] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve similar cases from knowledge base.

        Matching priority:
        1. SHA-256 exact hash match (same file -> score 1.0)
        2. FAISS hybrid semantic search (image 0.4 + text 0.6)
        3. Jaccard keyword fallback (if FAISS unavailable or empty)

        Results below ``MIN_SIMILARITY`` are filtered out to prevent
        low-quality matches from misleading the VLM.

        Args:
            current_features: Current extracted features dict.
            image_path: Path to current image (for hash match).
            top_k: Max number of results to return.
            raw_vlm_text: Raw VLM plain-text output for text embedding.
            query_image: BGR numpy array for image embedding search.
        """
        if not self.db:
            return []

        # --- 1. Hash exact match (use LATEST entry for same image) ---
        if image_path and Path(image_path).exists():
            query_hash = self._calculate_hash(image_path)
            latest_hit = None
            for entry in self.db:
                if entry.get("image_hash") == query_hash:
                    latest_hit = entry  # 持續覆寫，最終得到最新的
            if latest_hit is not None:
                hit = dict(latest_hit)
                hit["_match_type"] = "exact_hash"
                hit["_confidence"] = 1.0
                self._attach_rag_priors([hit])
                return [hit]

        # --- 2. FAISS hybrid semantic search ---
        try:
            vs = self._get_vector_store()
            if len(vs) > 0:
                img_emb = None
                if query_image is not None:
                    img_emb = self._compute_image_embedding_from_array(query_image)
                elif image_path and Path(image_path).exists():
                    img_emb = self._compute_image_embedding(image_path)

                txt_emb = self._compute_text_embedding(raw_vlm_text)

                if img_emb is not None or txt_emb is not None:
                    hits = vs.search(
                        image_embedding=img_emb,
                        text_embedding=txt_emb,
                        top_k=top_k,
                    )
                    if hits:
                        return self._hits_to_results(hits)
        except Exception as e:
            print(f"Warning: FAISS search failed, falling back to keyword: {e}")

        # --- 3. Jaccard keyword fallback ---
        return self._keyword_fallback(current_features, raw_vlm_text, top_k)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _hits_to_results(
        self, hits: List[tuple]
    ) -> List[Dict[str, Any]]:
        """Convert FAISS (entry_id, score) hits to annotated entry dicts.

        Results with combined score below ``MIN_SIMILARITY`` are discarded.
        """
        id_map = {e["id"]: e for e in self.db}
        results: List[Dict[str, Any]] = []
        for entry_id, score in hits:
            if score < self.MIN_SIMILARITY:
                continue
            entry = id_map.get(entry_id)
            if entry is None:
                continue
            annotated = dict(entry)
            annotated["_match_type"] = "semantic"
            annotated["_confidence"] = round(float(score), 3)
            results.append(annotated)
        self._attach_rag_priors(results)
        return results

    def _keyword_fallback(
        self,
        current_features: Dict[str, Any],
        raw_vlm_text: str,
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """Original Jaccard + legacy JSON fallback retrieval."""
        scored_entries: List[tuple] = []

        if raw_vlm_text.strip():
            query_tokens = set(
                w.lower() for w in re.findall(r'[A-Za-z]{4,}', raw_vlm_text)
            )
            for entry in self.db:
                db_vlm = (
                    entry.get("features", {}).get("raw_vlm_description", "")
                    or entry.get("reasoning", "")
                )
                if not db_vlm:
                    continue
                db_tokens = set(
                    w.lower() for w in re.findall(r'[A-Za-z]{4,}', db_vlm)
                )
                if not db_tokens:
                    continue
                overlap = len(query_tokens & db_tokens)
                union = len(query_tokens | db_tokens)
                score = overlap / union if union else 0.0
                if score > 0:
                    annotated = dict(entry)
                    annotated["_match_type"] = "text_keyword"
                    annotated["_confidence"] = round(score, 3)
                    scored_entries.append((score, annotated))

        if not scored_entries:
            current_shape = current_features.get("shape_description", "")
            current_geo = set(
                current_features.get("detected_features", {}).get("geometry", [])
            )
            for entry in self.db:
                score = 0
                db_shape = entry.get("features", {}).get("shape_description", "")
                if current_shape and db_shape:
                    if current_shape in db_shape or db_shape in current_shape:
                        score += 3
                db_geo = set(
                    entry.get("features", {}).get(
                        "detected_features", {}
                    ).get("geometry", [])
                )
                score += len(current_geo.intersection(db_geo))
                if score > 0:
                    annotated = dict(entry)
                    annotated["_match_type"] = "legacy_json"
                    annotated["_confidence"] = round(score / 10, 3)
                    scored_entries.append((float(score), annotated))

        scored_entries.sort(key=lambda x: x[0], reverse=True)
        # Apply MIN_SIMILARITY filter (consistent with FAISS path)
        results = [
            entry for score, entry in scored_entries[:top_k]
            if entry["_confidence"] >= self.MIN_SIMILARITY
        ]
        self._attach_rag_priors(results)
        return results

    @staticmethod
    def _attach_rag_priors(results: List[Dict[str, Any]]) -> None:
        """Attach geometry vocabulary anchors extracted from stored descriptions."""
        _vocab = [
            "Flat Plate", "Rectangular Base", "L-shaped Bracket", "U-shaped Channel",
            "Z-shaped Bracket", "Hat Channel", "Box",
            "Flange", "Rib", "Chamfer", "Fillet", "Gusset", "Louver", "Emboss",
            "Thru-hole", "Threaded hole", "Extruded hole", "Burring",
            "Countersink", "CSK", "Slotted hole", "Notch", "Cutout",
            "Weld symbol", "Surface finish mark",
        ]
        _vocab_lower = {v.lower(): v for v in _vocab}
        for res in results:
            ref_text = (
                res.get("features", {}).get("raw_vlm_description", "")
                or res.get("reasoning", "")
            )
            found: List[str] = []
            for lower, canonical in _vocab_lower.items():
                if lower in ref_text.lower() and canonical not in found:
                    found.append(canonical)
            res["rag_priors"] = found

    # ------------------------------------------------------------------
    # RAG effectiveness metrics
    # ------------------------------------------------------------------

    def compute_rag_metrics(
        self,
        v1_text: str,
        v2_text: str,
        hitl_text: str,
    ) -> Dict[str, Any]:
        """Compute RAG effectiveness by comparing VLM outputs to HITL correction.

        Args:
            v1_text: First-pass VLM output (before RAG).
            v2_text: Second-pass VLM output (after RAG refinement).
            hitl_text: Final human-corrected text.

        Returns:
            Dict with v1_distance, v2_distance, improvement_rate.
            Distances are 1 - cosine_similarity (lower = closer to HITL).
            improvement_rate > 0 means RAG helped.
        """
        if not hitl_text or not hitl_text.strip():
            return {}

        try:
            embedder = self._get_text_embedder()
            hitl_emb = embedder.encode(hitl_text)

            v1_dist = 1.0
            if v1_text and v1_text.strip():
                v1_emb = embedder.encode(v1_text)
                v1_sim = float(np.dot(v1_emb, hitl_emb))
                v1_dist = round(1.0 - v1_sim, 4)

            v2_dist = v1_dist
            if v2_text and v2_text.strip() and v2_text != v1_text:
                v2_emb = embedder.encode(v2_text)
                v2_sim = float(np.dot(v2_emb, hitl_emb))
                v2_dist = round(1.0 - v2_sim, 4)

            improvement = round((v1_dist - v2_dist) / v1_dist, 4) if v1_dist > 0 else 0.0

            return {
                "v1_distance": v1_dist,
                "v2_distance": v2_dist,
                "improvement_rate": improvement,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            print(f"Warning: RAG metrics computation failed: {e}")
            return {}

    def get_rag_metrics_history(self) -> list:
        """Return all entries that have rag_metrics, sorted by timestamp."""
        results = []
        for entry in self.db:
            m = entry.get("rag_metrics")
            if m and "v1_distance" in m:
                results.append({
                    "id": entry.get("id", ""),
                    "timestamp": m.get("timestamp", entry.get("timestamp", "")),
                    "v1_distance": m["v1_distance"],
                    "v2_distance": m["v2_distance"],
                    "improvement_rate": m["improvement_rate"],
                    "version_count": entry.get("version_count", 1),
                })
        results.sort(key=lambda x: x["timestamp"])
        return results

    # ------------------------------------------------------------------
    # Index rebuild (for migrating existing JSON entries to FAISS)
    # ------------------------------------------------------------------

    def rebuild_vector_index(self) -> int:
        """
        Rebuild FAISS index from all existing JSON entries.

        Use this once to migrate a pre-existing knowledge_db.json that
        was created before vector indexing was added.

        Returns:
            Number of entries indexed.
        """
        from app.knowledge.vector_store import DualVectorStore
        import faiss

        vs = DualVectorStore()
        # Reset indices
        vs._img_index = faiss.IndexFlatIP(vs.IMAGE_DIM)
        vs._txt_index = faiss.IndexFlatIP(vs.TEXT_DIM)
        vs._ids = []

        count = 0
        for entry in self.db:
            entry_id = entry.get("id", "")
            if not entry_id:
                continue

            # Image embedding
            img_emb = None
            img_path = entry.get("image_rel_path", "")
            if img_path and Path(img_path).exists():
                img_emb = self._compute_image_embedding(img_path)

            # Text embedding
            desc = (
                entry.get("features", {}).get("raw_vlm_description", "")
                or entry.get("reasoning", "")
            )
            txt_emb = self._compute_text_embedding(desc)

            vs.add(entry_id, image_embedding=img_emb, text_embedding=txt_emb)
            count += 1

        vs.save()
        self._vector_store = vs
        print(f"Rebuilt vector index: {count} entries indexed.")
        return count
