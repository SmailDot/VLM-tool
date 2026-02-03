"""
Symbol Detector for Manufacturing Drawings.

Detects welding symbols, surface finish marks, and other technical annotations
using template matching and pattern recognition.
"""

from typing import List, Tuple, Optional, Dict
import numpy as np
import cv2
from pathlib import Path
from enum import Enum

from ..schema import SymbolDetection


class SymbolType(str, Enum):
    """Known manufacturing symbol types."""
    WELDING = "welding"
    SPOT_WELDING = "spot_welding"
    SURFACE_FINISH = "surface_finish"
    GEOMETRIC_TOLERANCE = "geometric_tolerance"
    DIMENSION = "dimension"
    UNKNOWN = "unknown"


class SymbolDetector:
    """
    Detect manufacturing symbols in engineering drawings.
    
    Phase 1: Template matching (basic)
    Future: Deep learning-based symbol recognition (YOLOv8/Detectron2)
    """
    
    def __init__(self, template_dir: Optional[str] = None):
        """
        Initialize symbol detector.
        
        Args:
            template_dir: Directory containing symbol template images.
                         If None, uses built-in heuristics only.
        """
        self.template_dir = template_dir
        self.templates: Dict[SymbolType, List[np.ndarray]] = {}
        
        if template_dir and Path(template_dir).exists():
            self._load_templates()
    
    def _load_templates(self):
        """Load symbol templates from directory."""
        template_path = Path(self.template_dir)
        
        # Expected structure:
        # template_dir/
        #   welding/
        #     weld_01.png
        #     weld_02.png
        #   spot_welding/
        #     spot_01.png
        #   surface_finish/
        #     finish_01.png
        
        for symbol_type in SymbolType:
            if symbol_type == SymbolType.UNKNOWN:
                continue
            
            symbol_dir = template_path / symbol_type.value
            if symbol_dir.exists():
                templates = []
                for img_file in symbol_dir.glob("*.png"):
                    template = cv2.imread(str(img_file), cv2.IMREAD_GRAYSCALE)
                    if template is not None:
                        templates.append(template)
                
                if templates:
                    self.templates[symbol_type] = templates
    
    def detect(
        self,
        image: np.ndarray,
        confidence_threshold: float = 0.6
    ) -> List[SymbolDetection]:
        """
        Detect symbols in engineering drawing.
        
        Args:
            image: Input image (BGR or grayscale).
            confidence_threshold: Minimum matching confidence (0.0-1.0).
        
        Returns:
            List of SymbolDetection objects.
        """
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        detections = []
        
        # Method 1: Template matching (if templates available)
        if self.templates:
            detections.extend(
                self._template_matching(gray, confidence_threshold)
            )
        
        # Method 2: Heuristic detection (pattern-based)
        detections.extend(
            self._heuristic_detection(gray, confidence_threshold)
        )
        
        # Remove duplicates (same symbol detected multiple times)
        detections = self._remove_duplicates(detections)
        
        return detections
    
    def _template_matching(
        self,
        gray: np.ndarray,
        threshold: float
    ) -> List[SymbolDetection]:
        """
        Detect symbols using template matching.
        
        Args:
            gray: Grayscale image.
            threshold: Matching threshold.
        
        Returns:
            List of detections.
        """
        detections = []
        
        for symbol_type, templates in self.templates.items():
            for template in templates:
                # Multi-scale template matching
                for scale in [0.5, 0.75, 1.0, 1.25, 1.5]:
                    # Resize template
                    scaled_template = cv2.resize(
                        template,
                        None,
                        fx=scale,
                        fy=scale,
                        interpolation=cv2.INTER_LINEAR
                    )
                    
                    # Skip if template is larger than image
                    if (scaled_template.shape[0] > gray.shape[0] or
                        scaled_template.shape[1] > gray.shape[1]):
                        continue
                    
                    # Template matching
                    result = cv2.matchTemplate(
                        gray,
                        scaled_template,
                        cv2.TM_CCOEFF_NORMED
                    )
                    
                    # Find matches above threshold
                    locations = np.where(result >= threshold)
                    
                    for pt in zip(*locations[::-1]):
                        x, y = pt
                        w, h = scaled_template.shape[::-1]
                        
                        detections.append(SymbolDetection(
                            symbol_type=symbol_type.value,
                            label=symbol_type.value,  # Use symbol_type as label
                            confidence=float(result[y, x]),
                            bbox=[x, y, w, h]
                        ))
        
        return detections
    
    def _heuristic_detection(
        self,
        gray: np.ndarray,
        threshold: float
    ) -> List[SymbolDetection]:
        """
        Detect symbols using heuristic patterns.
        
        This method looks for common patterns in technical drawings:
        - Welding: Triangle + line combinations
        - SPOT: Circle + text "SPOT"
        - Surface finish: Check mark-like patterns
        
        Args:
            gray: Grayscale image.
            threshold: Confidence threshold (not used in heuristics).
        
        Returns:
            List of detections.
        """
        detections = []
        
        # Edge detection
        edges = cv2.Canny(gray, 50, 150)
        
        # Find contours
        contours, _ = cv2.findContours(
            edges,
            cv2.RETR_TREE,
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        for contour in contours:
            # Get bounding box
            x, y, w, h = cv2.boundingRect(contour)
            
            # Skip very small or very large contours
            area = w * h
            if area < 100 or area > gray.shape[0] * gray.shape[1] * 0.1:
                continue
            
            # Analyze shape
            symbol_type = self._classify_contour_shape(contour)
            
            if symbol_type != SymbolType.UNKNOWN:
                detections.append(SymbolDetection(
                    symbol_type=symbol_type.value,
                    label=symbol_type.value,  # Use symbol_type as label
                    confidence=0.7,  # Heuristic confidence
                    bbox=[x, y, w, h]
                ))
        
        return detections
    
    def _classify_contour_shape(self, contour: np.ndarray) -> SymbolType:
        """
        Classify contour shape into symbol type.
        
        Args:
            contour: Contour points.
        
        Returns:
            SymbolType enum value.
        """
        # Approximate polygon
        epsilon = 0.02 * cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon, True)
        
        num_vertices = len(approx)
        
        # Triangle-like → Potential welding symbol
        if num_vertices == 3:
            return SymbolType.WELDING
        
        # Circle-like → Potential spot welding or tolerance
        elif num_vertices > 8:
            # Check circularity
            area = cv2.contourArea(contour)
            perimeter = cv2.arcLength(contour, True)
            if perimeter > 0:
                circularity = 4 * np.pi * area / (perimeter ** 2)
                if circularity > 0.7:
                    return SymbolType.SPOT_WELDING
        
        return SymbolType.UNKNOWN
    
    def _remove_duplicates(
        self,
        detections: List[SymbolDetection],
        iou_threshold: float = 0.5
    ) -> List[SymbolDetection]:
        """
        Remove duplicate detections using Non-Maximum Suppression.
        
        Args:
            detections: List of detections.
            iou_threshold: IoU threshold for considering duplicates.
        
        Returns:
            Filtered list of detections.
        """
        if not detections:
            return []
        
        # Sort by confidence
        detections = sorted(detections, key=lambda d: d.confidence, reverse=True)
        
        keep = []
        
        while detections:
            # Take highest confidence detection
            current = detections.pop(0)
            keep.append(current)
            
            # Remove overlapping detections
            detections = [
                d for d in detections
                if self._calculate_iou(current.bbox, d.bbox) < iou_threshold
            ]
        
        return keep
    
    def _calculate_iou(
        self,
        box1: Tuple[int, int, int, int],
        box2: Tuple[int, int, int, int]
    ) -> float:
        """
        Calculate Intersection over Union (IoU) of two boxes.
        
        Args:
            box1: (x, y, w, h)
            box2: (x, y, w, h)
        
        Returns:
            IoU value (0.0-1.0).
        """
        x1, y1, w1, h1 = box1
        x2, y2, w2, h2 = box2
        
        # Calculate intersection
        x_left = max(x1, x2)
        y_top = max(y1, y2)
        x_right = min(x1 + w1, x2 + w2)
        y_bottom = min(y1 + h1, y2 + h2)
        
        if x_right < x_left or y_bottom < y_top:
            return 0.0
        
        intersection = (x_right - x_left) * (y_bottom - y_top)
        
        # Calculate union
        area1 = w1 * h1
        area2 = w2 * h2
        union = area1 + area2 - intersection
        
        if union == 0:
            return 0.0
        
        return intersection / union
    
    def visualize(
        self,
        image: np.ndarray,
        detections: List[SymbolDetection]
    ) -> np.ndarray:
        """
        Draw detected symbols on image.
        
        Args:
            image: Input image.
            detections: List of SymbolDetection objects.
        
        Returns:
            Image with drawn detections.
        """
        vis_image = image.copy()
        
        # Color map for different symbol types
        color_map = {
            SymbolType.WELDING.value: (0, 255, 0),  # Green
            SymbolType.SPOT_WELDING.value: (255, 0, 0),  # Blue
            SymbolType.SURFACE_FINISH.value: (0, 255, 255),  # Yellow
            SymbolType.GEOMETRIC_TOLERANCE.value: (255, 0, 255),  # Magenta
            SymbolType.UNKNOWN.value: (128, 128, 128)  # Gray
        }
        
        for detection in detections:
            x, y, w, h = detection.bbox
            color = color_map.get(detection.symbol_type, (255, 255, 255))
            
            # Draw rectangle
            cv2.rectangle(vis_image, (x, y), (x + w, y + h), color, 2)
            
            # Draw label
            label = f"{detection.symbol_type} ({detection.confidence:.2f})"
            label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            
            # Background
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
    
    def detect_from_file(
        self,
        image_path: str,
        confidence_threshold: float = 0.6
    ) -> List[SymbolDetection]:
        """
        Detect symbols from image file.
        
        Args:
            image_path: Path to image file.
            confidence_threshold: Minimum matching confidence.
        
        Returns:
            List of SymbolDetection objects.
        """
        if not Path(image_path).exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Failed to load image: {image_path}")
        
        return self.detect(image, confidence_threshold)


# Convenience function
def detect_symbols(image: np.ndarray) -> List[SymbolDetection]:
    """
    Quick symbol detection without creating detector object.
    
    Args:
        image: Input image.
    
    Returns:
        List of SymbolDetection objects.
    """
    detector = SymbolDetector()
    return detector.detect(image)
