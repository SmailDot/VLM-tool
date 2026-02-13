"""
Knowledge Base Manager for RAG cases.

Stores image features, corrected processes, and expert reasoning.
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import json
import shutil


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

    def add_entry(
        self,
        image_path: str,
        features: Dict[str, Any],
        correct_processes: List[str],
        reasoning: str,
        tags: Optional[List[str]] = None,
        additional_images: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Add a new knowledge entry to the database.

        Args:
            image_path: Path to source image file (primary image).
            features: Extracted features (VLM analysis output).
            correct_processes: Corrected process IDs.
            reasoning: Expert reasoning for correction.
            tags: Optional tags for retrieval.
            additional_images: Optional list of additional image paths to save.

        Returns:
            Dict[str, Any]: The created entry.
        """
        timestamp = datetime.now()
        filename = f"{timestamp.strftime('%Y%m%d_%H%M%S')}_{Path(image_path).name}"
        target_path = self.image_storage_dir / filename
        shutil.copy2(image_path, target_path)
        
        # Save additional images if provided
        additional_rel_paths = []
        if additional_images:
            for idx, img_path in enumerate(additional_images):
                if img_path != image_path:  # Skip primary image
                    additional_filename = f"{timestamp.strftime('%Y%m%d_%H%M%S')}_{idx}_{Path(img_path).name}"
                    additional_target = self.image_storage_dir / additional_filename
                    shutil.copy2(img_path, additional_target)
                    additional_rel_paths.append(str(additional_target))

        entry = {
            "id": filename.split(".")[0],
            "timestamp": timestamp.isoformat(),
            "image_rel_path": str(target_path),
            "additional_images": additional_rel_paths,  # NEW: Store additional images
            "features": features,
            "correct_processes": correct_processes,
            "reasoning": reasoning,
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
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Retrieve similar cases based on simple tag/shape matching.

        Args:
            current_features: Current VLM features.
            top_k: Number of cases to return.

        Returns:
            List[Dict[str, Any]]: Top matched entries.
        """
        scored_entries = []

        current_shape = current_features.get("shape_description", "")
        current_geo = set(current_features.get("detected_features", {}).get("geometry", []))

        for entry in self.db:
            score = 0

            db_shape = entry.get("features", {}).get("shape_description", "")
            if current_shape and db_shape:
                if current_shape in db_shape or db_shape in current_shape:
                    score += 3

            db_geo = set(entry.get("features", {}).get("detected_features", {}).get("geometry", []))
            overlap = len(current_geo.intersection(db_geo))
            score += overlap

            if score > 0:
                scored_entries.append((score, entry))

        scored_entries.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored_entries[:top_k]]
