"""
VLM 批次測試腳本 v3 — 7 零件 × 4 條件 = 28 次 VLM 呼叫
=========================================================
每個零件的所有子視圖（3~4 張）一次性一起送入 VLM，
模擬真實工程圖辨識情境（VLM 同時看 FRONT / TOP / SIDE / ISO）。

四個測試條件：
  Cond A — 無父圖 + 有BOM表內容
  Cond B — 無父圖 + 無BOM表內容
  Cond C — 有父圖（人類未加註）+ 有BOM表內容
  Cond D — 有父圖（人類未加註）+ 無BOM表內容

OCR（PaddleOCR）與符號辨識（SymbolMatcher）:
  對每個零件所有子視圖分別執行後彙整，四條件共用同一份結果。

結果存入 test_output/vlm_batch_result_<timestamp>.txt
每筆分析完成後立即 flush，中途中斷也有部分結果。
"""

from __future__ import annotations

import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

# ── 確保輸出 UTF-8 ────────────────────────────────────────────────────
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# ── BOM 資料（對應 test_jpg/BOM_System.txt） ──────────────────────────
BOM_DATA: Dict[str, str] = {
    "108-001416-13A": (
        "零件名稱 (Name)：SENS BKT PRE\n"
        "零件圖號 (Drawing No.)：108-001416 / 版本 (Rev.)：13A\n"
        "材質 (Material)：SPCC (冷軋鋼板)\n"
        "板厚 (Thickness)：t=2.3 mm\n"
        "表面處理 (Finish)：MF-Ni (無電解鎳 / 化學鎳)\n"
        "公差標準：JIS B0405 / 公差等級：m (中級)\n"
        "數量：6 / 設計單位：Hermes-Epitek (漢民微測)"
    ),
    "161-01489-00_A": (
        "零件名稱 (Name)：COVER, LIFT SYSTEM LOADLOCK, IBLAZAR\n"
        "零件圖號 (Drawing No.)：161-01489-00 / 版本 (Rev.)：A\n"
        "材質 (Material)：AL5052\n"
        "板厚 (Thickness)：2.0 mm\n"
        "表面處理 (Finish)：未特別指定（依加工表面粗糙度標準）\n"
        "公差標準：ASME Y 14.5 / 圖幅大小：A3\n"
        "備註：去除毛邊，最大R角或倒角0.12；清潔要求不得有灰塵油汙；"
        "需雷射/蝕刻/刻印方式標示零件編號與版本（字體高度4~6mm）；"
        "使用無塵室核可材料獨立包裝；設計單位：AIBT"
    ),
    "161-01757-00_A": (
        "零件名稱 (Name)：BRACKET_02, HV CABLE FIX\n"
        "零件圖號 (Drawing No.)：161-01757-00 / 版本 (Rev.)：A\n"
        "材質 (Material)：ALUM 5052-H32\n"
        "板厚 (Thickness)：1.5 mm\n"
        "表面處理 (Finish)：兩面打磨、絲向不拘、鋁洗淨\n"
        "公差標準：ASME Y14.5-1994 / 圖幅大小：A3\n"
        "備註：去除毛邊與尖銳處，折彎半徑取最小值；"
        "無油汙無污染交付，採獨立包裝（無塵布→PE袋→舒美布→緩衝材）；"
        "需5mm高字符標示料號與版次；外包裝貼AIBT標籤不可有供應商資訊；"
        "設計單位：AIBT"
    ),
    "5010-555691-13A": "",  # BOM_System.txt 無此圖號資料
    "5010-586800-11A": (
        "零件名稱 (Name)：BRACKET, VALVE\n"
        "零件圖號 (Drawing No.)：5010-586800-11 / 版本 (Rev.)：A\n"
        "材質 (Material)：SUS304 (不鏽鋼)\n"
        "板厚 (Thickness)：t=1.5 mm\n"
        "表面處理 (Finish)：無 (2B)\n"
        "公差等級：3 / 圖面比例 (Scale)：1:1 / 圖幅大小：A3 / 投影法：第三角法\n"
        "主要加工特徵：3個M3螺紋孔 (3-M3)；4個M4抽牙孔 (4-バーリング M4，凸點朝向背面 ウラに凸)\n"
        "加工備註：圖面標示FIBER，建議採光纖雷射切割；定義膜面與表面配置方向\n"
        "機密規範：包含TEL機密資訊，未經許可不得複製或披露；設計單位：TEL"
    ),
    "F0050-00_耐震ブラケット": "",  # BOM_System.txt 無此圖號資料
    "TSDH-230-3": (
        "零件名稱 (Name)：プレスアームホルダ (Press Arm Holder)\n"
        "零件圖號 (Drawing No.)：TSDH-230-3\n"
        "版本/變更 (Rev.)：2012.4.20（為了防止振動）\n"
        "材質 (Material)：SUS304 / 重量：29.04 g\n"
        "表面處理 (Finish)：不要（人類加註標示為2B）\n"
        "一般公差：1~10mm ±0.1；10~250mm ±0.2；250~500mm ±0.3\n"
        "圖面比例 (Scale)：1:1 / 投影法：三角法（第三角投影）/ 設計軟體：SolidWorks 2005\n"
        "數量：1個/台 / 設計單位：不二精機株式會社\n"
        "加工特徵：4個Φ4.5孔，從背面進行Φ6.5沉孔加工(皿取)\n"
        "外觀角處理：板厚1.6T以下R0.2，板厚2.0T以上R0.5\n"
        "安全要求：去除毛邊(バリ)以防止割傷\n"
        "加工方式：レーザー（雷射切割）"
    ),
}

