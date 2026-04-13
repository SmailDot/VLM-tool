"""
Shadow Testing — 影子測試模組

收集 VLM + ProcessBrain 推理結果與人工 ground truth 的差異，
自動累積進 RAG 知識庫，無需場域專家介入。

Usage::

    tester = ShadowTester()
    rec = tester.record(image_path, vlm_desc, inferences, ground_truth=["F01","C01"])
    print(rec.diff_missing, rec.diff_wrong)

    stats = tester.get_stats()
    n = tester.export_to_rag(kb_manager)
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional


@dataclass
class ShadowRecord:
    """單筆影子測試記錄。"""

    image_path: str
    vlm_description: str
    system_inferences: List[dict]         # ProcessBrain 的推理結果（ProcessInference.to_dict()）
    ground_truth_processes: List[str]     # 人工輸入的正確製程代碼，例如 ["F01", "C01"]
    diff_missing: List[str]               # ground truth 有但系統沒猜到的
    diff_wrong: List[str]                 # 系統猜了但 ground truth 沒有的
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ShadowTester:
    """
    影子測試管理器。

    - 存取 data/shadow_log.json 進行持久化
    - 提供統計報告（漏判率、誤判率、最常漏掉/誤判的製程）
    - 可一鍵匯出有 ground truth 的記錄至 RAG 知識庫
    """

    def __init__(self, shadow_log_path: str = "data/shadow_log.json") -> None:
        self.shadow_log_path = Path(shadow_log_path)
        self.shadow_log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log: List[Dict[str, Any]] = self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> List[Dict[str, Any]]:
        if not self.shadow_log_path.exists():
            return []
        try:
            with self.shadow_log_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: ShadowTester 無法載入 {self.shadow_log_path}: {e}")
            return []

    def _save(self) -> None:
        with self.shadow_log_path.open("w", encoding="utf-8") as f:
            json.dump(self._log, f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(
        self,
        image_path: str,
        vlm_desc: str,
        inferences: List[dict],
        ground_truth: List[str],
    ) -> ShadowRecord:
        """
        記錄一筆影子測試結果並寫入 shadow_log.json。

        Args:
            image_path:   圖片檔案路徑。
            vlm_desc:     VLM 描述文字。
            inferences:   ProcessBrain.infer() 的結果（List[ProcessInference.to_dict()]）。
            ground_truth: 人工輸入的正確製程代碼列表（例如 ["F01", "C01"]）。

        Returns:
            ShadowRecord（含 diff_missing、diff_wrong）。
        """
        gt_set = set(g.strip().upper() for g in ground_truth if g.strip())
        predicted_set = set(
            inf.get("process_id", "").strip().upper()
            for inf in inferences
            if inf.get("process_id", "").strip()
        )

        diff_missing = sorted(gt_set - predicted_set)
        diff_wrong   = sorted(predicted_set - gt_set)

        rec = ShadowRecord(
            image_path=image_path,
            vlm_description=vlm_desc,
            system_inferences=inferences,
            ground_truth_processes=list(gt_set),
            diff_missing=diff_missing,
            diff_wrong=diff_wrong,
        )

        self._log.append(rec.to_dict())
        self._save()
        return rec

    def get_stats(self) -> Dict[str, Any]:
        """
        回傳目前 shadow_log 的統計摘要。

        Returns::

            {
              "total_records": int,
              "avg_missing_rate": float,
              "avg_wrong_rate": float,
              "most_missed_processes": [("F01", 3), ...],
              "most_wrong_processes":  [("D01", 2), ...],
            }
        """
        if not self._log:
            return {
                "total_records": 0,
                "avg_missing_rate": 0.0,
                "avg_wrong_rate": 0.0,
                "most_missed_processes": [],
                "most_wrong_processes": [],
            }

        total = len(self._log)
        missing_rates: List[float] = []
        wrong_rates:   List[float] = []
        all_missing: List[str] = []
        all_wrong:   List[str] = []

        for rec in self._log:
            gt = rec.get("ground_truth_processes", [])
            predicted = [inf.get("process_id", "") for inf in rec.get("system_inferences", [])]
            dm = rec.get("diff_missing", [])
            dw = rec.get("diff_wrong", [])

            all_missing.extend(dm)
            all_wrong.extend(dw)

            # missing rate = 漏掉 / ground truth total
            if gt:
                missing_rates.append(len(dm) / len(gt))
            else:
                missing_rates.append(0.0)

            # wrong rate = 誤判 / predicted total
            if predicted:
                wrong_rates.append(len(dw) / len(predicted))
            else:
                wrong_rates.append(0.0)

        avg_miss = sum(missing_rates) / total if total > 0 else 0.0
        avg_wrong = sum(wrong_rates) / total if total > 0 else 0.0

        most_missed = Counter(all_missing).most_common(10)
        most_wrong  = Counter(all_wrong).most_common(10)

        return {
            "total_records": total,
            "avg_missing_rate": round(avg_miss, 4),
            "avg_wrong_rate": round(avg_wrong, 4),
            "most_missed_processes": most_missed,
            "most_wrong_processes": most_wrong,
        }

    def export_to_rag(self, kb_manager: Any) -> int:
        """
        將 shadow_log 裡有 ground_truth 的記錄寫入 KnowledgeBaseManager。

        每筆記錄須同時滿足：
        1. ground_truth_processes 非空
        2. image_path 對應檔案確實存在

        Args:
            kb_manager: KnowledgeBaseManager 實例。

        Returns:
            成功寫入的筆數。
        """
        from app.knowledge.manager import KnowledgeBaseManager  # noqa: F401 (type hint)

        count = 0
        for rec in self._log:
            gt = rec.get("ground_truth_processes", [])
            if not gt:
                continue

            img_path = rec.get("image_path", "")
            if not img_path or not Path(img_path).exists():
                continue

            vlm_desc = rec.get("vlm_description", "")
            reasoning = (
                f"[Shadow Test] ground_truth={gt}  "
                f"missing={rec.get('diff_missing', [])}  "
                f"wrong={rec.get('diff_wrong', [])}"
            )

            try:
                kb_manager.add_entry(
                    image_path=img_path,
                    features={"raw_vlm_description": vlm_desc},
                    correct_processes=gt,
                    reasoning=reasoning,
                    tags=["shadow_test"],
                )
                count += 1
            except Exception as e:
                print(f"Warning: export_to_rag skipped {img_path}: {e}")

        return count

    def format_stats_report(self) -> str:
        """產生易讀的中文統計報告字串（供 CLI --stats 輸出使用）。"""
        s = self.get_stats()
        lines = [
            f"總測試筆數：{s['total_records']}",
            f"平均漏判率：{s['avg_missing_rate'] * 100:.1f}%",
            f"平均誤判率：{s['avg_wrong_rate'] * 100:.1f}%",
        ]

        # 最常被漏掉
        if s["most_missed_processes"]:
            parts = "、".join(f"{pid}（{cnt}次）" for pid, cnt in s["most_missed_processes"][:5])
            lines.append(f"最常被漏掉：{parts}")
        else:
            lines.append("最常被漏掉：（無）")

        # 最常誤判
        if s["most_wrong_processes"]:
            parts = "、".join(f"{pid}（{cnt}次）" for pid, cnt in s["most_wrong_processes"][:5])
            lines.append(f"最常誤判：  {parts}")
        else:
            lines.append("最常誤判：  （無）")

        return "\n".join(lines)
