"""
view_metadata.py — 切圖後的 metadata 產生與儲存

功能：
  build_view_metadata  — 產生 metadata dict，供 VLM prompt 注入使用
  save_cropped_views   — 子圖 + metadata.json 一次寫入 output_dir
  record_view_correction — HITL 修正記錄寫入 knowledge_db.json
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import List, TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    from app.vision.drawing_cropper import CroppedView


# ── 主要 API ────────────────────────────────────────────────────────────────

def build_view_metadata(views: "List[CroppedView]", source_filename: str) -> dict:
    """
    產生 metadata.json 的內容，供 VLM prompt 注入使用。

    Args:
        views:           DrawingCropper.crop_views() 回傳的切圖清單
        source_filename: 原始工程圖檔名（用於記錄 source 欄位）

    Returns:
        可序列化為 JSON 的 dict
    """
    return {
        "source": source_filename,
        "total_views": len(views),
        "views": [
            {
                "index": i + 1,
                "label": v.view_label,
                "label_zh": v.view_label_zh,
                "role": "primary" if v.view_label in ("Top", "Front") else "supporting",
                "filename": v.suggested_filename,
                "confidence": round(v.confidence, 2),
                "bbox": list(v.bbox),
            }
            for i, v in enumerate(views)
        ],
    }


def save_cropped_views(
    views: "List[CroppedView]",
    output_dir: str,
    source_filename: str,
) -> str:
    """
    把子圖和 metadata.json 寫入 output_dir。

    Args:
        views:           DrawingCropper.crop_views() 回傳的切圖清單
        output_dir:      目標資料夾路徑（若不存在則自動建立）
        source_filename: 原始工程圖檔名

    Returns:
        metadata.json 的絕對路徑字串
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    for v in views:
        img_path = out / v.suggested_filename
        # cv2.imwrite 在 Windows 中文路徑下會靜默失敗，改用 imencode + tofile
        ok, buf = cv2.imencode(".png", v.image)
        if ok:
            buf.tofile(str(img_path))

    metadata = build_view_metadata(views, source_filename)
    meta_path = out / "metadata.json"
    meta_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(meta_path.resolve())


def record_view_correction(
    source_filename: str,
    original_label: str,
    corrected_label: str,
    bbox: tuple,
    db_path: str = "knowledge_db.json",
) -> None:
    """
    將 HITL 視角修正記錄寫入 knowledge_db.json 的 view_corrections 欄位。

    下次遇到 SHA-256 相同的圖面，DrawingCropper 可直接套用已修正的視角標籤。
    本函式由 Streamlit 前端呼叫；CLI 不處理此層。

    Args:
        source_filename:  原始工程圖檔名（用於顯示，不做 SHA-256 計算）
        original_label:   DrawingCropper 原本推斷的視角標籤
        corrected_label:  人工修正後的視角標籤
        bbox:             子圖在原圖的位置 (x, y, w, h)
        db_path:          knowledge_db.json 路徑（預設與 KnowledgeBaseManager 相同）
    """
    db_file = Path(db_path)
    if db_file.exists():
        with db_file.open(encoding="utf-8") as f:
            try:
                db: list = json.load(f)
            except json.JSONDecodeError:
                db = []
    else:
        db = []

    # 計算來源檔案的 SHA-256（以檔名為 key，若檔案不存在則跳過 hash）
    sha256 = _sha256_of_file(source_filename)

    record = {
        "source_filename": source_filename,
        "sha256": sha256,
        "original_label": original_label,
        "corrected_label": corrected_label,
        "bbox": list(bbox),
        "corrected_at": datetime.utcnow().isoformat() + "Z",
    }

    # 找或建立 view_corrections 區塊
    vc_entry = next(
        (e for e in db if isinstance(e, dict) and e.get("_type") == "view_corrections"),
        None,
    )
    if vc_entry is None:
        vc_entry = {"_type": "view_corrections", "corrections": []}
        db.append(vc_entry)

    vc_entry["corrections"].append(record)

    db_file.write_text(
        json.dumps(db, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ── 工具函式 ────────────────────────────────────────────────────────────────

def _sha256_of_file(file_path: str) -> str:
    """回傳檔案 SHA-256；若檔案不存在，回傳空字串。"""
    p = Path(file_path)
    if not p.exists():
        return ""
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_view_corrections(db_path: str = "knowledge_db.json") -> list:
    """
    載入 knowledge_db.json 中所有視角修正記錄。

    Returns:
        list of correction dicts（空列表表示無記錄或檔案不存在）
    """
    db_file = Path(db_path)
    if not db_file.exists():
        return []
    try:
        with db_file.open(encoding="utf-8") as f:
            db = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

    vc_entry = next(
        (e for e in db if isinstance(e, dict) and e.get("_type") == "view_corrections"),
        None,
    )
    return vc_entry["corrections"] if vc_entry else []
