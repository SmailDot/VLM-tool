"""
DrawingCropper — 工程圖多視角自動切割模組

核心演算法移植自佳元的 DrawingCutter（drawing_cutter.py），
封裝為本專案的標準介面，不依賴 GUI / pdf2image / pytesseract。

視角識別採三層架構：
  Layer 1 (必)  — 象限位置規則推斷 (Top/Front/Side/Iso)
  Layer 2 (選)  — VLM 確認，加 --verify-views 才啟用
  Layer 3 (留)  — HITL 人工修正 + RAG 記憶 (Streamlit 前端實作)
"""

from __future__ import annotations

import base64
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np


# ── 資料結構 ────────────────────────────────────────────────────────────────

_LABEL_ZH: Dict[str, str] = {
    "Top": "俯視圖",
    "Front": "前視圖",
    "Side": "側視圖",
    "Iso": "等角視圖",
    "Unknown": "未知",
}

# 輸出排序順序
_VIEW_ORDER = ["Top", "Front", "Side", "Iso", "Unknown"]


@dataclass
class CroppedView:
    image: np.ndarray               # 切出的子圖（BGR）
    view_label: str                 # "Top" / "Front" / "Side" / "Iso" / "Unknown"
    view_label_zh: str              # "俯視圖" / "前視圖" / "側視圖" / "等角視圖" / "未知"
    confidence: float               # 視角判斷信心度 0.0–1.0
    bbox: Tuple[int, int, int, int] # 在原圖的位置 (x, y, w, h)
    suggested_filename: str         # 例如 "PART001-01_Top.png"


# ── 主類別 ──────────────────────────────────────────────────────────────────

