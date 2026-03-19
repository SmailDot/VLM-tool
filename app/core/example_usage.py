"""Minimal embedding example for external projects."""

from pathlib import Path

from .contracts import AnalysisRequest
from .service import AOVCoreService


def run_example(image_path: str) -> str:
    """Return VLM description using pluggable core service."""
    service = AOVCoreService()
    request = AnalysisRequest(
        image=str(Path(image_path)),
        use_vlm=True,
        use_rag=False,
    )
    result = service.analyze(request)
    return result.features.raw_vlm_description or ""
