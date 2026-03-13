"""Symbol matcher using multi-scale template matching.

Loads PNG templates from ``data/symbol_library/`` (supports transparent / alpha-channel
PNG masks so background colour is ignored) and scans a target engineering-drawing image
for each symbol via ``cv2.matchTemplate``.

製程辨識系統 - 可擴充符號庫 CV 掃描器 (Task2-Step1)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np


# Default location of the symbol library relative to the repository root.
_DEFAULT_LIB_DIR = Path(__file__).resolve().parents[2] / "data" / "symbol_library"

# Scale range for multi-scale matching (min_scale, max_scale, step).
_SCALE_MIN: float = 0.2
_SCALE_MAX: float = 1.0
_SCALE_STEP: float = 0.1

# Template-matching threshold (0–1).  Higher = more strict.
_DEFAULT_THRESHOLD: float = 0.70


class SymbolMatcher:
    """Multi-scale template matcher backed by an on-disk PNG symbol library.

    Args:
        library_dir: Directory containing ``.png`` symbol templates.
                     Defaults to ``data/symbol_library/`` at project root.
        threshold:   Minimum normalised cross-correlation score (0–1) for a
                     positive match.  Defaults to 0.70.

    Usage::

        matcher = SymbolMatcher()
        results = matcher.match_symbols(target_img)  # np.ndarray (BGR or grey)
        for r in results:
            print(r["name"], r["confidence"], r["location"])
    """

    def __init__(
        self,
        library_dir: Optional[Path | str] = None,
        threshold: float = _DEFAULT_THRESHOLD,
    ) -> None:
        self.library_dir: Path = Path(library_dir) if library_dir else _DEFAULT_LIB_DIR
        self.threshold: float = threshold
        self._templates: Dict[str, Dict[str, Any]] = {}  # name -> {img, mask}
        self._load_library()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reload(self) -> None:
        """Reload all templates from disk (call after adding new symbols)."""
        self._templates.clear()
        self._load_library()

    def match_symbols(
        self,
        target_img: np.ndarray,
        *,
        max_per_template: int = 5,
    ) -> List[Dict[str, Any]]:
        """Scan *target_img* for all loaded symbol templates.

        Args:
            target_img:        BGR or greyscale image as ``np.ndarray``.
            max_per_template:  Maximum number of matches returned per template.

        Returns:
            List of match dicts, each containing:
            - ``name``       (str)   template stem, e.g. ``"weld_symbol"``
            - ``confidence`` (float) best NCC score
            - ``location``   (tuple) ``(x, y, w, h)`` of best match in pixels
            - ``all_hits``   (list)  up to *max_per_template* ``{score, location}``

            Sorted by ``confidence`` descending.
        """
        if not self._templates:
            return []

        grey_target = _to_grey(target_img)
        results: List[Dict[str, Any]] = []

        for name, tpl in self._templates.items():
            hits = self._match_one(grey_target, tpl["img"], tpl.get("mask"), max_per_template)
            if hits:
                best = hits[0]
                results.append(
                    {
                        "name": name,
                        "confidence": float(best["score"]),
                        "location": best["location"],
                        "all_hits": hits,
                    }
                )

        results.sort(key=lambda r: r["confidence"], reverse=True)
        return results

    @property
    def symbol_names(self) -> List[str]:
        """Return list of currently loaded template names."""
        return list(self._templates.keys())

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_library(self) -> None:
        """Load all ``.png`` templates from *library_dir*."""
        if not self.library_dir.exists():
            return  # Library not yet populated — silently skip.

        for png_path in sorted(self.library_dir.glob("*.png")):
            name = png_path.stem
            img, mask = _load_template(png_path)
            if img is not None:
                self._templates[name] = {"img": img, "mask": mask}

    def _match_one(
        self,
        grey_target: np.ndarray,
        tpl_grey: np.ndarray,
        tpl_mask: Optional[np.ndarray],
        max_hits: int,
    ) -> List[Dict[str, Any]]:
        """Run multi-scale NCC matching for a single template.

        Returns list of hit dicts ``{score, location: (x, y, w, h)}``,
        sorted by score descending.
        """
        th, tw = tpl_grey.shape[:2]
        target_h, target_w = grey_target.shape[:2]

        best_hits: List[Dict[str, Any]] = []

        # Iterate scales
        scale = _SCALE_MIN
        while scale <= _SCALE_MAX + 1e-6:
            new_w = max(1, int(tw * scale))
            new_h = max(1, int(th * scale))

            # Skip if template is larger than target after resize
            if new_w >= target_w or new_h >= target_h:
                scale += _SCALE_STEP
                continue

            resized_tpl = cv2.resize(tpl_grey, (new_w, new_h), interpolation=cv2.INTER_AREA)
            resized_mask: Optional[np.ndarray] = None
            if tpl_mask is not None:
                resized_mask = cv2.resize(tpl_mask, (new_w, new_h), interpolation=cv2.INTER_AREA)

            # Template matching
            method = cv2.TM_CCOEFF_NORMED
            try:
                result_map = cv2.matchTemplate(grey_target, resized_tpl, method, mask=resized_mask)
            except cv2.error:
                scale += _SCALE_STEP
                continue

            # Collect all peaks above threshold
            loc_y, loc_x = np.where(result_map >= self.threshold)
            scores = result_map[loc_y, loc_x]
            for score, x, y in zip(scores.tolist(), loc_x.tolist(), loc_y.tolist()):
                best_hits.append(
                    {
                        "score": score,
                        "location": (int(x), int(y), new_w, new_h),
                    }
                )

            scale += _SCALE_STEP

        if not best_hits:
            return []

        # Deduplicate overlapping hits via greedy NMS
        best_hits.sort(key=lambda h: h["score"], reverse=True)
        deduped = _non_max_suppression(best_hits, iou_threshold=0.5)
        return deduped[:max_hits]


# ---------------------------------------------------------------------------
# Module-level utilities
# ---------------------------------------------------------------------------


def _load_template(png_path: Path) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """Load a PNG template, returning (grey_img, alpha_mask).

    If the image has an alpha channel (BGRA), the alpha is used as a mask so
    transparent regions do not contribute to the NCC score.

    Returns:
        (grey_img, mask) or (None, None) on failure.
    """
    try:
        raw = cv2.imread(str(png_path), cv2.IMREAD_UNCHANGED)
        if raw is None:
            return None, None

        if raw.ndim == 2:
            # Already greyscale
            return raw, None

        if raw.shape[2] == 4:
            # BGRA — split alpha as mask
            bgr = raw[:, :, :3]
            alpha = raw[:, :, 3]
            grey = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            # Mask: 255 where fully/mostly opaque, 0 where transparent or anti-aliased edge.
            # 使用 > 128 而非 > 0，避免去背工具產生的邊緣 anti-aliasing 半透明像素將奇數計入比對
            mask = np.where(alpha > 128, np.uint8(255), np.uint8(0))
            return grey, mask

        # BGR without alpha
        grey = cv2.cvtColor(raw, cv2.COLOR_BGR2GRAY)
        return grey, None

    except Exception:
        return None, None


def _to_grey(img: np.ndarray) -> np.ndarray:
    """Convert an image to single-channel greyscale if needed."""
    if img.ndim == 2:
        return img
    if img.shape[2] == 4:
        return cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2GRAY)
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def _iou(box_a: Tuple[int, int, int, int], box_b: Tuple[int, int, int, int]) -> float:
    """Compute Intersection-over-Union for two (x, y, w, h) boxes."""
    ax, ay, aw, ah = box_a
    bx, by, bw, bh = box_b

    ix1 = max(ax, bx)
    iy1 = max(ay, by)
    ix2 = min(ax + aw, bx + bw)
    iy2 = min(ay + ah, by + bh)

    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0

    inter = (ix2 - ix1) * (iy2 - iy1)
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def _non_max_suppression(
    hits: List[Dict[str, Any]],
    iou_threshold: float = 0.5,
) -> List[Dict[str, Any]]:
    """Greedy NMS: keep highest-score hit, suppress overlapping hits."""
    kept: List[Dict[str, Any]] = []
    for hit in hits:  # already sorted by score desc
        loc = hit["location"]
        if all(_iou(loc, k["location"]) < iou_threshold for k in kept):
            kept.append(hit)
    return kept
