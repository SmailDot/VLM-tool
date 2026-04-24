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
import re
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
# Auto-discovery: scan test_jpg/ and group files into families
# ══════════════════════════════════════════════════════════════════════

_TJPG = _REPO_ROOT / "test_jpg"

_IMG_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff'}

# View-name tokens used to strip suffixes when grouping orphan images
_VIEW_TOKENS = [
    '人類未加註', '人類加註',
    '前視圖', '後視圖', '俯視圖', '府試圖', '仰視圖',
    '側視圖', '左側視圖', '右側視圖', '立體圖', '等角圖', '測試圖',
    'FRONT', 'BACK', 'LEFT', 'RIGHT', 'TOP', 'BOTTOM', 'SIDE', 'ISO',
]


def _pdf_to_family_id(stem: str) -> str:
    """Extract family ID from a PDF stem by stripping annotation suffixes."""
    # Handles: -人類未加註  _人類加註  -人類加註  etc.
    cleaned = re.sub(r'[-_ ]+人類[未]?加註$', '', stem).strip()
    return cleaned if cleaned else stem


def _strip_view_suffix(stem: str) -> str:
    """Strip trailing view-name tokens to get a candidate family ID for orphan images."""
    # .pdf.jpg files — remove the embedded .pdf
    if stem.lower().endswith('.pdf'):
        stem = stem[:-4]
    for token in sorted(_VIEW_TOKENS, key=len, reverse=True):
        cleaned = re.sub(rf'[-_ ]+{re.escape(token)}.*$', '', stem,
                         flags=re.IGNORECASE).strip()
        if cleaned and cleaned != stem:
            return cleaned
    return stem


def _discover_families(folder: Path) -> dict[str, dict]:
    """
    Scan *folder* and build a family dict automatically.

    Rules:
    - Every PDF whose stem contains 人類未加註 / 人類加註 → defines a family ID
    - PDFs without that annotation → family ID = full stem (bare PDFs are parents too)
    - Image files are assigned to the family whose ID is the longest prefix of the filename
    - Orphan images (no matching PDF) are grouped by stripping view-name tokens
    - Within a family, 未加註 PDF is preferred as the parent over 加註
    """
    if not folder.exists():
        return {}

    families: dict[str, dict] = {}

    # ── Pass 1: PDFs define family IDs ──────────────────────────────
    for pdf in sorted(folder.glob("*.pdf")):
        fid = _pdf_to_family_id(pdf.stem)
        if not fid:
            continue
        if fid not in families:
            families[fid] = {"children": [], "parent": None}
        current = families[fid]["parent"]
        # Prefer 未加註 (unannotated) as parent
        if current is None or ("未加註" in pdf.stem and "未加註" not in current.stem):
            families[fid]["parent"] = pdf

    # ── Pass 2: assign images to families by longest-prefix match ───
    # Sort family IDs longest-first to avoid a short ID stealing files
    # that belong to a longer ID (e.g. "ABC" vs "ABC-extra")
    fids_by_len = sorted(families, key=len, reverse=True)

    unmatched: list[Path] = []
    for img in sorted(p for p in folder.iterdir()
                      if p.is_file() and p.suffix.lower() in _IMG_EXTS):
        img_lower = img.name.lower()
        matched = False
        for fid in fids_by_len:
            if img_lower.startswith(fid.lower()):
                families[fid]["children"].append(img)
                matched = True
                break
        if not matched:
            unmatched.append(img)

    # ── Pass 3: group orphan images (no parent PDF found) ───────────
    orphan_groups: dict[str, list[Path]] = {}
    for img in unmatched:
        candidate = _strip_view_suffix(img.stem)
        orphan_groups.setdefault(candidate, []).append(img)

    for fid, imgs in orphan_groups.items():
        if fid not in families:
            families[fid] = {"children": imgs, "parent": None}
        else:
            families[fid]["children"].extend(imgs)

    return families


# ── Manual overrides (only needed for edge cases auto-discovery can't handle) ──
# Add entries here to override or supplement auto-discovery for specific families.
# Example:
#   _OVERRIDES: dict[str, dict] = {
#       "MY-PART-001": {
#           "children": [_TJPG / "MY-PART-001-front.jpg"],
#           "parent":   _TJPG / "MY-PART-001.pdf",
#       },
#   }
_OVERRIDES: dict[str, dict] = {}

# FAMILIES = auto-discovery (covers every file in test_jpg/) + manual overrides
FAMILIES: dict[str, dict] = {**_discover_families(_TJPG), **_OVERRIDES}


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
    lines.append("▌ Step 2｜4 Agents 分類輸出")
    lines.append("─" * 60)
    for agent_name, agent_out in result["step2"].items():
        lines.append(f"  【{agent_name}】")
        lines.append(f"  {agent_out}")
        lines.append("")

    # ── Step 3 (disabled) ──
    lines.append("")
    lines.append("▌ Step 3｜（已停用 — 彙整由團隊外部處理）")
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
        help="Skip parent PDF image — send child images only.",
    )
    parser.add_argument(
        "--parent-only", action="store_true",
        help="Send parent PDF image only — skip all child images.",
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
    print(f"[MVP] Running {len(selected)} families × 5 VLM calls each (1+4, Step 3 disabled).")
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

        # Load parent
        parent_img = None
        if not args.no_parent and fam.get("parent"):
            parent_img = _load_parent_pdf(fam["parent"])

        # --parent-only: skip children, require parent
        if args.parent_only:
            if parent_img is None:
                print(f"  [SKIP] --parent-only set but no parent available for {family_id}")
                continue
            child_paths = []
            print(f"  [RUN] parent-only mode — sending parent image only")
        else:
            if not child_paths:
                print(f"  [SKIP] No valid child images for {family_id}")
                continue

        # Run pipeline
        result = pipeline.run(
            child_images=child_paths,
            parent_image=parent_img,
        )

        # Determine image mode label
        if args.parent_only:
            mode_label = "parent-only"
        elif args.no_parent:
            mode_label = "child-only"
        else:
            mode_label = "full"

        # Per-family header
        fam_header = (
            f"MVP Multi-Agent VLM Pipeline — {ts}\n"
            f"Model: {actual_model}\n"
            f"Family: {family_id}  |  Calls: 5 (1+4, Step3 disabled)  |  Mode: {mode_label}\n"
            f"Workers (Step 2): {args.workers}\n"
        )
        block = _fmt_result(family_id, result)

        # Sanitise family_id for use as a filename
        safe_id = family_id.replace("/", "_").replace(" ", "_").replace("\\", "_")
        out_path = output_dir / f"mvp_{safe_id}_{mode_label}_{ts}.txt"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(fam_header + "\n" + block)
        saved_files.append(out_path.name)
        print(f"  [MVP] Saved → {out_path.name}")

    print(f"\n[MVP] All done. {len(saved_files)} files saved:")
    for name in saved_files:
        print(f"  → {name}")


if __name__ == "__main__":
    main()
