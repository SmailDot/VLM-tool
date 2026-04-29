"""
MVP Runner — runs the 3-step multi-agent pipeline on drawing groups.

Usage:
    python -m mvp.run                                   # all groups in test_jpg/
    python -m mvp.run --group 108-001416-13A            # single group by ID
    python -m mvp.run --group A B                       # multiple groups
    python -m mvp.run --path /any/folder                # ad-hoc: scan a custom directory
    python -m mvp.run --path /any/file.pdf              # ad-hoc: single PDF (parent only)
    python -m mvp.run --path /any/image.jpg             # ad-hoc: single image (child only)
    python -m mvp.run --list                            # print available groups

Output saved to: test_output/mvp_<group>_<mode>_<timestamp>.txt

Modes:
    default       — parent + child views
    --parent-only — parent PDF page only
    --no-parent   — child views only
                    Fallback: if a group has only a parent PDF and no real child images,
                    the rendered PDF page is used as the lone child so the run still
                    proceeds.
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
# Auto-discovery: scan a folder and group files into groups
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


def _pdf_to_group_id(stem: str) -> str:
    """Extract group ID from a PDF stem by stripping annotation suffixes."""
    cleaned = re.sub(r'[-_ ]+人類[未]?加註$', '', stem).strip()
    return cleaned if cleaned else stem


def _strip_view_suffix(stem: str) -> str:
    """Strip trailing view-name tokens to get a candidate group ID for orphan images."""
    if stem.lower().endswith('.pdf'):
        stem = stem[:-4]
    for token in sorted(_VIEW_TOKENS, key=len, reverse=True):
        cleaned = re.sub(rf'[-_ ]+{re.escape(token)}.*$', '', stem,
                         flags=re.IGNORECASE).strip()
        if cleaned and cleaned != stem:
            return cleaned
    return stem


def _discover_groups(folder: Path) -> dict[str, dict]:
    """
    Scan *folder* and build a group dict automatically.

    Rules:
    - Every PDF whose stem contains 人類未加註 / 人類加註 → defines a group ID
    - PDFs without that annotation → group ID = full stem (bare PDFs are parents too)
    - Image files are assigned to the group whose ID is the longest prefix of the filename
    - Orphan images (no matching PDF) are grouped by stripping view-name tokens
    - Within a group, 未加註 PDF is preferred as the parent over 加註
    """
    if not folder.exists():
        return {}

    groups: dict[str, dict] = {}

    # ── Pass 1: PDFs define group IDs ───────────────────────────────
    for pdf in sorted(folder.glob("*.pdf")):
        gid = _pdf_to_group_id(pdf.stem)
        if not gid:
            continue
        if gid not in groups:
            groups[gid] = {"children": [], "parent": None}
        current = groups[gid]["parent"]
        if current is None or ("未加註" in pdf.stem and "未加註" not in current.stem):
            groups[gid]["parent"] = pdf

    # ── Pass 2: assign images to groups by longest-prefix match ─────
    gids_by_len = sorted(groups, key=len, reverse=True)

    unmatched: list[Path] = []
    for img in sorted(p for p in folder.iterdir()
                      if p.is_file() and p.suffix.lower() in _IMG_EXTS):
        img_lower = img.name.lower()
        matched = False
        for gid in gids_by_len:
            if img_lower.startswith(gid.lower()):
                groups[gid]["children"].append(img)
                matched = True
                break
        if not matched:
            unmatched.append(img)

    # ── Pass 3: group orphan images (no parent PDF found) ───────────
    orphan_groups: dict[str, list[Path]] = {}
    for img in unmatched:
        candidate = _strip_view_suffix(img.stem)
        orphan_groups.setdefault(candidate, []).append(img)

    for gid, imgs in orphan_groups.items():
        if gid not in groups:
            groups[gid] = {"children": imgs, "parent": None}
        else:
            groups[gid]["children"].extend(imgs)

    return groups


def _groups_from_path(path: Path) -> dict[str, dict]:
    """
    Build a groups dict from an arbitrary path:
      - Directory   → scan it like test_jpg/
      - Single PDF  → one group (PDF as parent, no children)
      - Single image → one group (image as the only child, no parent)
    """
    if not path.exists():
        print(f"[ERROR] Path not found: {path}")
        return {}

    if path.is_dir():
        return _discover_groups(path)

    if path.is_file():
        suffix = path.suffix.lower()
        gid = path.stem
        if suffix == ".pdf":
            return {gid: {"children": [], "parent": path}}
        if suffix in _IMG_EXTS:
            return {gid: {"children": [path], "parent": None}}

    print(f"[ERROR] Unsupported path: {path}")
    return {}


# ── Manual overrides (only for edge cases auto-discovery can't handle) ──
_OVERRIDES: dict[str, dict] = {}

# GROUPS = auto-discovery (covers every file in test_jpg/) + manual overrides
GROUPS: dict[str, dict] = {**_discover_groups(_TJPG), **_OVERRIDES}


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


def _fmt_result(group_id: str, result: dict) -> str:
    """Format one group's pipeline result into a text block."""
    lines = []
    sep = "═" * 72
    lines.append(sep)
    lines.append(f"零件 ID : {group_id}")
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
        "--group", nargs="*",
        help="Group ID(s) to run. Omit for all groups in the active source.",
    )
    parser.add_argument(
        "--path", type=str, default=None,
        help="Run on an arbitrary path (file or directory) instead of test_jpg/.",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List available group IDs and exit.",
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

    # Resolve the candidate group set
    if args.path:
        available = _groups_from_path(Path(args.path).expanduser().resolve())
        if not available:
            sys.exit(1)
    else:
        available = GROUPS

    if args.list:
        print("Available groups:")
        for gid in available:
            print(f"  {gid}")
        return

    # Select groups to run
    if args.group:
        selected = {}
        for gid in args.group:
            if gid not in available:
                print(f"[ERROR] Unknown group: {gid}")
                print(f"        Available: {list(available.keys())}")
                sys.exit(1)
            selected[gid] = available[gid]
    else:
        selected = available

    # Health check
    pipeline = MVPPipeline(max_workers=args.workers)
    if not pipeline.client.is_available():
        print("[ERROR] VLM service not available. Is LM Studio running?")
        sys.exit(1)

    try:
        models_resp = pipeline.client.client.models.list()
        actual_model = models_resp.data[0].id if models_resp.data else pipeline.client.model
    except Exception:
        actual_model = pipeline.client.model

    print(f"[MVP] VLM service OK. Model: {actual_model}")
    print(f"[MVP] Running {len(selected)} groups × 5 VLM calls each (1+4, Step 3 disabled).")
    print(f"[MVP] Each group saved as its own txt in test_output/")

    output_dir = _REPO_ROOT / "test_output"
    output_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    saved_files = []

    for group_id, grp in selected.items():
        print(f"\n{'─'*60}")
        print(f"[MVP] === {group_id} ===")

        # Validate children
        child_paths, missing = _validate_children(grp["children"])
        if missing:
            print(f"  [WARN] Missing child images: {missing}")

        # Load parent (skipped if --no-parent)
        parent_img = None
        if not args.no_parent and grp.get("parent"):
            parent_img = _load_parent_pdf(grp["parent"])

        # Mode dispatch + parent-PDF-as-child fallback when no real children exist
        if args.parent_only:
            if parent_img is None:
                print(f"  [SKIP] --parent-only set but no parent available for {group_id}")
                continue
            child_paths = []
            mode_label = "parent-only"
            print(f"  [RUN] parent-only mode — sending parent image only")
        elif args.no_parent:
            # No-parent mode: need at least one child. If none, render the PDF as fallback.
            if not child_paths and grp.get("parent"):
                fallback = _load_parent_pdf(grp["parent"])
                if fallback is not None:
                    child_paths = [fallback]
                    print(f"  [RUN] No child images — using parent PDF page as child fallback")
            if not child_paths:
                print(f"  [SKIP] --no-parent but no children and no PDF fallback for {group_id}")
                continue
            mode_label = "child-only"
        else:
            # Default mode: parent + children. At least one of them must exist.
            if parent_img is None and not child_paths:
                print(f"  [SKIP] No images at all for {group_id}")
                continue
            mode_label = "full"

        # Run pipeline
        result = pipeline.run(
            child_images=child_paths,
            parent_image=parent_img,
        )

        # Per-group header
        header = (
            f"MVP Multi-Agent VLM Pipeline — {ts}\n"
            f"Model: {actual_model}\n"
            f"Group: {group_id}  |  Calls: 5 (1+4, Step3 disabled)  |  Mode: {mode_label}\n"
            f"Workers (Step 2): {args.workers}\n"
        )
        block = _fmt_result(group_id, result)

        # Sanitise group_id for use as a filename
        safe_id = group_id.replace("/", "_").replace(" ", "_").replace("\\", "_")
        out_path = output_dir / f"mvp_{safe_id}_{mode_label}_{ts}.txt"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(header + "\n" + block)
        saved_files.append(out_path.name)
        print(f"  [MVP] Saved → {out_path.name}")

    print(f"\n[MVP] All done. {len(saved_files)} files saved:")
    for name in saved_files:
        print(f"  → {name}")


if __name__ == "__main__":
    main()