class DrawingCropper:
    """
    工程圖多視角自動切割器。

    移植佳元的連通元件演算法，加上投影白帶偵測與位置規則視角分類。
    不依賴 GUI 視窗（cv2.imshow）、pdf2image、pytesseract。

    Args:
        min_view_area_ratio: 最小視圖面積比（佔整圖），低於此值的區塊被過濾。
    """

    def __init__(self, min_view_area_ratio: float = 0.05) -> None:
        self.min_view_area_ratio = min_view_area_ratio

    # ── 公開 API ─────────────────────────────────────────────────────────────

    def crop_from_file(
        self,
        image_path: str,
        prefix: str = "PART",
    ) -> List[CroppedView]:
        """從檔案路徑讀圖並切割（支援 JPG / PNG / PDF）。"""
        path = Path(image_path)
        if path.suffix.lower() == ".pdf":
            try:
                from app.manufacturing.extractors.pdf_extractor import PDFImageExtractor
                extractor = PDFImageExtractor(target_dpi=200)
                img = extractor.extract_full_page(str(path), page_num=0)
            except Exception as exc:
                raise ValueError(f"PDF 載入失敗: {exc}") from exc
        else:
            data = np.fromfile(str(path), dtype=np.uint8)
            img = cv2.imdecode(data, cv2.IMREAD_COLOR)
            if img is None:
                raise FileNotFoundError(f"無法載入圖片: {image_path}")
        return self.crop_views(img, prefix=prefix)

    def crop_views(
        self,
        image: np.ndarray,
        prefix: str = "PART",
    ) -> List[CroppedView]:
        """
        輸入完整工程圖（BGR ndarray），
        回傳切割後的視角清單，依慣例排序（Top → Front → Side → Iso）。
        """
        bboxes = self._detect_view_bboxes(image)
        if not bboxes:
            return []

        raw = self._classify_views_by_position(bboxes, image.shape)

        # 依 VIEW_ORDER 排序後編號命名
        order_map = {lbl: i for i, lbl in enumerate(_VIEW_ORDER)}
        raw.sort(key=lambda t: (order_map.get(t[1], 99), t[0][1], t[0][0]))

        result: List[CroppedView] = []
        for idx, (bbox, label, confidence) in enumerate(raw, 1):
            x, y, w, h = bbox
            crop = image[y : y + h, x : x + w].copy()
            filename = f"{prefix}-{idx:02d}_{label}.png"
            result.append(
                CroppedView(
                    image=crop,
                    view_label=label,
                    view_label_zh=_LABEL_ZH.get(label, "未知"),
                    confidence=confidence,
                    bbox=bbox,
                    suggested_filename=filename,
                )
            )
        return result

    def verify_views_with_vlm(self, views: List[CroppedView]) -> List[CroppedView]:
        """
        第二層：VLM 視角確認（選配）。

        對每張切出的子圖發送輕量 VLM 請求，要求回答
        Top / Front / Side / Iso / Unknown。

        - VLM 結果與 Layer 1 一致 → confidence 提升至 0.95
        - VLM 結果不一致 → 保留 VLM 標籤，confidence 設為 0.75
        - VLM 請求失敗 → 保留原結果不變
        """
        from app.config import VLM_BASE_URL, VLM_MODEL

        try:
            from openai import OpenAI
        except ImportError:
            return views

        PROMPT = (
            "This is one cropped view from a multi-view engineering drawing.\n"
            "Look at the projection lines, visible edges, and layout.\n"
            "Which standard orthographic view is this?\n"
            "Reply with ONLY one word: Top / Front / Side / Iso / Unknown"
        )
        VALID = {"Top", "Front", "Side", "Iso", "Unknown"}

        updated: List[CroppedView] = []
        for view in views:
            try:
                _, buf = cv2.imencode(".png", view.image)
                b64 = base64.b64encode(buf.tobytes()).decode()

                oai = OpenAI(
                    base_url=VLM_BASE_URL, api_key="not-needed",
                    timeout=30, max_retries=1,
                )
                resp = oai.chat.completions.create(
                    model=VLM_MODEL,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": PROMPT},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{b64}"
                                    },
                                },
                            ],
                        }
                    ],
                    temperature=0.0,
                    max_tokens=10,
                )
                raw_ans = (resp.choices[0].message.content or "").strip()
                vlm_label = raw_ans.capitalize() if raw_ans.capitalize() in VALID else "Unknown"

                if vlm_label == view.view_label:
                    new_conf = 0.95
                    new_label = view.view_label
                else:
                    new_conf = 0.75
                    new_label = vlm_label

                updated.append(
                    CroppedView(
                        image=view.image,
                        view_label=new_label,
                        view_label_zh=_LABEL_ZH.get(new_label, "未知"),
                        confidence=new_conf,
                        bbox=view.bbox,
                        suggested_filename=view.suggested_filename.replace(
                            f"_{view.view_label}.png", f"_{new_label}.png"
                        ),
                    )
                )
            except Exception:  # noqa: BLE001
                updated.append(view)

        return updated

    # ── 視圖偵測 ─────────────────────────────────────────────────────────────

    def _detect_view_bboxes(
        self, image: np.ndarray
    ) -> List[Tuple[int, int, int, int]]:
        """偵測視角區域的 bounding boxes。優先使用投影法，失敗則退回連通元件法。"""
        bboxes = self._projection_split(image)
        if len(bboxes) < 2:
            bboxes = self._component_split(image)

        img_area = image.shape[0] * image.shape[1]
        min_area = img_area * self.min_view_area_ratio
        return [b for b in bboxes if b[2] * b[3] >= min_area]

    def _projection_split(
        self, image: np.ndarray
    ) -> List[Tuple[int, int, int, int]]:
        """
        水平 / 垂直投影白帶偵測（移植概念：投影線 / 白邊 / 邊界）。

        將每行 / 每列的白色像素比例超過閾值（預設 96%）的連續帶視為分割線，
        用這些分割線把圖面切成矩形視圖區域。
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        h, w = gray.shape

        # 白底工程圖：> 200 視為白色
        _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)

        row_white = binary.mean(axis=1) / 255.0
        col_white = binary.mean(axis=0) / 255.0

        h_gaps = self._find_white_gaps(row_white, threshold=0.96, min_width=8)
        v_gaps = self._find_white_gaps(col_white, threshold=0.96, min_width=8)

        row_bounds = self._gaps_to_bounds(h_gaps, h)
        col_bounds = self._gaps_to_bounds(v_gaps, w)

        if len(row_bounds) < 2 or len(col_bounds) < 2:
            return []

        bboxes = []
        for r0, r1 in zip(row_bounds[:-1], row_bounds[1:]):
            for c0, c1 in zip(col_bounds[:-1], col_bounds[1:]):
                if (r1 - r0) > 0 and (c1 - c0) > 0:
                    bboxes.append((c0, r0, c1 - c0, r1 - r0))
        return bboxes

    def _find_white_gaps(
        self,
        ratio: np.ndarray,
        threshold: float,
        min_width: int,
    ) -> List[Tuple[int, int]]:
        """找連續白帶（ratio >= threshold），回傳 (start, end) 列表。"""
        is_white = ratio >= threshold
        gaps: List[Tuple[int, int]] = []
        in_gap = False
        start = 0
        for i, white in enumerate(is_white):
            if white and not in_gap:
                in_gap = True
                start = i
            elif not white and in_gap:
                in_gap = False
                if i - start >= min_width:
                    gaps.append((start, i))
        if in_gap and len(is_white) - start >= min_width:
            gaps.append((start, len(is_white)))
        return gaps

    def _gaps_to_bounds(
        self,
        gaps: List[Tuple[int, int]],
        total: int,
    ) -> List[int]:
        """把白帶列表轉為分割邊界（含 0 和 total）。"""
        bounds = {0, total}
        for start, end in gaps:
            bounds.add((start + end) // 2)
        return sorted(bounds)

    def _component_split(
        self, image: np.ndarray
    ) -> List[Tuple[int, int, int, int]]:
        """
        Fallback：連通元件切圖（移植自佳元的 detect_connected_components）。

        用大半徑膨脹把同一視圖的線條合併成一個連通塊，
        再用 connectedComponentsWithStats 找各視圖 bbox。
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        h, w = gray.shape
        img_area = h * w

        # Otsu 二值化（墨水 = 255）
        _, binary = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )

        # 大膨脹：讓同一視圖的線條連成一塊
        # line_distance 約為圖面最短邊的 3%，最小 20px
        line_distance = max(20, min(h, w) // 30)
        ksize = line_distance * 2 + 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ksize, ksize))
        dilated = cv2.dilate(binary, kernel, iterations=1)

        num_labels, _, stats, _ = cv2.connectedComponentsWithStats(
            dilated, connectivity=8
        )

        max_bbox_area = img_area * 0.90  # 排除幾乎等於全圖的邊框

        bboxes: List[Tuple[int, int, int, int]] = []
        for i in range(1, num_labels):
            x = stats[i, cv2.CC_STAT_LEFT]
            y = stats[i, cv2.CC_STAT_TOP]
            cw = stats[i, cv2.CC_STAT_WIDTH]
            ch = stats[i, cv2.CC_STAT_HEIGHT]
            bbox_area = cw * ch
            if bbox_area <= max_bbox_area:
                pad = 5
                bboxes.append((
                    max(0, x - pad),
                    max(0, y - pad),
                    min(cw + 2 * pad, w - max(0, x - pad)),
                    min(ch + 2 * pad, h - max(0, y - pad)),
                ))
        return bboxes

    # ── 視角分類（Layer 1）────────────────────────────────────────────────────

    def _classify_views_by_position(
        self,
        bboxes: List[Tuple[int, int, int, int]],
        image_shape: Tuple,
    ) -> List[Tuple[Tuple[int, int, int, int], str, float]]:
        """
        第一層：位置規則推斷視角標籤。

        以所有子圖中心點的中位數為原點，依象限分類：
          左上 → Top (confidence 0.85)
          左下 → Front
          右上 → Side
          右下 → Iso

        特殊處理：
          n=1 → Unknown 0.30
          n=2 → 上=Top, 下=Front (0.85)
          n=3 → 右側最大者=Iso (0.65), 其餘依位置 (0.75)
          n≥4 → 象限分類，重複標籤者降為 Unknown 0.30
        """
        n = len(bboxes)
        if n == 0:
            return []
        if n == 1:
            return [(bboxes[0], "Unknown", 0.30)]

        centers = [(x + w // 2, y + h // 2) for x, y, w, h in bboxes]
        cxs = [c[0] for c in centers]
        cys = [c[1] for c in centers]
        median_cx = float(np.median(cxs))
        median_cy = float(np.median(cys))

        if n == 2:
            indexed = sorted(range(2), key=lambda i: bboxes[i][1])  # sort by y
            labels = ["Top", "Front"]
            results = []
            for rank, orig_i in enumerate(indexed):
                results.append((bboxes[orig_i], labels[rank], 0.85))
            return results

        if n == 3:
            # 找右側最大者 → Iso
            right_ids = [i for i in range(3) if cxs[i] >= median_cx]
            if right_ids:
                iso_idx = max(right_ids, key=lambda i: bboxes[i][2] * bboxes[i][3])
            else:
                iso_idx = max(range(3), key=lambda i: bboxes[i][2] * bboxes[i][3])
            remaining = sorted(
                [i for i in range(3) if i != iso_idx],
                key=lambda i: cys[i],
            )
            label_map = {
                remaining[0]: ("Top", 0.75),
                remaining[1]: ("Front", 0.75),
                iso_idx: ("Iso", 0.65),
            }
            return [(bboxes[i], *label_map[i]) for i in range(3)]

        # n >= 4 — 象限分類
        quad_map = {
            (False, False): "Top",
            (False, True): "Front",
            (True, False): "Side",
            (True, True): "Iso",
        }
        raw: List[Tuple[Tuple, str, float]] = []
        for bbox, (cx, cy) in zip(bboxes, centers):
            is_right = cx >= median_cx
            is_lower = cy >= median_cy
            raw.append((bbox, quad_map[(is_right, is_lower)], 0.85))

        # 解決重複標籤：同標籤只保留最大面積，其餘降為 Unknown
        by_label: Dict[str, List[Tuple[int, Tuple, float]]] = defaultdict(list)
        for i, (bbox, label, conf) in enumerate(raw):
            by_label[label].append((i, bbox, conf))

        final = list(raw)
        for label, items in by_label.items():
            if len(items) > 1:
                keep_idx = max(items, key=lambda t: t[1][2] * t[1][3])[0]
                for i, bbox, _ in items:
                    if i != keep_idx:
                        final[i] = (bbox, "Unknown", 0.30)

        return final
