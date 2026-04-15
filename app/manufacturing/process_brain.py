"""
Process Brain — 製程推理層 (Process Reasoning Layer)

根據 VLM 描述文字與 BOM 備註，對每個製程逐一比對觸發關鍵詞，
輸出帶信心度與自然語言線索的推理結果。

設計原則：
- 純 keyword-matching，不依賴外部模型，離線可用
- 信心度來源透明：BOM 命中 0.9、VLM 命中 0.7、雙重命中 1.0
- RAG priors 最多補 +0.1，但不超過 1.0
- 僅回傳 confidence >= 0.5 的結果
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict, Any


@dataclass
class ProcessInference:
    """單一製程的推理結果。"""

    process_id: str          # e.g. "F01"
    process_name: str        # e.g. "焊接"
    confidence: float        # 0.0–1.0
    source: str              # "BOM" / "VLM" / "COMBINED"
    clues: List[str] = field(default_factory=list)  # 自然語言線索

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ProcessBrain:
    """
    製程推理大腦。

    載入 data/process_knowledge.json，對每個製程比對
    trigger_vlm（VLM 英文術語）與 trigger_bom（BOM 中日英文關鍵字），
    計算信心度並產生自然語言線索。

    Usage::

        brain = ProcessBrain()
        results = brain.infer(vlm_description, bom_facts, rag_priors)
        for r in results:
            print(r.process_id, r.confidence, r.clues)
    """

    DEFAULT_KNOWLEDGE_PATH = "data/process_knowledge.json"

    def __init__(self, knowledge_path: str = DEFAULT_KNOWLEDGE_PATH) -> None:
        kp = Path(knowledge_path)
        if not kp.exists():
            raise FileNotFoundError(
                f"ProcessBrain: 製程知識庫不存在 → {kp.resolve()}\n"
                "請確認 data/process_knowledge.json 已建立。"
            )
        with kp.open("r", encoding="utf-8") as f:
            self._knowledge: Dict[str, Dict[str, Any]] = json.load(f)
        if not self._knowledge:
            raise ValueError(
                "ProcessBrain: process_knowledge.json 是空的，請確認內容正確。"
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_negated_lines(text: str) -> str:
        """移除 VLM 輸出中明確否定某特徵的行。

        VLM 結構化輸出的第 2 節格式：
            - Weld symbol detected: False
            - Surface finish mark detected: False
        這類行包含關鍵詞，卻代表「沒有」，直接做 substring 搜尋會假陽性。
        將這些行去掉後，再讓剩餘文字參與 keyword matching。
        """
        keep = []
        for line in text.splitlines():
            lower_line = line.lower()
            # 過濾 "X detected: false / no" 的行（Weld symbol / Surface finish mark）
            if "detected: false" in lower_line or "detected: no" in lower_line:
                continue
            # 過濾 "Other text annotation found: False" 的行
            if "found: false" in lower_line or "found: no" in lower_line:
                continue
            keep.append(line)
        return "\n".join(keep)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def infer(
        self,
        vlm_description: str,
        bom_facts: str = "",
        rag_priors: List[str] = [],
    ) -> List[ProcessInference]:
        """
        根據 VLM 描述與 BOM 備註推理所有可能製程。

        Args:
            vlm_description: VLM 第二輪輸出的純文字幾何描述（英文）。
            bom_facts:        BOM / 父圖備註字串（中日英文皆可）。
            rag_priors:       RAG 從知識庫取回的製程名稱列表（字串）。

        Returns:
            信心度 >= 0.5 的推理結果列表，依信心度降序排列。
        """
        # 先移除否定行，再做 keyword matching，防止 "weld symbol detected: False" 假陽性
        vlm_active = self._strip_negated_lines(vlm_description)
        vlm_lower = vlm_active.lower()
        bom_lower = bom_facts.lower()

        # rag_priors 全轉小寫，方便後面比對
        rag_lower = [p.lower() for p in rag_priors]

        results: List[ProcessInference] = []

        for process_id, meta in self._knowledge.items():
            name: str = meta.get("name", "")
            triggers_vlm: List[str] = meta.get("trigger_vlm", [])
            triggers_bom: List[str] = meta.get("trigger_bom", [])

            # ── 比對 ─────────────────────────────────────────────────────
            hit_vlm_kws: List[str] = [kw for kw in triggers_vlm if kw.lower() in vlm_lower]
            hit_bom_kws: List[str] = [kw for kw in triggers_bom if kw.lower() in bom_lower]

            bom_hit = len(hit_bom_kws) > 0
            vlm_hit = len(hit_vlm_kws) > 0

            if not bom_hit and not vlm_hit:
                continue

            # ── 信心度計算 ────────────────────────────────────────────────
            if bom_hit and vlm_hit:
                base = 1.0
                source = "COMBINED"
            elif bom_hit:
                base = 0.9
                source = "BOM"
            else:
                base = 0.7
                source = "VLM"

            # RAG priors 補正：製程名稱或 process_id 出現在 rag_priors 中
            rag_bonus = 0.0
            if name.lower() in rag_lower or process_id.lower() in rag_lower:
                rag_bonus = 0.1

            confidence = min(1.0, base + rag_bonus)

            if confidence < 0.5:
                continue

            # ── 自然語言線索 ─────────────────────────────────────────────
            clues: List[str] = []
            if bom_hit:
                kw_str = "、".join(f"「{kw}」" for kw in hit_bom_kws[:3])
                clues.append(f"因為 BOM 標註了{kw_str}，判斷需要{name}製程。")
            if vlm_hit:
                kw_str = "、".join(hit_vlm_kws[:3])
                clues.append(f"因為 VLM 看到了 {kw_str}，推斷需要{name}製程。")

            results.append(
                ProcessInference(
                    process_id=process_id,
                    process_name=name,
                    confidence=round(confidence, 2),
                    source=source,
                    clues=clues,
                )
            )

        results.sort(key=lambda x: x.confidence, reverse=True)
        return results
