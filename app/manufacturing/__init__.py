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

# Import pipeline for direct usage
from .pipeline import ManufacturingPipeline, recognize

__all__ = [
    # Data structures
    "ExtractedFeatures",
    "ProcessPrediction",
    "RecognitionResult",
    "OCRResult",
    "SymbolDetection",
    "GeometryFeatures",
    "FeatureType",
    "ProcessCategory",
    # Main pipeline
    "ManufacturingPipeline",
    "recognize",
]

__version__ = "1.0.0"
