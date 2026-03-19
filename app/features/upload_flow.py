"""Upload and preprocessing flow helpers.

Accepts generic inputs (bytes, Path, ndarray, or file-like objects)
so the module can be used outside of Streamlit.
"""

import tempfile
from pathlib import Path
from typing import Any, Iterable, List, Optional, Sequence, Tuple, Union

import cv2
import numpy as np

from ..manufacturing.extractors.ocr import OCRExtractor


ImageArray = np.ndarray

# Type alias for flexible image input
ImageInput = Union[bytes, str, Path, np.ndarray, Any]  # Any = file-like with .read()


def _to_bgr_array(source: ImageInput) -> Optional[ImageArray]:
    """Convert various image sources to a BGR numpy array.

    Supported inputs:
      - np.ndarray (returned as-is)
      - bytes / bytearray
      - str or Path (read from disk)
      - file-like object with .read() method (e.g. Streamlit UploadedFile)
    """
    if isinstance(source, np.ndarray):
        return source

    raw: Optional[bytes] = None

    if isinstance(source, (bytes, bytearray)):
        raw = bytes(source)
    elif isinstance(source, (str, Path)):
        path = Path(source)
        if path.exists():
            raw = path.read_bytes()
    elif hasattr(source, "read"):
        # file-like (Streamlit UploadedFile, io.BytesIO, open(..., 'rb'), etc.)
        raw = source.read()

    if raw is None:
        return None

    arr = np.asarray(bytearray(raw), dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def _get_name(source: ImageInput) -> str:
    """Best-effort filename extraction from various input types."""
    if isinstance(source, (str, Path)):
        return Path(source).name
    if hasattr(source, "name"):
        return source.name
    return "image"


def decode_bom_uploads(uploaded_files: Optional[Iterable[ImageInput]]) -> List[ImageArray]:
    """Decode uploaded BOM images into BGR arrays.

    Each element can be bytes, a file path, an ndarray, or a file-like object.
    """
    bom_imgs: List[ImageArray] = []
    for bf in (uploaded_files or []):
        img = _to_bgr_array(bf)
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
    view_files: Sequence[ImageInput],
    view_labels: Sequence[str],
) -> Tuple[List[ImageArray], List[str], List[str]]:
    """Decode uploaded child view files and return images, preview names, and short labels.

    Each element of *view_files* can be bytes, a file path, an ndarray,
    or a file-like object (e.g. Streamlit UploadedFile).
    """
    drawing_images: List[ImageArray] = []
    drawing_names: List[str] = []
    uploaded_labels: List[str] = []

    for uf, lbl in zip(view_files, view_labels):
        if uf is None:
            continue
        img = _to_bgr_array(uf)
        if img is not None:
            drawing_images.append(img)
            drawing_names.append(f"{lbl}: {_get_name(uf)}")
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
