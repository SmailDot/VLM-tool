"""
Manufacturing Process Recognition Module
製程辨識模組

This module provides tools for recognizing manufacturing processes
from engineering drawings.

Main components:
- schema: Data structures
- ingestion: PDF/Image preprocessing
- extractors: OCR, symbols, geometry, embeddings
- rag: Knowledge base and retrieval
- decision: Process scoring and prediction
- pipeline: End-to-end recognition orchestration
"""

from .schema import (
    ExtractedFeatures,
    ManufacturingCase,
    ProcessPrediction,
    RecognitionResult,
    ProcessDefinition,
    OCRResult,
    SymbolDetection,
    GeometryFeatures,
    FeatureType,
    ProcessCategory
)

# Import pipeline for direct usage
from .pipeline import ManufacturingPipeline, recognize

# Import decision engines
from .decision import DecisionEngine
from .decision.engine_v2 import DecisionEngineV2

__all__ = [
    # Data structures
    "ExtractedFeatures",
    "ManufacturingCase",
    "ProcessPrediction",
    "RecognitionResult",
    "ProcessDefinition",
    "OCRResult",
    "SymbolDetection",
    "GeometryFeatures",
    "FeatureType",
    "ProcessCategory",
    
    # Main pipeline
    "ManufacturingPipeline",
    "recognize",
    
    # Decision engines
    "DecisionEngine",
    "DecisionEngineV2",
]

__version__ = "1.0.0"
