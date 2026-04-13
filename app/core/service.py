"""Service facade for modular VLM drawing analysis."""

from typing import Optional

from app.manufacturing.pipeline import ManufacturingPipeline
from app.manufacturing.schema import RecognitionResult

from .contracts import AnalysisRequest


class AOVCoreService:
    """Stable facade that other projects can import as a puzzle-piece module."""

    def __init__(self) -> None:
        self._pipeline: Optional[ManufacturingPipeline] = None
        self._last_use_vlm: Optional[bool] = None

    def _ensure_pipeline(self, request: AnalysisRequest) -> ManufacturingPipeline:
        need_rebuild = (
            self._pipeline is None
            or self._last_use_vlm != request.use_vlm
            or getattr(self._pipeline, "auto_crop", False) != request.auto_crop
        )
        if need_rebuild:
            self._pipeline = ManufacturingPipeline(
                use_visual=False,
                use_vlm=request.use_vlm,
                enable_process_prediction=False,
                auto_crop=request.auto_crop,
            )
            self._last_use_vlm = request.use_vlm
        else:
            self._pipeline.reset_vlm_client()
        return self._pipeline

    def analyze(self, request: AnalysisRequest) -> RecognitionResult:
        """Run VLM-first drawing analysis and return recognition result contract."""
        pipeline = self._ensure_pipeline(request)
        return pipeline.recognize(
            request.image,
            parent_image=request.parent_image,
            top_n=None,
            min_confidence=request.min_confidence,
            frequency_filter=None,
            use_rag=request.use_rag,
            child_images=request.child_images,
            view_labels=request.view_labels,
            bom_context=request.bom_context,
            enable_process_prediction=False,
        )
