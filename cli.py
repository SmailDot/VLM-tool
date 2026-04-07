"""
VLM Tool CLI — 工業製程圖紙辨識工具命令列介面

用法:
  python cli.py analyze      --image drawing.jpg [--parent p.jpg] [--bom "SUS304,T1.5"] [--rag] [--output result.json] [--vlm]
  python cli.py symbol-check --images img1.jpg img2.jpg [--symbol weld_v]
  python cli.py symbol-check --list-all
  python cli.py batch        --dir ./drawings/ [--bom "SUS304"] [--rag] [--output batch.json] [--vlm]
  python cli.py query        --image drawing.jpg --ask "這張圖有焊接符號嗎?" --vlm
  python cli.py crop         --image full_drawing.jpg --prefix "PART001" --output-dir ./cropped/
  python cli.py crop         --image full_drawing.jpg --prefix "PART001" --output-dir ./cropped/ --show-bbox --verify-views --vlm

所有子命令共用:
  --vlm      啟用 VLM（預設關閉，啟用需要 LM Studio 執行中）
  --verbose  顯示詳細處理過程
  --quiet    只輸出最終結果，無任何過程訊息
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path
from typing import Any, Dict


# ── helpers ─────────────────────────────────────────────────────────────────

def _log(msg: str, verbose: bool, quiet: bool) -> None:
    if verbose and not quiet:
        print(f"[INFO] {msg}", file=sys.stderr)


def _err(msg: str) -> None:
    print(f"[ERROR] {msg}", file=sys.stderr)


def _safe_print(text: str) -> None:
    """Print text, replacing unencodable characters so Windows consoles don't crash."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(
            sys.stdout.encoding or "utf-8"
        ))


def _out_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


# ── analyze ─────────────────────────────────────────────────────────────────

def cmd_analyze(args: argparse.Namespace) -> int:
    from app.core import AOVCoreService
    from app.features import run_analysis, build_analysis_request
    from app.cli.formatters import to_cli_json

    image_path = Path(args.image)
    if not image_path.exists():
        _err(f"Image not found: {args.image}")
        return 1

    parent: str | None = None
    if args.parent:
        parent_path = Path(args.parent)
        if not parent_path.exists():
            _err(f"Parent image not found: {args.parent}")
            return 1
        parent = str(parent_path)

    _log(f"Loading image: {image_path}", args.verbose, args.quiet)

    service = AOVCoreService()
    request = build_analysis_request(
        image=str(image_path),
        parent_image=parent,
        child_images=None,
        view_labels=None,
        locked_bom="",
        bom_context_input=args.bom or "",
        use_rag=args.rag,
        use_vlm=args.vlm,
        min_confidence=0.25,
        auto_crop=getattr(args, "auto_crop", False),
    )

    _log("Running analysis...", args.verbose, args.quiet)
    result, elapsed = run_analysis(service, request)

    output = to_cli_json(result, image_path=str(image_path), elapsed=elapsed)

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(
            json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if not args.quiet:
            print(f"Result written to {args.output}", file=sys.stderr)
    else:
        _out_json(output)

    return 0


# ── symbol-check ────────────────────────────────────────────────────────────

def _load_image_or_pdf(path: Path):
    """Return list of (label, np.ndarray) frames from an image or PDF file."""
    import cv2
    import numpy as np

    if path.suffix.lower() == ".pdf":
        try:
            from app.manufacturing.extractors.pdf_extractor import PDFImageExtractor
            extractor = PDFImageExtractor(target_dpi=150)
            import fitz
            doc = fitz.open(str(path))
            frames = []
            for page_num in range(len(doc)):
                img = extractor.extract_full_page(str(path), page_num=page_num)
                label = f"{path.name} (page {page_num + 1})"
                frames.append((label, img))
            doc.close()
            return frames
        except Exception as exc:
            return [(str(path), None, str(exc))]

    _buf = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(_buf, cv2.IMREAD_COLOR)
    return [(path.name, img)]


def cmd_symbol_check(args: argparse.Namespace) -> int:
    from app.vision.symbol_matcher import SymbolMatcher

    matcher = SymbolMatcher()

    if args.list_all:
        names = matcher.symbol_names
        if names:
            for name in sorted(names):
                print(name)
        else:
            print("(符號庫為空，請先新增符號模板至 data/symbol_library/)")
        return 0

    if not args.images:
        _err("--images 為必填（或使用 --list-all 列出可用符號）")
        return 1

    exit_code = 0
    for img_path_str in args.images:
        img_path = Path(img_path_str)
        if not img_path.exists():
            print(f"{img_path_str}: Error (file not found)", file=sys.stderr)
            exit_code = 1
            continue

        frames = _load_image_or_pdf(img_path)

        for frame in frames:
            if len(frame) == 3:  # error tuple
                label, img, err = frame
                print(f"{label}: Error ({err})", file=sys.stderr)
                exit_code = 1
                continue
            label, img = frame

            if img is None:
                print(f"{label}: Error (cannot load)", file=sys.stderr)
                exit_code = 1
                continue

            _log(f"Scanning: {label}", args.verbose, args.quiet)
            matches = matcher.match_symbols(img)

            # Filter out inf/nan confidence values.
            # TM_CCOEFF_NORMED with a sparse alpha mask produces inf when the image
            # patch under the mask has near-zero std (e.g. blank white paper).
            # These are false positives — discard them.
            import math
            matches = [m for m in matches if math.isfinite(m["confidence"])]

            if args.symbol:
                target = args.symbol.lower()
                hits = [m for m in matches if m["name"].lower() == target]
                if hits:
                    _safe_print(f"{label}: True (confidence: {hits[0]['confidence']:.2f})")
                else:
                    _safe_print(f"{label}: False")
            else:
                if matches:
                    for m in matches:
                        _safe_print(
                            f"{label}: {m['name']} = True"
                            f" (confidence: {m['confidence']:.2f})"
                        )
                else:
                    _safe_print(f"{label}: no symbols detected")

    return exit_code


# ── batch ───────────────────────────────────────────────────────────────────

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".pdf"}


