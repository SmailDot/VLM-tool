"""Upload and preprocessing flow helpers for the Streamlit app."""

import tempfile
from pathlib import Path
from typing import Any, Iterable, List, Optional, Sequence, Tuple

import cv2
import numpy as np

from ..manufacturing.extractors.ocr import OCRExtractor


ImageArray = np.ndarray


def decode_bom_uploads(uploaded_files: Optional[Iterable[Any]]) -> List[ImageArray]:
    """Decode uploaded BOM images into BGR arrays."""
    bom_imgs: List[ImageArray] = []
    for bf in (uploaded_files or []):
        raw = np.asarray(bytearray(bf.read()), dtype=np.uint8)
        img = cv2.imdecode(raw, cv2.IMREAD_COLOR)
        if img is not None:
            bom_imgs.append(img)
    return bom_imgs


def scan_ocr_text(targets: Sequence[ImageArray]) -> Tuple[str, int]:
    """Run OCR on multiple pages and return joined text with region count."""
    ocr = OCRExtractor()
    all_texts: List[str] = []
    total_regions = 0
    for page_idx, target_img in enumerate(targets):
        page_results = ocr.extract(target_img)
        if page_results:
            total_regions += len(page_results)
            if len(targets) > 1:
                all_texts.append(f"--- 第 {page_idx + 1} 頁 ---")
            all_texts.extend([r.text for r in page_results if r.text.strip()])
    return "\n".join(all_texts), total_regions


def decode_child_views(
    view_files: Sequence[Any],
    view_labels: Sequence[str],
) -> Tuple[List[ImageArray], List[str], List[str]]:
    """Decode uploaded child view files and return images, preview names, and short labels."""
    drawing_images: List[ImageArray] = []
    drawing_names: List[str] = []
    uploaded_labels: List[str] = []

    for uf, lbl in zip(view_files, view_labels):
        if uf is None:
            continue
        file_bytes = np.asarray(bytearray(uf.read()), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        if img is not None:
            drawing_images.append(img)
            drawing_names.append(f"{lbl}: {uf.name}")
            uploaded_labels.append(lbl.split('（')[0].strip())

    return drawing_images, drawing_names, uploaded_labels


def build_collage_or_single(drawing_images: Sequence[ImageArray]) -> ImageArray:
    """Build 2x2 collage for multi-view uploads, or return first image."""
    if not drawing_images:
        raise ValueError("drawing_images must not be empty")

    views = list(drawing_images)
    if len(views) == 1:
        return views[0]

    max_h = max(v.shape[0] for v in views)
    max_w = max(v.shape[1] for v in views)

    def pad_view(v: ImageArray) -> ImageArray:
        canvas = np.zeros((max_h, max_w, 3), dtype=np.uint8)
        canvas[: v.shape[0], : v.shape[1]] = (
            v[:, :, :3] if v.shape[2] == 3 else cv2.cvtColor(v, cv2.COLOR_BGRA2BGR)
        )
        return canvas

    padded = [pad_view(v) for v in views[:4]]
    while len(padded) < 4:
        padded.append(np.zeros((max_h, max_w, 3), dtype=np.uint8))

    row1 = np.hstack(padded[:2])
    row2 = np.hstack(padded[2:4])
    return np.vstack([row1, row2])


def persist_temp_preview_image(image: ImageArray) -> str:
    """Persist preview image to temp file and return path."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_image:
        cv2.imwrite(tmp_image.name, image)
        return tmp_image.name
