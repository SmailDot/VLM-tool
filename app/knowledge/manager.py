"""
Knowledge Base Manager for RAG cases.

Stores image features, corrected processes, and expert reasoning.
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path
import json
import shutil
import os
import cv2
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
        # 確保使用絕對路徑，以專案根目錄為基準
        if not Path(db_path).is_absolute():
            # 找到專案根目錄（假設 manager.py 在 app/knowledge/ 下）
            project_root = Path(__file__).parent.parent.parent
            self.db_path = project_root / db_path
        else:
            self.db_path = Path(db_path)
        
        if not Path(image_storage_dir).is_absolute():
            project_root = Path(__file__).parent.parent.parent
            self.image_storage_dir = project_root / image_storage_dir
        else:
            self.image_storage_dir = Path(image_storage_dir)
        
        self.image_storage_dir.mkdir(parents=True, exist_ok=True)
        self.db: List[Dict[str, Any]] = self._load_db()
        
        # 啟動時自動清理無效條目
        self._cleanup_invalid_entries()
    
    def _cleanup_invalid_entries(self) -> int:
        """
        Remove entries with missing image files.
        
        Returns:
            int: Number of entries removed.
        """
        initial_count = len(self.db)
        valid_entries = []
        
        for entry in self.db:
            image_path = entry.get("image_rel_path")
            if image_path and Path(image_path).exists():
                valid_entries.append(entry)
            else:
                print(f"[Cleanup] Removing invalid entry: {entry.get('id', 'unknown')} (image not found: {image_path})")
        
        self.db = valid_entries
        removed = initial_count - len(self.db)
        
        if removed > 0:
            self._save_db()
            print(f"[Cleanup] Removed {removed} invalid entries from knowledge base")
        
        return removed
    
    def _compute_image_hash(self, image_path: str) -> str:
        """
        Compute perceptual hash of image using average hash algorithm.
        
        Args:
            image_path: Path to image file.
        
        Returns:
            str: 64-character hash string (empty if error).
        """
        try:
            img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
            if img is None:
                print(f"[Hash] Failed to load image: {image_path}")
                return ""
            
            # Resize to 8x8 for average hash
            img_resized = cv2.resize(img, (8, 8), interpolation=cv2.INTER_AREA)
            
            # Calculate average pixel value
            avg_val = img_resized.mean()
            
            # Generate binary hash (1 if pixel > avg, 0 otherwise)
            hash_bits = (img_resized > avg_val).astype(int).flatten()
            hash_binary = ''.join(map(str, hash_bits))
            
            # Convert to hex for compact storage
            if len(hash_binary) > 0:
                hash_int = int(hash_binary, 2)
                hash_hex = format(hash_int, '016x')  # 64-bit hex string
            else:
                hash_hex = "0" * 16
            
            return hash_hex
        
        except Exception as e:
            print(f"[Hash] Error computing hash for {image_path}: {e}")
            return ""

    def _hamming_distance(self, hash1: str, hash2: str) -> int:
        """
        Calculate Hamming distance between two hex hash strings.
        
        Args:
            hash1: First hash (hex string).
            hash2: Second hash (hex string).
        
        Returns:
            int: Hamming distance (number of differing bits), -1 if error.
        """
        if not hash1 or not hash2:
            return -1
        
        if len(hash1) != len(hash2):
            return -1
        
        try:
            # Convert hex to binary and count differing bits
            int1 = int(hash1, 16)
            int2 = int(hash2, 16)
            xor_result = int1 ^ int2
            
            # Count number of 1s in XOR result (differing bits)
            distance = bin(xor_result).count('1')
            return distance
        
        except Exception:
            return -1
    
    def _find_similar_images(self, image_hash: str, threshold: int = 5) -> List[Tuple[Dict[str, Any], int]]:
        """
        Find entries with similar image hashes.
        
        Args:
            image_hash: Hash of the query image.
            threshold: Maximum Hamming distance to consider similar (default: 5).
        
        Returns:
            List of tuples: (entry, hamming_distance), sorted by similarity (closest first).
        """
        if not image_hash:
            return []
        
        similar = []
        
        for entry in self.db:
            db_hash = entry.get("image_hash", "")
            if not db_hash:
                continue
            
            distance = self._hamming_distance(image_hash, db_hash)
            
            if distance >= 0 and distance <= threshold:
                similar.append((entry, distance))
        
        # Sort by distance (most similar first)
        similar.sort(key=lambda x: x[1])
        
        return similar

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
        similarity_threshold: int = 5
    ) -> Dict[str, Any]:
        """
        Add a new knowledge entry to the database with duplicate detection.

        Args:
            image_path: Path to source image file.
            features: Extracted features (VLM analysis output).
            correct_processes: Corrected process IDs.
            reasoning: Expert reasoning for correction.
            tags: Optional tags for retrieval.
            similarity_threshold: Max Hamming distance for duplicate detection (default: 5).

        Returns:
            Dict with:
            - status: "ok" | "duplicate_found"
            - entry: The created entry (if status="ok")
            - similar: List of similar entries (if status="duplicate_found")
        """
        # Compute image hash BEFORE copying
        image_hash = self._compute_image_hash(image_path)
        
        # Check for duplicates
        if image_hash:
            similar = self._find_similar_images(image_hash, threshold=similarity_threshold)
            
            if similar:
                # Found similar images, return for user decision
                return {
                    "status": "duplicate_found",
                    "similar": [
                        {
                            "entry": entry,
                            "distance": dist,
                            "similarity_percent": round((1 - dist / 64) * 100, 1)
                        }
                        for entry, dist in similar
                    ]
                }
        
        # No duplicates found, proceed with adding
        timestamp = datetime.now()
        filename = f"{timestamp.strftime('%Y%m%d_%H%M%S')}_{Path(image_path).name}"
        target_path = self.image_storage_dir / filename
        shutil.copy2(image_path, target_path)

        entry = {
            "id": filename.split(".")[0],
            "timestamp": timestamp.isoformat(),
            "image_rel_path": str(target_path),
            "image_hash": image_hash,
            "features": features,
            "correct_processes": correct_processes,
            "reasoning": reasoning,
            "tags": tags or []
        }

        self.db.append(entry)
        self._save_db()
        
        return {
            "status": "ok",
            "entry": entry
        }

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

    def delete_entry(self, entry_id: str) -> bool:
        """
        Delete a knowledge entry by ID and remove its image file if present.

        Args:
            entry_id: Entry identifier.

        Returns:
            bool: True if deleted, False if not found.
        """
        for i, entry in enumerate(self.db):
            if entry.get("id") == entry_id:
                image_path = entry.get("image_rel_path")
                if image_path and os.path.exists(image_path):
                    try:
                        os.remove(image_path)
                    except Exception:
                        pass
                del self.db[i]
                self._save_db()
                return True
        return False

    def retrieve_similar(
        self,
        current_features: Dict[str, Any],
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Retrieve similar cases based on geometry features and shape matching.

        Scoring strategy:
        - Geometry overlap: 5 points per matching feature (high priority)
        - Shape keyword match: 2 points (medium priority)
        - Shape full match: 1 point (low priority)

        Args:
            current_features: Current VLM features.
            top_k: Number of cases to return.

        Returns:
            List[Dict[str, Any]]: Top matched entries.
        """
        scored_entries = []

        current_shape = current_features.get("shape_description", "")
        current_geo = set(current_features.get("detected_features", {}).get("geometry", []))
        
        # 提取形狀描述中的關鍵字（用於寬鬆匹配）
        shape_keywords = self._extract_shape_keywords(current_shape)

        for entry in self.db:
            score = 0

            # 1. 幾何特徵重疊（最高權重：5 points/feature）
            db_geo = set(entry.get("features", {}).get("detected_features", {}).get("geometry", []))
            overlap = len(current_geo.intersection(db_geo))
            score += overlap * 5

            # 2. 形狀關鍵字匹配（中權重：2 points/keyword）
            db_shape = entry.get("features", {}).get("shape_description", "")
            if current_shape and db_shape:
                # 檢查關鍵字是否出現在資料庫的形狀描述中
                keyword_matches = sum(1 for kw in shape_keywords if kw in db_shape)
                score += keyword_matches * 2
                
                # 3. 完全字串包含匹配（低權重：1 point）
                if current_shape in db_shape or db_shape in current_shape:
                    score += 1

            if score > 0:
                scored_entries.append((score, entry))

        scored_entries.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored_entries[:top_k]]

    def _extract_shape_keywords(self, shape_desc: str) -> List[str]:
        """
        Extract key shape-related keywords from description.

        Args:
            shape_desc: Shape description string.

        Returns:
            List of extracted keywords.
        """
        if not shape_desc:
            return []
        
        # 定義常見的形狀關鍵字（中英文）
        common_keywords = [
            "L型", "L形", "U型", "U形", "Z型", "Z形",
            "板金", "板材", "薄板",
            "孔洞", "圓孔", "螺絲孔", "鑽孔",
            "折彎", "彎曲", "折角",
            "矩形", "方形", "圓形", "橢圓",
            "支架", "機箱", "外殼", "底座",
            "L-shaped", "U-shaped", "bracket",
            "sheet metal", "plate",
            "hole", "drill", "bore",
            "bend", "fold", "angle"
        ]
        
        # 提取出現在描述中的關鍵字
        keywords = [kw for kw in common_keywords if kw.lower() in shape_desc.lower()]
        return keywords
