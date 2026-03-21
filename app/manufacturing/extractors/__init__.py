"""
Feature Extractors for Manufacturing Recognition.

Modules:
- ocr: PaddleOCR text extraction
- embeddings: Visual embeddings (DINOv2)
- pdf_extractor: High-resolution PDF image extraction
"""

from .ocr import OCRExtractor
from .embeddings import VisualEmbedder
from .pdf_extractor import PDFImageExtractor, is_pdf_available, extract_from_pdf

__all__ = [
    'OCRExtractor',
    'VisualEmbedder',
    'PDFImageExtractor',
    'is_pdf_available',
    'extract_from_pdf'
]
