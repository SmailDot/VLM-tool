"""
Manufacturing Extractors Module.

Provides feature extractors for engineering drawing analysis:
- OCR: Text extraction (PaddleOCR)
- Geometry: Line/shape detection (OpenCV)
- Symbols: Technical symbol recognition (Template matching)
- Embeddings: Visual semantic embeddings (DINOv2/CLIP)
"""

from .ocr import OCRExtractor, extract_text
from .geometry import GeometryExtractor, extract_geometry
from .symbols import SymbolDetector, detect_symbols, SymbolType
from .embeddings import VisualEmbedder, extract_embedding

__all__ = [
    # OCR
    "OCRExtractor",
    "extract_text",
    
    # Geometry
    "GeometryExtractor",
    "extract_geometry",
    
    # Symbols
    "SymbolDetector",
    "detect_symbols",
    "SymbolType",
    
    # Embeddings
    "VisualEmbedder",
    "extract_embedding",
]