def cmd_batch(args: argparse.Namespace) -> int:
    from app.core import AOVCoreService
    from app.features import run_analysis, build_analysis_request
    from app.cli.formatters import to_cli_json, to_batch_report

    dir_path = Path(args.dir)
    if not dir_path.is_dir():
        _err(f"Directory not found: {args.dir}")
        return 1

    image_files = sorted(
        p
        for p in dir_path.iterdir()
        if p.is_file() and p.suffix.lower() in _IMAGE_EXTS
    )

    if not image_files:
        _err(f"No image files found in {args.dir}")
        return 1

    service = AOVCoreService()
    auto_crop: bool = getattr(args, "auto_crop", False)
    entries = []
    total = len(image_files)

    for idx, img_path in enumerate(image_files, 1):
        if not args.quiet:
            print(f"[{idx}/{total}] {img_path.name} ...", file=sys.stderr)

        try:
            child_images = None
            view_labels = None

            if auto_crop:
                from app.vision.drawing_cropper import DrawingCropper
                cropper = DrawingCropper()
                views = cropper.crop_from_file(str(img_path), prefix="AUTO")
                if len(views) >= 2:
                    child_images = [v.image for v in views]
                    view_labels = [v.view_label for v in views]
                    if not args.quiet:
                        print(
                            f"  → 自動切圖：偵測到 {len(views)} 個視角",
                            file=sys.stderr,
                        )

            request = build_analysis_request(
                image=str(img_path),
                parent_image=None,
                child_images=child_images,
                view_labels=view_labels,
                locked_bom="",
                bom_context_input=args.bom or "",
                use_rag=args.rag,
                use_vlm=args.vlm,
                min_confidence=0.25,
            )
            result, elapsed = run_analysis(service, request)
            entry = to_cli_json(result, image_path=str(img_path), elapsed=elapsed)
        except Exception as exc:  # noqa: BLE001
            entry = {"image": str(img_path), "errors": [str(exc)], "elapsed_seconds": 0.0}
            if not args.quiet:
                print(f"  → Error: {exc}", file=sys.stderr)

        entries.append(entry)

        if args.verbose and not args.quiet:
            desc = entry.get("vlm_description") or ""
            short = desc[:100].replace("\n", " ") if desc else "(no description)"
            print(f"  → {short}", file=sys.stderr)

    report = to_batch_report(entries)

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if not args.quiet:
            print(
                f"\nReport written to {args.output}"
                f"  (total={report['total']} success={report['success']}"
                f" failed={report['failed']})",
                file=sys.stderr,
            )
    else:
        _out_json(report)

    return 0 if report["failed"] == 0 else 1


# ── crop ────────────────────────────────────────────────────────────────────

