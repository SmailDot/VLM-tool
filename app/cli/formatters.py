"""CLI output formatters — convert RecognitionResult to CLI-friendly structures."""

from __future__ import annotations

from typing import Any, Dict, List

from app.manufacturing.schema import RecognitionResult


def to_cli_json(
    result: RecognitionResult,
    image_path: str = "",
    elapsed: float = 0.0,
) -> Dict[str, Any]:
    """Convert RecognitionResult to a JSON-serialisable dict for CLI output.

    Strips large fields (visual / text embeddings) that are not useful in a
    CLI context and keeps only human-readable data.
    """
    features = result.features

    symbols = [
        {
            "name": s.label,
            "type": s.symbol_type,
            "confidence": round(s.confidence, 3),
            "bbox": s.bbox,
        }
        for s in features.symbols
    ]

    ocr_texts = [
        o.text
        for o in features.ocr_results
        if o.text.strip()
    ]

    output: Dict[str, Any] = {
        "image": image_path,
        "elapsed_seconds": round(elapsed, 2),
        "vlm_description": features.raw_vlm_description,
        "vlm_description_v1": features.raw_vlm_description_v1,
        "symbols": symbols,
        "ocr_texts": ocr_texts,
        "rag_references": result.rag_references,
        "process_inferences": result.process_inferences,
        "vlm_process_selection": result.vlm_process_selection,
        "warnings": result.warnings,
        "errors": result.errors,
        "total_time": round(result.total_time, 2),
    }

    if result.parent_context:
        ctx = result.parent_context
        output["parent_context"] = {
            "material": ctx.material,
            "thickness": ctx.thickness,
            "customer": ctx.customer,
        }

    return output


def to_cli_summary(
    image_path: str,
    result: RecognitionResult,
    elapsed: float = 0.0,
) -> str:
    """Single-line summary for batch progress display."""
    desc = result.features.raw_vlm_description or ""
    short = desc[:80].replace("\n", " ") if desc else "(no description)"
    symbol_count = len(result.features.symbols)
    return f"{image_path}: symbols={symbol_count}, time={elapsed:.1f}s | {short}"


def to_batch_report(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate batch results into a summary report."""
    total = len(entries)
    failed = sum(1 for e in entries if e.get("errors"))
    return {
        "total": total,
        "success": total - failed,
        "failed": failed,
        "results": entries,
    }
