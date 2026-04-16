"""
MVP Runner — runs the 3-step multi-agent pipeline on test_jpg families.

Usage:
    python -m mvp.run                         # all families
    python -m mvp.run --family 108-001416-13A  # single family
    python -m mvp.run --family 108-001416-13A 161-01757-00_A  # multiple
    python -m mvp.run --list                  # print available families

Output saved to: test_output/mvp_result_<timestamp>.txt
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

# Allow running as `python -m mvp.run` or `python mvp/run.py`
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.manufacturing.extractors.pdf_extractor import PDFImageExtractor
from mvp.pipeline import MVPPipeline

# ══════════════════════════════════════════════════════════════════════
# Family definitions
# Each family: list of child .jpg paths + optional parent .pdf path
# All paths relative to test_jpg/
# ══════════════════════════════════════════════════════════════════════

_TJPG = _REPO_ROOT / "test_jpg"

FAMILIES: dict[str, dict] = {
    "108-001416-13A": {
        "children": [
            _TJPG / "108-001416-13A-人類加註_FRONT.jpg",
            _TJPG / "108-001416-13A-人類加註_TOP.jpg",
            _TJPG / "108-001416-13A-人類加註_側視圖.jpg",
        ],
        "parent": _TJPG / "108-001416-13A-人類未加註.pdf",
    },
    "161-01489-00_A": {
        "children": [
            _TJPG / "161-01489-00_A-人類未加註_仰視圖.pdf.jpg",
            _TJPG / "161-01489-00_A-人類未加註_俯視圖.pdf.jpg",
            _TJPG / "161-01489-00_A-人類未加註_左側視圖.pdf.jpg",
            _TJPG / "161-01489-00_A-人類未加註_立體圖.pdf.jpg",
        ],
        "parent": _TJPG / "161-01489-00_A-人類未加註.pdf",
    },
    "161-01757-00_A": {
        "children": [
            _TJPG / "161-01757-00_A_前試圖.pdf.jpg",
            _TJPG / "161-01757-00_A_府試圖.pdf.jpg",
            _TJPG / "161-01757-00_A_側視圖.pdf.jpg",
            _TJPG / "161-01757-00_A_立體圖.pdf.jpg",
        ],
        "parent": _TJPG / "161-01757-00_A-人類未加註.pdf",
    },
    "5010-555691-13A": {
        "children": [
            _TJPG / "5010-555691-13A-前視圖.pdf.jpg",
            _TJPG / "5010-555691-13A-俯視圖.pdf.jpg",
            _TJPG / "5010-555691-13A-側視圖.pdf.jpg",
            _TJPG / "5010-555691-13A-立體圖.pdf.jpg",
        ],
        "parent": _TJPG / "5010-555691-13A-人類未加註.pdf",
    },
    "5010-586800-11A": {
        "children": [
            _TJPG / "5010-586800-11A-前試圖.pdf.jpg",
            _TJPG / "5010-586800-11A-俯視圖.pdf.jpg",
            _TJPG / "5010-586800-11A-測試圖.pdf.jpg",
            _TJPG / "5010-586800-11A-立體圖.pdf.jpg",
        ],
        "parent": _TJPG / "5010-586800-11A-人類未加註.pdf",
    },
    "F0050-00_耐震ブラケット": {
        "children": [
            _TJPG / "f0050-00_耐震ﾌﾞﾗｹｯﾄ 前視圖.pdf.jpg",
            _TJPG / "f0050-00_耐震ﾌﾞﾗｹｯﾄ 府試圖.pdf.jpg",
            _TJPG / "f0050-00_耐震ﾌﾞﾗｹｯﾄ 側視圖.pdf.jpg",
        ],
        "parent": _TJPG / "F0050-00_耐震ﾌﾞﾗｹｯﾄ-人類未加註.pdf",
    },
    "TSDH-230-3": {
        "children": [
            _TJPG / "tsDH-230-3-府試圖.jpg",
            _TJPG / "tsDH-230-3-測試圖.jpg",
            _TJPG / "tsDH-230-3-立體圖.jpg",
        ],
        "parent": _TJPG / "TSDH-230-3-人類未加註.pdf",
    },
}


# ══════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════

def _load_parent_pdf(pdf_path: Path):
    """Convert first page of a PDF to a numpy image array for the VLM."""
    if not pdf_path.exists():
        print(f"  [RUN] Parent PDF not found, skipping: {pdf_path.name}")
        return None
    try:
        extractor = PDFImageExtractor(target_dpi=200)
        img = extractor.extract_full_page(str(pdf_path), page_num=0)
        if img is None:
            print(f"  [RUN] PDF extraction returned None: {pdf_path.name}")
        return img
    except Exception as exc:
        print(f"  [RUN] PDF extraction error ({pdf_path.name}): {exc}")
        return None


def _validate_children(children: list[Path]) -> tuple[list[Path], list[str]]:
    """Return (existing_paths, missing_names)."""
    ok, missing = [], []
    for p in children:
        if p.exists():
            ok.append(p)
        else:
            missing.append(p.name)
    return ok, missing


def _fmt_result(family_id: str, result: dict) -> str:
    """Format one family's pipeline result into a text block."""
    lines = []
    sep = "═" * 72
    lines.append(sep)
    lines.append(f"零件 ID : {family_id}")
    lines.append(
        f"耗時   : Step1={result['elapsed_step1']}s  "
        f"Step2={result['elapsed_step2']}s  "
        f"Step3={result['elapsed_step3']}s"
    )
    if result.get("error"):
        lines.append(f"⚠️  錯誤: {result['error']}")
        lines.append(sep)
        return "\n".join(lines)

    # ── Step 1 ──
    lines.append("")
    lines.append("▌ Step 1｜視覺觀察描述")
    lines.append("─" * 60)
    lines.append(result["step1"] or "（無輸出）")

    # ── Step 2 ──
    lines.append("")
    lines.append("▌ Step 2｜8 Agents 分類輸出")
    lines.append("─" * 60)
    for agent_name, agent_out in result["step2"].items():
        lines.append(f"  【{agent_name}】")
        lines.append(f"  {agent_out}")
        lines.append("")

    # ── Step 3 ──
    lines.append("")
    lines.append("▌ Step 3｜最終製程彙整表")
    lines.append("─" * 60)
    lines.append(result["step3"] or "（無輸出）")
    lines.append(sep)
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(description="MVP Multi-Agent VLM Pipeline Runner")
    parser.add_argument(
        "--family", nargs="*",
        help="Family ID(s) to run. Omit for all families.",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List available family IDs and exit.",
    )
    parser.add_argument(
        "--workers", type=int, default=4,
        help="Parallel workers for Step 2 (default: 4).",
    )
    parser.add_argument(
        "--no-parent", action="store_true",
        help="Skip parent PDF image (faster, tests child-only performance).",
    )
    args = parser.parse_args()

    if args.list:
        print("Available families:")
        for fid in FAMILIES:
            print(f"  {fid}")
        return

    # Select families to run
    if args.family:
        selected = {}
        for fid in args.family:
            if fid not in FAMILIES:
                print(f"[ERROR] Unknown family: {fid}")
                print(f"        Available: {list(FAMILIES.keys())}")
                sys.exit(1)
            selected[fid] = FAMILIES[fid]
    else:
        selected = FAMILIES

    # Health check
    pipeline = MVPPipeline(max_workers=args.workers)
    if not pipeline.client.is_available():
        print("[ERROR] VLM service not available. Is LM Studio running?")
        sys.exit(1)

    # Query actual loaded model name from LM Studio (config default may differ)
    try:
        models_resp = pipeline.client.client.models.list()
        actual_model = models_resp.data[0].id if models_resp.data else pipeline.client.model
    except Exception:
        actual_model = pipeline.client.model

    print(f"[MVP] VLM service OK. Model: {actual_model}")
    print(f"[MVP] Running {len(selected)} families × 10 VLM calls each.")
    print(f"[MVP] Each family saved as its own txt in test_output/")

    output_dir = _REPO_ROOT / "test_output"
    output_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    saved_files = []

    for family_id, fam in selected.items():
        print(f"\n{'─'*60}")
        print(f"[MVP] === {family_id} ===")

        # Validate children
        child_paths, missing = _validate_children(fam["children"])
        if missing:
            print(f"  [WARN] Missing child images: {missing}")
        if not child_paths:
            print(f"  [SKIP] No valid child images for {family_id}")
            continue

        # Load parent
        parent_img = None
        if not args.no_parent and fam.get("parent"):
            parent_img = _load_parent_pdf(fam["parent"])

        # Run pipeline
        result = pipeline.run(
            child_images=child_paths,
            parent_image=parent_img,
        )

        # Per-family header
        fam_header = (
            f"MVP Multi-Agent VLM Pipeline — {ts}\n"
            f"Model: {actual_model}\n"
            f"Family: {family_id}  |  Calls: 10 (1+8+1)\n"
            f"Workers (Step 2): {args.workers}\n"
        )
        block = _fmt_result(family_id, result)

        # Sanitise family_id for use as a filename
        safe_id = family_id.replace("/", "_").replace(" ", "_").replace("\\", "_")
        out_path = output_dir / f"mvp_{safe_id}_{ts}.txt"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(fam_header + "\n" + block)
        saved_files.append(out_path.name)
        print(f"  [MVP] Saved → {out_path.name}")

    print(f"\n[MVP] All done. {len(saved_files)} files saved:")
    for name in saved_files:
        print(f"  → {name}")


if __name__ == "__main__":
    main()
