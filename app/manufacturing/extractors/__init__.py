"""
Feature Extractors for Manufacturing Recognition.

Each extractor carries heavy optional dependencies — import them directly
instead of relying on this package's __init__ to avoid loading the full
AI stack when only a lightweight module is needed.

Direct import examples:
    from app.manufacturing.extractors.ocr import OCRExtractor          # PaddleOCR
    from app.manufacturing.extractors.embeddings import VisualEmbedder  # DINOv2 / torch
    from app.manufacturing.extractors.pdf_extractor import PDFImageExtractor  # PyMuPDF
    from app.manufacturing.extractors.vlm_client import VLMClient       # OpenAI-compat
"""

# No eager imports — each extractor is loaded only when explicitly imported.

__all__ = [
    'OCRExtractor',
    'VisualEmbedder',
    'PDFImageExtractor',
    'is_pdf_available',
    'extract_from_pdf',
]
