"""
OCR Extractor for Manufacturing Drawings.

Uses PaddleOCR to extract Chinese and English text from engineering drawings.
Optimized for technical blueprints with both language requirements.
"""

from typing import List, Optional, Tuple
import numpy as np
import cv2
from pathlib import Path

try:
    from paddleocr import PaddleOCR
except ImportError:
    raise ImportError("PaddleOCR not installed. Run: pip install paddleocr")

from ..schema import OCRResult


class OCRExtractor:
    """
    Wrapper for PaddleOCR optimized for engineering drawings.
    
    Features:
    - Supports both Chinese (Traditional/Simplified) and English
    - Returns bounding boxes, text, and confidence scores
    - Handles monochrome technical drawings (white bg + black lines)
    """
    
    def __init__(
        self,
        use_angle_cls: bool = True,
        lang: str = "ch"
    ):
        """
        Initialize OCR engine.
        
        Args:
            use_angle_cls: Enable text direction classification (useful for rotated text).
            lang: Language code. 'ch' for Chinese+English, 'en' for English only.
        """
        self.ocr = PaddleOCR(
            use_angle_cls=use_angle_cls,
            lang=lang
        )
    
    def extract(
        self,
        image: np.ndarray,
        confidence_threshold: float = 0.5
    ) -> List[OCRResult]:
        """
        Extract text from engineering drawing.
        
        Args:
            image: Input image (BGR or grayscale).
            confidence_threshold: Minimum confidence to include result (0.0-1.0).
        
        Returns:
            List of OCRResult objects with text, bbox, and confidence.
        """
        # Convert to grayscale if needed (PaddleOCR accepts both)
        if len(image.shape) == 3:
            # Keep original for better OCR quality
            pass
        
        # Run PaddleOCR
        # Returns: List[List[bbox, (text, confidence)]]
        # bbox: [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
        result = self.ocr.ocr(image, cls=True)
        
        # Parse results
        ocr_results = []
        
        if result is None or len(result) == 0:
            return []
        
        # PaddleOCR returns nested list: [[line1], [line2], ...]
        for line in result[0]:
            if line is None:
                continue
            
            bbox, (text, confidence) = line
            
            # Filter by confidence
            if confidence < confidence_threshold:
                continue
            
            # Convert bbox to (x, y, w, h) format
            x_coords = [pt[0] for pt in bbox]
            y_coords = [pt[1] for pt in bbox]
            x = int(min(x_coords))
            y = int(min(y_coords))
            w = int(max(x_coords) - x)
            h = int(max(y_coords) - y)
            
            ocr_results.append(OCRResult(
                text=text.strip(),
                bbox=(x, y, w, h),
                confidence=float(confidence)
            ))
        
        return ocr_results
    
    def extract_from_file(
        self,
        image_path: str,
        confidence_threshold: float = 0.5
    ) -> List[OCRResult]:
        """
        Extract text from image file.
        
        Args:
            image_path: Path to image file.
            confidence_threshold: Minimum confidence to include result.
        
        Returns:
            List of OCRResult objects.
        """
        if not Path(image_path).exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        # Read image
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Failed to load image: {image_path}")
        
        return self.extract(image, confidence_threshold)
    
    def visualize(
        self,
        image: np.ndarray,
        ocr_results: List[OCRResult],
        color: Tuple[int, int, int] = (0, 255, 0),
        thickness: int = 2
    ) -> np.ndarray:
        """
        Draw OCR bounding boxes on image for debugging.
        
        Args:
            image: Input image.
            ocr_results: List of OCRResult objects.
            color: Box color (B, G, R).
            thickness: Box line thickness.
        
        Returns:
            Image with drawn boxes and text.
        """
        vis_image = image.copy()
        
        for result in ocr_results:
            x, y, w, h = result.bbox
            
            # Draw rectangle
            cv2.rectangle(vis_image, (x, y), (x + w, y + h), color, thickness)
            
            # Draw text label
            label = f"{result.text} ({result.confidence:.2f})"
            label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            
            # Background for text
            cv2.rectangle(
                vis_image,
                (x, y - label_size[1] - 4),
                (x + label_size[0], y),
                color,
                -1
            )
            
            # Text
            cv2.putText(
                vis_image,
                label,
                (x, y - 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1
            )
        
        return vis_image


# Convenience function for quick usage
def extract_text(image: np.ndarray, confidence_threshold: float = 0.5) -> List[OCRResult]:
    """
    Quick OCR extraction without creating extractor object.
    
    Args:
        image: Input image.
        confidence_threshold: Minimum confidence to include result.
    
    Returns:
        List of OCRResult objects.
    """
    extractor = OCRExtractor()
    return extractor.extract(image, confidence_threshold)