def cmd_crop(args: argparse.Namespace) -> int:
    from app.vision.drawing_cropper import DrawingCropper
    from app.vision.view_metadata import save_cropped_views

    img_path = Path(args.image)
    if not img_path.exists():
        _err(f"Image not found: {args.image}")
        return 1

    output_dir = Path(args.output_dir)
    prefix = args.prefix or "PART"

    _log(f"Loading image: {img_path}", args.verbose, args.quiet)

    cropper = DrawingCropper()
    views = cropper.crop_from_file(str(img_path), prefix=prefix)

    if not views:
        _err("切圖失敗：未偵測到任何視角（請確認輸入為多視角工程圖）")
        return 1

    # Layer 2: VLM view verification (opt-in)
    if getattr(args, "verify_views", False):
        if not args.vlm:
            _err("--verify-views 需要搭配 --vlm（需要 LM Studio 執行中）")
            return 1
        _log("使用 VLM 驗證視角標籤...", args.verbose, args.quiet)
        views = cropper.verify_views_with_vlm(views)

    # Save images + metadata.json
    meta_path = save_cropped_views(views, str(output_dir), img_path.name)

    if not args.quiet:
        print(f"切圖完成：{len(views)} 個視角")
        for i, v in enumerate(views, 1):
            line = (
                f"  [{i}] {v.suggested_filename}"
                f"  {v.view_label_zh}"
                f"  信心度: {v.confidence:.2f}"
            )
            if getattr(args, "show_bbox", False):
                x, y, w, h = v.bbox
                line += f"  bbox=({x},{y},{w},{h})"
            _safe_print(line)
        print(f"metadata.json 已寫入 {meta_path}", file=sys.stderr)

    return 0


# ── query ───────────────────────────────────────────────────────────────────

def cmd_query(args: argparse.Namespace) -> int:
    if not args.vlm:
        _err("query 子命令必須加上 --vlm（需要 LM Studio 執行中）")
        return 1

    img_path = Path(args.image)
    if not img_path.exists():
        _err(f"Image not found: {args.image}")
        return 1

    _log(f"Querying VLM: {args.ask}", args.verbose, args.quiet)
    result = _query_via_vlm(str(img_path), args.ask, verbose=args.verbose, quiet=args.quiet)
    _out_json(result)
    return 0


def _query_via_vlm(
    image_path: str,
    question: str,
    verbose: bool = False,
    quiet: bool = False,
) -> Dict[str, Any]:
    """Send a yes/no question to the VLM using a lightweight system prompt.

    Bypasses the standard 3-section report format so the model can answer
    free-form questions concisely.
    """
    import cv2
    import numpy as np
    from app.config import VLM_BASE_URL, VLM_MODEL

    try:
        from openai import OpenAI
    except ImportError:
        return {"answer": False, "reason": "openai package not installed", "confidence": "low"}

    _buf = np.fromfile(image_path, dtype=np.uint8)
    img = cv2.imdecode(_buf, cv2.IMREAD_COLOR)
    if img is None:
        return {"answer": False, "reason": f"Cannot load image: {image_path}", "confidence": "low"}

    _, buf = cv2.imencode(".png", img)
    b64 = base64.b64encode(buf.tobytes()).decode()

    system = (
        "You are an expert sheet metal drawing analyst. "
        "Answer yes/no questions about engineering drawings concisely. "
        "Reply in this exact 3-line format — no extra text:\n"
        "Answer: True\n"
        "Reason: <one sentence referencing what you observe in the drawing>\n"
        "Confidence: high"
    )

    _log("Connecting to VLM...", verbose, quiet)
    try:
        oai = OpenAI(base_url=VLM_BASE_URL, api_key="not-needed", timeout=60, max_retries=1)
        resp = oai.chat.completions.create(
            model=VLM_MODEL,
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": question},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                    ],
                },
            ],
            temperature=0.1,
            max_tokens=200,
        )
        text = (resp.choices[0].message.content or "").strip()
    except Exception as exc:  # noqa: BLE001
        return {"answer": False, "reason": f"VLM request failed: {exc}", "confidence": "low"}

    _log(f"VLM raw response: {text[:200]}", verbose, quiet)

    parsed: Dict[str, str] = {}
    for line in text.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            parsed[k.strip().lower()] = v.strip()

    raw_answer = parsed.get("answer", "false").lower()
    answer = raw_answer in ("true", "yes", "1")
    reason = parsed.get("reason", text[:300])
    confidence = parsed.get("confidence", "medium").lower()
    if confidence not in ("high", "medium", "low"):
        confidence = "medium"

    return {"answer": answer, "reason": reason, "confidence": confidence}


# ── parser ───────────────────────────────────────────────────────────────────

def _shared_parser() -> argparse.ArgumentParser:
    """Parent parser that injects shared flags into every subcommand."""
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument(
        "--vlm",
        action="store_true",
        help="啟用 VLM（預設關閉，啟用需要 LM Studio 執行中）",
    )
    p.add_argument("--verbose", action="store_true", help="顯示詳細處理過程")
    p.add_argument("--quiet", action="store_true", help="只輸出最終結果，無任何過程訊息")
    return p