# ── 測試案例定義 ──────────────────────────────────────────────────────
# 每個 family 代表一個零件（工程圖），children 是該零件的所有子視圖（3~4張）
# 送 VLM 時一次送入全部子視圖，讓模型同時看所有視角
BASE = Path("test_jpg")

FAMILIES = [
    {
        "id": "108-001416-13A",
        "children": [
            ("FRONT",  BASE / "108-001416-13A-人類加註_FRONT.jpg"),
            ("TOP",    BASE / "108-001416-13A-人類加註_TOP.jpg"),
            ("側視圖", BASE / "108-001416-13A-人類加註_側視圖.jpg"),
        ],
        "parent_unann": BASE / "108-001416-13A-人類未加註.pdf",
    },
    {
        "id": "161-01489-00_A",
        "children": [
            ("仰視圖",  BASE / "161-01489-00_A-人類未加註_仰視圖.pdf.jpg"),
            ("俯視圖",  BASE / "161-01489-00_A-人類未加註_俯視圖.pdf.jpg"),
            ("左側視圖", BASE / "161-01489-00_A-人類未加註_左側視圖.pdf.jpg"),
            ("立體圖",  BASE / "161-01489-00_A-人類未加註_立體圖.pdf.jpg"),
        ],
        "parent_unann": BASE / "161-01489-00_A-人類未加註.pdf",
    },
    {
        "id": "161-01757-00_A",
        "children": [
            ("前視圖", BASE / "161-01757-00_A_前試圖.pdf.jpg"),
            ("俯視圖", BASE / "161-01757-00_A_府試圖.pdf.jpg"),
            ("側視圖", BASE / "161-01757-00_A_側視圖.pdf.jpg"),
            ("立體圖", BASE / "161-01757-00_A_立體圖.pdf.jpg"),
        ],
        "parent_unann": BASE / "161-01757-00_A-人類未加註.pdf",
    },
    {
        "id": "5010-555691-13A",
        "children": [
            ("前視圖", BASE / "5010-555691-13A-前視圖.pdf.jpg"),
            ("俯視圖", BASE / "5010-555691-13A-俯視圖.pdf.jpg"),
            ("側視圖", BASE / "5010-555691-13A-側視圖.pdf.jpg"),
            ("立體圖", BASE / "5010-555691-13A-立體圖.pdf.jpg"),
        ],
        "parent_unann": BASE / "5010-555691-13A-人類未加註.pdf",
    },
    {
        "id": "5010-586800-11A",
        "children": [
            ("前視圖", BASE / "5010-586800-11A-前試圖.pdf.jpg"),
            ("俯視圖", BASE / "5010-586800-11A-俯視圖.pdf.jpg"),
            ("測視圖", BASE / "5010-586800-11A-測試圖.pdf.jpg"),
            ("立體圖", BASE / "5010-586800-11A-立體圖.pdf.jpg"),
        ],
        "parent_unann": BASE / "5010-586800-11A-人類未加註.pdf",
    },
    {
        "id": "F0050-00_耐震ブラケット",
        "children": [
            ("前視圖", BASE / "f0050-00_耐震ﾌﾞﾗｹｯﾄ 前視圖.pdf.jpg"),
            ("俯視圖", BASE / "f0050-00_耐震ﾌﾞﾗｹｯﾄ 府試圖.pdf.jpg"),
            ("側視圖", BASE / "f0050-00_耐震ﾌﾞﾗｹｯﾄ 側視圖.pdf.jpg"),
        ],
        "parent_unann": BASE / "F0050-00_耐震ﾌﾞﾗｹｯﾄ-人類未加註.pdf",
    },
    {
        "id": "TSDH-230-3",
        "children": [
            ("前視圖", BASE / "tsDH-230-3-測試圖.jpg"),
            ("俯視圖", BASE / "tsDH-230-3-府試圖.jpg"),
            ("立體圖", BASE / "tsDH-230-3-立體圖.jpg"),
        ],
        "parent_unann": BASE / "TSDH-230-3-人類未加註.pdf",
    },
]

