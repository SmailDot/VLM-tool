"""
Manufacturing Process Recognition Module
製程辨識模組

This module provides tools for recognizing manufacturing processes
from engineering drawings.

Main components:
- schema: Data structures
- extractors: OCR, embeddings, PDF
- decision: Process scoring and prediction
- pipeline: End-to-end recognition orchestration
"""

from .schema import (
    TIER1_VOCABULARY,
    ExtractedFeatures,
    ProcessPrediction,
    RecognitionResult,
    OCRResult,
    SymbolDetection,
    GeometryFeatures,
    FeatureType,
    ProcessCategory
)

# NOTE: pipeline / extractors are NOT eagerly imported here.
# They carry heavy optional dependencies (torch, paddle, openai, cv2).
# Import them directly when needed:
#   from app.manufacturing.pipeline import ManufacturingPipeline
#   from app.manufacturing.process_brain import ProcessBrain
# This keeps lightweight modules (schema, process_brain) fast to import.

def get_pipeline():
    """Lazy accessor — returns ManufacturingPipeline without triggering
    torch/paddle/openai at module load time."""
    from .pipeline import ManufacturingPipeline
    return ManufacturingPipeline

__all__ = [
    # Data structures (always safe to import)
    "ExtractedFeatures",
    "ProcessPrediction",
    "RecognitionResult",
    "OCRResult",
    "SymbolDetection",
    "GeometryFeatures",
    "FeatureType",
    "ProcessCategory",
    # Lazy accessor
    "get_pipeline",
]

__version__ = "1.0.0"
