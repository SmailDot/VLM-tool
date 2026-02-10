"""
Feature Extractors for Manufacturing Recognition.

Modules:
- ocr: PaddleOCR text extraction
- geometry: Geometric primitive detection
- symbols: Symbol template matching
- embeddings: Visual embeddings (DINOv2)
- pdf_extractor: High-resolution PDF image extraction
"""

from .ocr import OCRExtractor
from .geometry import GeometryExtractor
from .symbols import SymbolDetector
from .embeddings import VisualEmbedder
from .llm_client import LLMClient
from .pdf_extractor import PDFImageExtractor, is_pdf_available, extract_from_pdf

__all__ = [
    'OCRExtractor',
    'GeometryExtractor',
    'SymbolDetector',
    'VisualEmbedder',
    'PDFImageExtractor',
    'is_pdf_available',
    'extract_from_pdf',
    'LLMClient'
]