def build_parser() -> argparse.ArgumentParser:
    shared = _shared_parser()

    parser = argparse.ArgumentParser(
        prog="cli.py",
        description="VLM Tool CLI — 工業製程圖紙辨識工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "範例:\n"
            "  python cli.py analyze --image drawing.jpg\n"
            "  python cli.py analyze --image drawing.jpg --parent parent.jpg\n"
            "  python cli.py analyze --image drawing.jpg --bom \"SUS304, T1.5\"\n"
            "  python cli.py analyze --image drawing.jpg --rag --output result.json --vlm\n"
            "\n"
            "  python cli.py symbol-check --images img1.jpg img2.jpg --symbol weld_v\n"
            "  python cli.py symbol-check --images img1.jpg --list-all\n"
            "\n"
            "  python cli.py batch --dir ./drawings/\n"
            "  python cli.py batch --dir ./drawings/ --output batch_result.json\n"
            "  python cli.py batch --dir ./drawings/ --bom \"SUS304\" --rag --vlm\n"
            "\n"
            "  python cli.py query --image drawing.jpg --ask \"這張圖有焊接符號嗎?\" --vlm\n"
        ),
    )

    sub = parser.add_subparsers(dest="command", metavar="<command>")
    sub.required = True

    # ── analyze ──────────────────────────────────────────────────────────
    p_analyze = sub.add_parser(
        "analyze",
        parents=[shared],
        help="對單張圖執行完整 VLM 分析",
        description=(
            "對單張工程圖執行完整分析（符號偵測 + VLM 描述 + RAG 檢索）。\n"
            "預設輸出 JSON 到 stdout；加 --output 寫入檔案。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "用法:\n"
            "  python cli.py analyze --image drawing.jpg\n"
            "  python cli.py analyze --image drawing.jpg --parent parent.jpg\n"
            "  python cli.py analyze --image drawing.jpg --bom \"SUS304, T1.5\"\n"
            "  python cli.py analyze --image drawing.jpg --rag --output result.json --vlm\n"
        ),
    )
    p_analyze.add_argument(
        "--image", required=True, metavar="PATH", help="輸入圖片路徑（JPG / PNG / PDF）"
    )
    p_analyze.add_argument("--parent", metavar="PATH", help="母件圖（BOM context 來源）")
    p_analyze.add_argument("--bom", metavar="TEXT", help="BOM 字串，例如 'SUS304, T1.5'")
    p_analyze.add_argument("--rag", action="store_true", help="啟用 RAG 知識庫檢索")
    p_analyze.add_argument(
        "--auto-crop",
        dest="auto_crop",
        action="store_true",
        help="自動切割多視角工程圖再分析（寬高比 > 1.2 才觸發）",
    )
    p_analyze.add_argument(
        "--output", metavar="FILE", help="輸出 JSON 寫入此檔案（預設 stdout）"
    )
    p_analyze.set_defaults(func=cmd_analyze)

    # ── symbol-check ─────────────────────────────────────────────────────
    p_sym = sub.add_parser(
        "symbol-check",
        parents=[shared],
        help="檢查圖片是否含有指定符號（純 CV，不需 VLM）",
        description=(
            "使用 CV 模板比對偵測符號，不需 LM Studio，可離線執行。\n"
            "符號模板存放於 data/symbol_library/*.png。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "用法:\n"
            "  python cli.py symbol-check --images img1.jpg img2.jpg --symbol weld_v\n"
            "  python cli.py symbol-check --images img1.jpg\n"
            "  python cli.py symbol-check --list-all\n"
            "\n"
            "輸出:\n"
            "  img1.jpg: True (confidence: 0.87)\n"
            "  img2.jpg: False\n"
        ),
    )
    p_sym.add_argument(
        "--images", nargs="+", metavar="PATH", help="輸入圖片路徑（可多張）"
    )
    p_sym.add_argument(
        "--symbol", metavar="NAME", help="指定符號名稱篩選（例如 weld_v）"
    )
    p_sym.add_argument(
        "--list-all", action="store_true", help="列出符號庫所有可用的符號名稱"
    )
    p_sym.set_defaults(func=cmd_symbol_check)

    # ── batch ─────────────────────────────────────────────────────────────
    p_batch = sub.add_parser(
        "batch",
        parents=[shared],
        help="對整個資料夾批次分析",
        description=(
            "對指定資料夾中所有圖片（JPG / PNG / PDF）執行分析。\n"
            "輸出一份 JSON，包含每張圖的結果摘要與總計。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "用法:\n"
            "  python cli.py batch --dir ./drawings/\n"
            "  python cli.py batch --dir ./drawings/ --output batch_result.json\n"
            "  python cli.py batch --dir ./drawings/ --bom \"SUS304\" --rag --vlm\n"
        ),
    )
    p_batch.add_argument(
        "--dir", required=True, metavar="DIR", help="輸入圖片資料夾路徑"
    )
    p_batch.add_argument("--bom", metavar="TEXT", help="套用至所有圖片的 BOM 字串")
    p_batch.add_argument("--rag", action="store_true", help="啟用 RAG 知識庫檢索")
    p_batch.add_argument(
        "--auto-crop",
        dest="auto_crop",
        action="store_true",
        help="對每張圖先自動切圖再分析（切出 2 張以上才啟用多視角模式）",
    )
    p_batch.add_argument(
        "--output", metavar="FILE", help="輸出 JSON 寫入此檔案（預設 stdout）"
    )
    p_batch.set_defaults(func=cmd_batch)

    # ── query ─────────────────────────────────────────────────────────────
    p_query = sub.add_parser(
        "query",
        parents=[shared],
        help="用自然語言問是非題，VLM 回答 True/False + 原因",
        description=(
            "對圖片提出一個是非題，VLM 回答 True/False 並附上原因與信心水準。\n"
            "必須搭配 --vlm 旗標使用（需要 LM Studio 執行中）。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "用法:\n"
            "  python cli.py query --image drawing.jpg --ask \"這張圖有焊接符號嗎?\" --vlm\n"
            "\n"
            "輸出:\n"
            "  {\n"
            "    \"answer\": true,\n"
            "    \"reason\": \"Section 2 shows Weld symbol detected: True at upper-left flange area\",\n"
            "    \"confidence\": \"high\"\n"
            "  }\n"
        ),
    )
    p_query.add_argument(
        "--image", required=True, metavar="PATH", help="輸入圖片路徑"
    )
    p_query.add_argument(
        "--ask", required=True, metavar="QUESTION", help="是非題問題（例如 '這張圖有焊接符號嗎?'）"
    )
    p_query.set_defaults(func=cmd_query)

    # ── crop ──────────────────────────────────────────────────────────────
    p_crop = sub.add_parser(
        "crop",
        parents=[shared],
        help="自動切割多視角工程圖（俯視 / 前視 / 側視 / 等角）",
        description=(
            "偵測工程圖的多個視角並各自切割儲存，同時輸出 metadata.json。\n"
            "視角辨識採三層架構：位置規則 → VLM 確認（--verify-views）→ HITL（Streamlit）。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "用法:\n"
            "  python cli.py crop --image drawing.jpg --prefix \"PART001\" --output-dir ./cropped/\n"
            "  python cli.py crop --image drawing.jpg --prefix \"PART001\" --output-dir ./cropped/ --show-bbox\n"
            "  python cli.py crop --image drawing.jpg --prefix \"PART001\" --output-dir ./cropped/ --verify-views --vlm\n"
            "\n"
            "輸出:\n"
            "  切圖完成：4 個視角\n"
            "    [1] PART001-01_Top.png  俯視圖  信心度: 0.85\n"
            "    [2] PART001-02_Front.png  前視圖  信心度: 0.85\n"
            "    [3] PART001-03_Side.png  側視圖  信心度: 0.85\n"
            "    [4] PART001-04_Iso.png  等角視圖  信心度: 0.65\n"
            "  metadata.json 已寫入 ./cropped/metadata.json\n"
        ),
    )
    p_crop.add_argument(
        "--image", required=True, metavar="PATH", help="輸入圖片路徑（JPG / PNG）"
    )
    p_crop.add_argument(
        "--prefix", default="PART", metavar="PREFIX", help="輸出檔名前綴（例如 PART001）"
    )
    p_crop.add_argument(
        "--output-dir",
        required=True,
        dest="output_dir",
        metavar="DIR",
        help="切圖輸出目錄（若不存在則自動建立）",
    )
    p_crop.add_argument(
        "--show-bbox",
        dest="show_bbox",
        action="store_true",
        help="輸出每個視角在原圖的 bbox 座標",
    )
    p_crop.add_argument(
        "--verify-views",
        dest="verify_views",
        action="store_true",
        help="啟用第二層 VLM 視角確認（需搭配 --vlm）",
    )
    p_crop.set_defaults(func=cmd_crop)

    return parser


# ── entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
