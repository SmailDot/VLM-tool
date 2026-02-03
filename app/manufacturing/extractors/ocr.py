"""
OCR Extractor for Manufacturing Drawings.

Uses PaddleOCR to extract Chinese and English text from engineering drawings.
Optimized for technical blueprints with both language requirements.
"""

from typing import List, Optional, Tuple, Dict, Any
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
    - Supports multilingual text extraction (Chinese, English, Japanese, Korean)
    - Returns bounding boxes, text, and confidence scores
    - Handles monochrome technical drawings (white bg + black lines)
    - Auto-detects and switches between language models
    """
    
    def __init__(
        self,
        use_angle_cls: bool = True,
        lang: str = "ch",
        enable_multilang: bool = False
    ):
        """
        Initialize OCR engine.
        
        Args:
            use_angle_cls: Enable text direction classification (useful for rotated text).
            lang: Primary language code. 
                  - 'ch': Chinese Simplified + English
                  - 'chinese_cht': Chinese Traditional + English
                  - 'en': English only
                  - 'japan': Japanese + English
                  - 'korean': Korean + English
            enable_multilang: Enable multi-language detection (slower, tries all languages).
        """
        self.primary_lang = lang
        self.enable_multilang = enable_multilang
        self.use_angle_cls = use_angle_cls
        
        # Initialize primary OCR engine
        self.ocr = PaddleOCR(
            use_angle_cls=use_angle_cls,
            lang=lang
        )
        
        # Cache for additional language engines (lazy loading)
        self.ocr_engines = {lang: self.ocr}
        
        # Supported languages for multi-language mode
        self.supported_langs = {
            'ch': 'Chinese Simplified',
            'chinese_cht': 'Chinese Traditional', 
            'en': 'English',
            'japan': 'Japanese',
            'korean': 'Korean'
        }
    
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
                bbox=[x, y, w, h],
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
            if result.bbox is None or len(result.bbox) != 4:
                continue
            x, y, w, h = result.bbox[0], result.bbox[1], result.bbox[2], result.bbox[3]
            
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
    
    def extract_region(
        self,
        image: np.ndarray,
        region: Tuple[int, int, int, int],
        confidence_threshold: float = 0.5
    ) -> List[OCRResult]:
        """
        Extract text from specific region of image.
        Useful for scanning title blocks or notes sections in engineering drawings.
        
        Args:
            image: Full input image (BGR or grayscale).
            region: (x, y, width, height) of the region to scan.
            confidence_threshold: Minimum confidence to include result.
        
        Returns:
            List of OCRResult objects with adjusted bbox coordinates (relative to full image).
        """
        x, y, w, h = region
        
        # Extract region
        roi = image[y:y+h, x:x+w]
        
        # Run OCR on region
        results = self.extract(roi, confidence_threshold)
        
        # Adjust bbox coordinates to full image space
        for result in results:
            if result.bbox:
                result.bbox[0] += x  # Adjust x
                result.bbox[1] += y  # Adjust y
        
        return results
    
    def extract_multilang(
        self,
        image: np.ndarray,
        languages: List[str] = None,
        confidence_threshold: float = 0.5,
        translate_to_chinese: bool = True
    ) -> List[OCRResult]:
        """
        Extract text with multiple language support.
        Tries each specified language and returns combined results.
        
        Args:
            image: Input image (BGR or grayscale).
            languages: List of language codes to try. 
                      If None, uses ['chinese_cht', 'en', 'japan', 'korean'].
            confidence_threshold: Minimum confidence to include result.
            translate_to_chinese: If True, attempts to translate non-Chinese text to Chinese.
        
        Returns:
            List of OCRResult objects with detected text in multiple languages.
        """
        if languages is None:
            # Default: Try Traditional Chinese, English, Japanese, Korean
            languages = ['chinese_cht', 'en', 'japan', 'korean']
        
        all_results = []
        seen_texts = set()  # Avoid duplicates
        
        for lang in languages:
            # Get or create OCR engine for this language
            if lang not in self.ocr_engines:
                try:
                    self.ocr_engines[lang] = PaddleOCR(
                        use_angle_cls=self.use_angle_cls,
                        lang=lang
                    )
                except Exception as e:
                    print(f"Warning: Failed to load OCR for language '{lang}': {e}")
                    continue
            
            ocr_engine = self.ocr_engines[lang]
            
            # Run OCR with this language
            try:
                result = ocr_engine.ocr(image, cls=True)
                
                if result is None or len(result) == 0:
                    continue
                
                # Parse results
                for line in result[0]:
                    if line is None:
                        continue
                    
                    bbox_pts, (text, confidence) = line
                    
                    # Filter by confidence
                    if confidence < confidence_threshold:
                        continue
                    
                    # Skip if we've seen this text already (avoid duplicates)
                    if text.strip() in seen_texts:
                        continue
                    
                    seen_texts.add(text.strip())
                    
                    # Convert bbox to (x, y, w, h) format
                    x_coords = [pt[0] for pt in bbox_pts]
                    y_coords = [pt[1] for pt in bbox_pts]
                    x = int(min(x_coords))
                    y = int(min(y_coords))
                    w = int(max(x_coords) - x)
                    h = int(max(y_coords) - y)
                    
                    ocr_result = OCRResult(
                        text=text.strip(),
                        bbox=[x, y, w, h],
                        confidence=float(confidence)
                    )
                    
                    # Add language metadata
                    if not hasattr(ocr_result, 'metadata'):
                        ocr_result.metadata = {}
                    ocr_result.metadata = {'language': lang}
                    
                    all_results.append(ocr_result)
                    
            except Exception as e:
                print(f"Warning: OCR failed for language '{lang}': {e}")
                continue
        
        return all_results
    
    def detect_title_block_notes(
        self,
        image: np.ndarray,
        scan_bottom_right: bool = True,
        region_ratio: float = 0.25,
        confidence_threshold: float = 0.5
    ) -> Dict[str, Any]:
        """
        Detect and extract notes from engineering drawing title block area.
        Typically located in bottom-right corner.
        
        Args:
            image: Full engineering drawing image.
            scan_bottom_right: If True, scan bottom-right quadrant (default for most drawings).
            region_ratio: Ratio of image size to scan (0.25 = bottom-right 25% of image).
            confidence_threshold: Minimum OCR confidence.
        
        Returns:
            Dictionary containing:
            - 'raw_texts': List[str] - All detected text lines
            - 'ocr_results': List[OCRResult] - Full OCR results with bbox
            - 'region': Tuple[int, int, int, int] - Scanned region (x, y, w, h)
            - 'important_notes': List[str] - Filtered important notes/warnings
        """
        h, w = image.shape[:2]
        
        if scan_bottom_right:
            # Bottom-right corner region
            region_w = int(w * region_ratio)
            region_h = int(h * region_ratio)
            x = w - region_w
            y = h - region_h
            region = (x, y, region_w, region_h)
        else:
            # Full image scan (fallback)
            region = (0, 0, w, h)
        
        # Extract text from region with multilingual support
        ocr_results = self.extract_multilang(
            image,
            languages=['chinese_cht', 'ch', 'en', 'japan', 'korean'],
            confidence_threshold=confidence_threshold,
            translate_to_chinese=False
        )
        
        # Filter results to only those in the scanned region
        region_results = []
        for result in ocr_results:
            if result.bbox:
                bbox_x, bbox_y = result.bbox[0], result.bbox[1]
                if (bbox_x >= region[0] and bbox_x < region[0] + region[2] and
                    bbox_y >= region[1] and bbox_y < region[1] + region[3]):
                    region_results.append(result)
        
        # Extract raw text lines
        raw_texts = [r.text for r in region_results]
        
        # Filter for important notes (heuristic: look for keywords)
        important_keywords = [
            '注意', '警告', 'note', 'warning', 'caution', 'important',
            '要求', 'requirement', '禁止', 'forbidden', 
            '必須', 'must', 'shall', '不可', 'do not',
            '注記', '備考', 'remark', '說明', 'specification'
        ]
        
        important_notes = []
        for text in raw_texts:
            text_lower = text.lower()
            if any(kw in text_lower for kw in important_keywords):
                important_notes.append(text)
            # Also include lines with exclamation marks or special symbols
            elif any(symbol in text for symbol in ['!', '！', '※', '★', '●']):
                important_notes.append(text)
        
        return {
            'raw_texts': raw_texts,
            'ocr_results': region_results,
            'region': region,
            'important_notes': important_notes
        }


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