# 四個測試條件：(條件名稱, use_parent, use_bom)
# 父圖一律使用「人類未加註」版本
CONDITIONS = [
    ("A_無父圖_有BOM",       False, True),
    ("B_無父圖_無BOM",       False, False),
    ("C_有父圖未加註_有BOM", True,  True),
    ("D_有父圖未加註_無BOM", True,  False),
]

# ── 輸出工具 ─────────────────────────────────────────────────────────
SEP1 = "═" * 72
SEP2 = "─" * 72


def fmt_section(title: str, content: str) -> str:
    lines = [f"■ {title}"]
    for line in content.splitlines():
        lines.append(f"  {line}")
    return "\n".join(lines)


def _load_img_safe(path: Path) -> Optional[np.ndarray]:
    """Unicode/中文路徑安全的圖片載入（Windows）。"""
    try:
        buf = np.fromfile(str(path), dtype=np.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        return img
    except Exception:
        return None


def fmt_result(
    family_id: str,
    view_labels: List[str],
    cond_name: str,
    bom_text: str,
    result,
    elapsed: float,
    direct_ocr: list,
    direct_syms: list,
) -> str:
    views_str = " + ".join(view_labels)
    blocks = [
        SEP1,
        f"[零件] {family_id}",
        f"[子視圖] {views_str}",
        f"[條件] {cond_name}",
        f"耗時: {elapsed:.1f}s",
        SEP2,
    ]

    # 注入的 BOM 內容
    if bom_text:
        bom_preview = bom_text[:350] + "..." if len(bom_text) > 350 else bom_text
        blocks.append(fmt_section("注入BOM內容", bom_preview))
    else:
        blocks.append(fmt_section("注入BOM內容", "(本次未注入)"))

    # VLM 描述
    desc = result.features.raw_vlm_description or "(無 — VLM 未返回結果)"
    blocks.append(fmt_section("VLM 描述 (最終版)", desc))

    # Section 4 — VLM 製程選擇
    sel = result.vlm_process_selection
    if sel:
        sel_lines = "\n".join(
            f"  [{s['process_id']}] {s['name']}: {s['evidence']}" for s in sel
        )
        blocks.append(fmt_section("VLM 製程選擇 (Section 4)", sel_lines))
    else:
        blocks.append(fmt_section("VLM 製程選擇 (Section 4)", "(無輸出)"))

    # ProcessBrain 推論
    infs = result.process_inferences
    if infs:
        inf_lines = "\n".join(
            f"  {i['process_id']} {i['process_name']:<12} {i['source']} {i['confidence']:.2f}"
            f"  → {i['clues'][0] if i['clues'] else ''}"
            for i in infs
        )
        blocks.append(fmt_section("ProcessBrain 推論", inf_lines))
    else:
        blocks.append(fmt_section("ProcessBrain 推論", "(無觸發)"))

    # 符號偵測 — 對所有子視圖執行後彙整，四條件共用
    if direct_syms:
        seen_syms: set = set()
        sym_lines = []
        for h in direct_syms:
            key = h["name"]
            if key not in seen_syms:
                seen_syms.add(key)
                sym_lines.append(f"  {h['name']}  conf={h['score']:.3f}")
        blocks.append(fmt_section(
            "符號偵測 (所有子視圖彙整，四條件共用)",
            "\n".join(sym_lines),
        ))
    else:
        blocks.append(fmt_section("符號偵測 (所有子視圖彙整，四條件共用)", "(無命中)"))

    # 父圖解析 BOM
    if result.parent_context:
        ctx = result.parent_context
        bom_info = (
            f"material={ctx.material or '-'}  "
            f"thickness={ctx.thickness or '-'}  "
            f"customer={ctx.customer or '-'}"
        )
        if ctx.triggered_processes:
            bom_info += f"\n  triggered_processes: {ctx.triggered_processes}"
        if hasattr(ctx, "important_notes") and ctx.important_notes:
            bom_info += f"\n  notes: {ctx.important_notes}"
        blocks.append(fmt_section("父圖解析 BOM", bom_info))
    else:
        blocks.append(fmt_section("父圖解析 BOM", "(無父圖)"))

    # 錯誤/警告
    issues = result.errors + result.warnings
    blocks.append(fmt_section("錯誤/警告", "\n".join(issues) if issues else "(無)"))

    return "\n".join(blocks) + "\n"


# ── 跨條件比較摘要（同一零件，四條件差異）─────────────────────────────
def fmt_comparison(family_id: str, view_labels: List[str], cond_results: dict) -> str:
    views_str = " + ".join(view_labels)
    lines = [
        SEP1,
        f"[比較] {family_id}  子視圖: {views_str}",
        SEP2,
    ]
    for cond_name, result in cond_results.items():
        if result is None:
            lines.append(f"  {cond_name}: ERROR")
            continue
        sel_ids = [s["process_id"] for s in result.vlm_process_selection]
        inf_ids = [i["process_id"] for i in result.process_inferences]
        lines.append(f"  {cond_name}:")
        lines.append(f"    VLM選擇:      {', '.join(sel_ids) if sel_ids else '(無)'}")
        lines.append(f"    ProcessBrain: {', '.join(inf_ids) if inf_ids else '(無)'}")
    return "\n".join(lines) + "\n"


# ── 主流程 ────────────────────────────────────────────────────────────
def main():
    from app.manufacturing.pipeline import ManufacturingPipeline
    from app.manufacturing.extractors.ocr import OCRExtractor
    from app.vision.symbol_matcher import SymbolMatcher

    output_dir = Path("test_output")
    output_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = output_dir / f"vlm_batch_result_{ts}.txt"

    # ── 初始化 Pipeline
    pipeline = ManufacturingPipeline(use_vlm=True, use_visual=False)

    # ── 初始化 OCR
    print("初始化 PaddleOCR...", flush=True)
    ocr_extractor = None
    try:
        ocr_extractor = OCRExtractor(lang="ch")
        print("  OCR 初始化完成", flush=True)
    except Exception as e:
        print(f"  OCR 初始化失敗（略過）: {e}", flush=True)

    # ── 初始化 SymbolMatcher
    print("初始化 SymbolMatcher...", flush=True)
    sym_matcher = None
    try:
        sym_matcher = SymbolMatcher()
        print(f"  符號模板: {sym_matcher.symbol_names}", flush=True)
    except Exception as e:
        print(f"  SymbolMatcher 初始化失敗（略過）: {e}", flush=True)

    total = len(FAMILIES) * len(CONDITIONS)  # 7 × 4 = 28
    done = 0

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("VLM 批次測試報告 v3\n")
        f.write(f"生成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"總測試數: {total}（7 零件 × 4 條件，每次 VLM 呼叫同時輸入該零件所有子視圖）\n")
        f.write("測試條件:\n")
        f.write("  A_無父圖_有BOM       — 無父圖 PDF，注入 BOM System 表內容\n")
        f.write("  B_無父圖_無BOM       — 無父圖 PDF，不注入 BOM\n")
        f.write("  C_有父圖未加註_有BOM — 有父圖 PDF（人類未加註），注入 BOM System 表內容\n")
        f.write("  D_有父圖未加註_無BOM — 有父圖 PDF（人類未加註），不注入 BOM\n")
        f.write("OCR/符號偵測: 對每個零件所有子視圖分別執行後彙整，四條件共用同一份結果\n")
        f.write("注意: 5010-555691-13A 與 F0050-00_耐震ブラケット 無BOM資料，有BOM條件等同無BOM\n")
        f.write(SEP1 + "\n\n")
        f.flush()

        comparisons = []

        for family in FAMILIES:
            fid = family["id"]
            family_bom = BOM_DATA.get(fid, "")
            bom_available = bool(family_bom.strip())

            # 子視圖路徑與標籤
            view_labels = [v for v, _ in family["children"]]
            child_paths = [p for _, p in family["children"]]

            # 父圖路徑
            parent_unann_path = family["parent_unann"]
            parent_unann_str = (
                str(parent_unann_path)
                if parent_unann_path.exists()
                else None
            )
            if not parent_unann_str:
                print(f"  ⚠ 父圖未加註不存在: {parent_unann_path}", flush=True)

            # ── 預先對所有子視圖執行 OCR + SymbolMatcher（四條件共用）──────
            direct_ocr: list = []
            direct_syms: list = []

            print(f"\n[零件] {fid}  子視圖: {' + '.join(view_labels)}", flush=True)
            print("  執行 OCR + 符號偵測...", flush=True)

            for view_name, child_path in family["children"]:
                child_img = _load_img_safe(child_path) if child_path.exists() else None
                if child_img is None:
                    print(f"  ⚠ 無法載入子圖: {child_path}", flush=True)
                    continue

                # OCR
                if ocr_extractor is not None:
                    try:
                        results = ocr_extractor.extract(child_img, confidence_threshold=0.5)
                        direct_ocr.extend(results)
                    except Exception as e:
                        print(f"    OCR 失敗 [{view_name}]: {e}", flush=True)

                # 符號偵測
                if sym_matcher is not None and sym_matcher.symbol_names:
                    try:
                        hits = sym_matcher.match_symbols(child_img)
                        direct_syms.extend(hits)
                    except Exception as e:
                        print(f"    SymbolMatcher 失敗 [{view_name}]: {e}", flush=True)

            ocr_count = len([o for o in direct_ocr if o.text.strip()])
            sym_count = len(direct_syms)
            print(f"  OCR 命中: {ocr_count} 筆  符號命中: {sym_count} 筆", flush=True)

            # ── 四條件依序執行 VLM ────────────────────────────────────────
            cond_results: dict = {}

            for cond_name, use_parent, use_bom in CONDITIONS:
                done += 1

                bom_context = family_bom if (use_bom and bom_available) else ""
                bom_status = (
                    "有BOM" if bom_context
                    else ("無BOM資料(等同無注入)" if use_bom else "無BOM")
                )

                parent_path = parent_unann_str if use_parent else None
                parent_status = (
                    "有父圖" if parent_path
                    else ("父圖不存在" if use_parent else "無父圖")
                )

                print(
                    f"  [{done}/{total}] {cond_name}  "
                    f"[{parent_status}] [{bom_status}] ...",
                    flush=True,
                )

                t0 = time.time()
                result = None
                try:
                    pipeline.reset_vlm_client()
                    result = pipeline.recognize(
                        image=str(child_paths[0]),          # 主視圖（第一張）
                        child_images=[str(p) for p in child_paths],  # 所有子視圖
                        view_labels=view_labels,
                        parent_image=parent_path,
                        use_rag=False,
                        bom_context=bom_context,
                    )
                    elapsed = time.time() - t0
                    block = fmt_result(
                        fid, view_labels, cond_name, bom_context,
                        result, elapsed, direct_ocr, direct_syms,
                    )
                    f.write(block + "\n")
                    f.flush()
                    sel_count = len(result.vlm_process_selection)
                    print(
                        f"    → done {elapsed:.1f}s | Section4={sel_count} processes",
                        flush=True,
                    )
                except Exception as e:
                    elapsed = time.time() - t0
                    err_msg = traceback.format_exc()
                    f.write(SEP1 + "\n")
                    f.write(f"[零件] {fid}  [條件] {cond_name}\n")
                    f.write(f"耗時: {elapsed:.1f}s\n")
                    f.write(f"■ ERROR\n  {err_msg}\n\n")
                    f.flush()
                    print(f"    → ERROR: {e}", flush=True)

                cond_results[cond_name] = result

            comparisons.append(fmt_comparison(fid, view_labels, cond_results))

        # 全部完成後寫比較區塊
        f.write("\n\n" + "═" * 72 + "\n")
        f.write("跨條件比較摘要（7 零件 × 4 條件）\n")
        f.write("═" * 72 + "\n\n")
        for cmp in comparisons:
            f.write(cmp + "\n")
        f.flush()

    print(f"\n完成！結果已存入: {out_path}", flush=True)


if __name__ == "__main__":
    main()
