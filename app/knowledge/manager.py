"""
Knowledge Base Manager for RAG cases.

Stores image features, corrected processes, and expert reasoning.
"""

from __future__ import annotations

import re as _re
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import json
import re
import shutil
import hashlib

class KnowledgeBaseManager:
    """
    Manage knowledge base entries for manufacturing process recognition.

    Each entry stores:
    - image copy (local storage)
    - extracted features (VLM analysis)
    - corrected process IDs
    - expert reasoning
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

    def _load_db(self) -> List[Dict[str, Any]]:
        """
        Load knowledge base data from disk.

        Returns:
            List[Dict[str, Any]]: Loaded entries, or empty list if missing/invalid.
        """
        if not self.db_path.exists():
            return []
        try:
            with self.db_path.open("r", encoding="utf-8") as file:
                return json.load(file)
        except Exception:
            return []

    def _save_db(self) -> None:
        """Persist the in-memory database to disk."""
        with self.db_path.open("w", encoding="utf-8") as file:
            json.dump(self.db, file, ensure_ascii=False, indent=2)

    def _calculate_hash(self, image_path: str) -> str:
        """
        計算圖片的 SHA-256 hash 作為唯一識別碼。

        Args:
            image_path: 圖片檔案路徑。

        Returns:
            str: 十六進位 SHA-256 hash 字串。
        """
        h = hashlib.sha256()
        with open(image_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def add_entry(
        self,
        image_path: str,
        features: Dict[str, Any],
        correct_processes: List[str],
        reasoning: str,
        tags: Optional[List[str]] = None,
        bom_context: str = ""
    ) -> Dict[str, Any]:
        """
        Add a new knowledge entry to the database.

        Args:
            image_path: Path to source image file.
            features: Extracted features (VLM analysis output).
            correct_processes: Corrected process IDs.
            reasoning: Expert reasoning for correction.
            tags: Optional tags for retrieval.
            bom_context: BOM / global notes text.

        Returns:
            Dict[str, Any]: The created entry.
        """
        timestamp = datetime.now()
        filename = f"{timestamp.strftime('%Y%m%d_%H%M%S')}_{Path(image_path).name}"
        target_path = self.image_storage_dir / filename
        if not Path(image_path).exists():
            raise FileNotFoundError(f"Source image not found: {image_path}")
        shutil.copy2(image_path, target_path)
        image_hash = self._calculate_hash(image_path)

        entry = {
            "id": filename.split(".")[0],
            "timestamp": timestamp.isoformat(),
            "image_rel_path": str(target_path),
            "image_hash": image_hash,
            "features": features,
            "correct_processes": correct_processes,
            "reasoning": reasoning,
            "bom_context": bom_context,
            "tags": tags or []
        }

        self.db.append(entry)
        self._save_db()
        return entry

    def update_entry(self, entry_id: str, new_data: Dict[str, Any]) -> bool:
        """
        Update an existing knowledge entry by ID.

        Args:
            entry_id: Entry identifier.
            new_data: Fields to update.

        Returns:
            bool: True if updated, False if not found.
        """
        for i, entry in enumerate(self.db):
            if entry.get("id") == entry_id:
                self.db[i].update(new_data)
                self.db[i]["updated_at"] = datetime.now().isoformat()
                self._save_db()
                return True
        return False

    def retrieve_similar(
        self,
        current_features: Dict[str, Any],
        image_path: str = "",
        top_k: int = 3,
        raw_vlm_text: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Retrieve similar cases from knowledge base.

        Matching priority:
        1. SHA-256 exact hash match (same file → score 1.0)
        2. Keyword overlap on raw_vlm_description plain text (Jaccard similarity)
        3. Legacy JSON shape/geometry fields (fallback for old entries)

        Args:
            current_features: Current extracted features dict.
            image_path: Path to current image (for hash match).
            top_k: Max number of results to return.
            raw_vlm_text: Raw VLM plain-text output for keyword matching.

        Returns:
            List[Dict[str, Any]]: Top matched entries, each annotated with
            '_match_type' and '_confidence' keys.
        """
        # --- 1. Hash exact match ---
        if image_path and Path(image_path).exists():
            query_hash = self._calculate_hash(image_path)
            for entry in self.db:
                if entry.get("image_hash") == query_hash:
                    hit = dict(entry)
                    hit["_match_type"] = "exact_hash"
                    hit["_confidence"] = 1.0
                    return [hit]

        scored_entries: List[tuple[float, Dict[str, Any]]] = []

        # --- 2. Keyword overlap on raw_vlm_description (primary) ---
        if raw_vlm_text.strip():
            # Extract meaningful tokens: lowercase alpha words, length >= 4
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

        # --- 3. Legacy JSON shape/geometry fallback ---
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
        results = [entry for _, entry in scored_entries[:top_k]]
        # Attach rag_priors to every result: geometry nouns extracted from
        # the stored raw_vlm_description (or reasoning) for use as VLM anchors.
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
        return results
        return [entry for _, entry in scored_entries[:top_k]]
