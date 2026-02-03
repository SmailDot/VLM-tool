"""
Geometry Extractor for Manufacturing Drawings.

Analyzes geometric primitives in engineering drawings using OpenCV:
- Lines (Hough transform) → Bend lines, cut lines
- Contours → Holes, circles, complex shapes
- Basic shape classification
"""

from typing import List, Tuple, Optional
import numpy as np
import cv2
from pathlib import Path

from ..schema import GeometryFeatures


class GeometryExtractor:
    """
    Extract geometric features from technical drawings.
    
    Analyzes:
    - Straight lines (potential bend lines, cut lines)
    - Circles/holes (drilling, countersink)
    - Rectangles/polygons (basic shapes)
    """
    
    def __init__(
        self,
        line_threshold: int = 100,
        min_line_length: int = 50,
        max_line_gap: int = 10,
        circle_param1: int = 50,
        circle_param2: int = 30
    ):
        """
        Initialize geometry extractor.
        
        Args:
            line_threshold: Hough line detection threshold (votes).
            min_line_length: Minimum line length in pixels.
            max_line_gap: Maximum gap between line segments.
            circle_param1: Canny high threshold for circle detection.
            circle_param2: Accumulator threshold for circle detection.
        """
        self.line_threshold = line_threshold
        self.min_line_length = min_line_length
        self.max_line_gap = max_line_gap
        self.circle_param1 = circle_param1
        self.circle_param2 = circle_param2
    
    def extract(
        self,
        image: np.ndarray,
        min_contour_area: int = 100,
        ocr_results: Optional[List] = None
    ) -> GeometryFeatures:
        """
        Extract geometric features from engineering drawing.
        
        Args:
            image: Input image (BGR or grayscale).
            min_contour_area: Minimum contour area to consider.
            ocr_results: Optional OCR results for filtering dimension lines.
        
        Returns:
            GeometryFeatures object with detected primitives.
        """
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # Edge detection
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        
        # Extract lines
        all_lines = self._detect_lines(edges)
        
        # Filter out dimension/auxiliary lines (NEW!)
        lines = self._filter_auxiliary_lines(all_lines, gray.shape, ocr_results)
        
        # Classify bend lines from filtered part lines
        bend_lines = self._classify_bend_lines(lines, gray.shape)
        
        # Extract circles/holes
        circles = self._detect_circles(gray)
        holes = self._classify_holes(circles)
        
        # Extract contours
        contours, _ = cv2.findContours(
            edges,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        # Filter by area
        valid_contours = [
            c for c in contours
            if cv2.contourArea(c) >= min_contour_area
        ]
        
        # Count total primitive shapes
        total_shapes = len(valid_contours)
        
        # Create contour data for GeometryFeatures
        contour_data = [
            {
                'points': c.tolist(),
                'area': float(cv2.contourArea(c)),
                'perimeter': float(cv2.arcLength(c, True))
            }
            for c in valid_contours
        ]
        
        # Convert tuples to dicts for schema compatibility
        lines_data = [
            {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2}
            for x1, y1, x2, y2 in lines
        ]
        bend_lines_data = [
            {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2}
            for x1, y1, x2, y2 in bend_lines
        ]
        holes_data = [
            {'x': x, 'y': y, 'radius': r}
            for x, y, r in holes
        ]
        circles_data = [
            {'x': x, 'y': y, 'radius': r}
            for x, y, r in circles
        ]
        
        return GeometryFeatures(
            lines=lines_data,
            bend_lines=bend_lines_data,
            holes=holes_data,
            circles=circles_data,
            contours=contour_data
        )
    
    def _detect_lines(self, edges: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        Detect straight lines using Hough transform.
        
        Args:
            edges: Edge-detected image.
        
        Returns:
            List of lines as (x1, y1, x2, y2).
        """
        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=self.line_threshold,
            minLineLength=self.min_line_length,
            maxLineGap=self.max_line_gap
        )
        
        if lines is None:
            return []
        
        # Convert to simple format
        result = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            result.append((int(x1), int(y1), int(x2), int(y2)))
        
        return result
    
    def _classify_bend_lines(
        self,
        lines: List[Tuple[int, int, int, int]],
        image_shape: Tuple[int, int]
    ) -> List[Tuple[int, int, int, int]]:
        """
        Classify potential bend lines.
        
        Bend lines are typically:
        - Dashed lines
        - Center lines (long, horizontal/vertical)
        - Symmetry axes
        
        Args:
            lines: Detected lines.
            image_shape: Image (height, width).
        
        Returns:
            List of bend lines as (x1, y1, x2, y2).
        """
        height, width = image_shape
        bend_lines = []
        
        for x1, y1, x2, y2 in lines:
            # Calculate line length
            length = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
            
            # Calculate angle (0-180 degrees)
            angle = np.abs(np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi)
            
            # Check if horizontal or vertical
            is_horizontal = angle < 10 or angle > 170
            is_vertical = 80 < angle < 100
            
            # Heuristic: Long horizontal/vertical lines in center region
            # These are often bend indicators or symmetry lines
            if (is_horizontal or is_vertical) and length > min(width, height) * 0.3:
                bend_lines.append((x1, y1, x2, y2))
        
        return bend_lines
    
    def _detect_circles(self, gray: np.ndarray) -> List[Tuple[int, int, int]]:
        """
        Detect circles using Hough Circle Transform.
        
        Args:
            gray: Grayscale image.
        
        Returns:
            List of circles as (x, y, radius).
        """
        circles = cv2.HoughCircles(
            gray,
            cv2.HOUGH_GRADIENT,
            dp=1,
            minDist=20,
            param1=self.circle_param1,
            param2=self.circle_param2,
            minRadius=5,
            maxRadius=200
        )
        
        if circles is None:
            return []
        
        # Convert to integer
        circles = np.uint16(np.around(circles))
        
        result = []
        for circle in circles[0, :]:
            x, y, r = circle
            result.append((int(x), int(y), int(r)))
        
        return result
    
    def _classify_holes(
        self,
        circles: List[Tuple[int, int, int]]
    ) -> List[Tuple[int, int, int]]:
        """
        Classify potential holes (drilling points).
        
        Holes are typically:
        - Small to medium circles
        - Clear boundaries
        - Not too large (excludes large arcs)
        
        Args:
            circles: Detected circles.
        
        Returns:
            List of holes as (x, y, radius).
        """
        holes = []
        
        for x, y, r in circles:
            # Heuristic: Holes are typically 5-50 pixels radius
            # (This depends on drawing scale, may need calibration)
            if 5 <= r <= 50:
                holes.append((x, y, r))
        
        return holes
    
    def _filter_auxiliary_lines(
        self,
        lines: List[Tuple[int, int, int, int]],
        image_shape: Tuple[int, int],
        ocr_results: Optional[List] = None
    ) -> List[Tuple[int, int, int, int]]:
        """
        過濾尺寸輔助線，保留零件實線
        
        策略:
        1. 檢查線條附近是否有尺寸數字（OCR）
        2. 檢查線條是否在圖紙邊緣外側
        3. 檢查線條長度是否異常（跨越整個圖紙）
        
        Args:
            lines: Detected lines.
            image_shape: Image (height, width).
            ocr_results: Optional OCR results for filtering.
        
        Returns:
            Filtered list of part lines (excluding dimension lines).
        """
        if not lines:
            return []
        
        height, width = image_shape
        part_lines = []
        
        for line in lines:
            x1, y1, x2, y2 = line
            length = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
            
            # 過濾條件 1: 異常長度（跨越 >80% 圖紙寬度/高度）
            # 這通常是總長度標註線
            if length > min(width, height) * 0.8:
                continue  # 跳過
            
            # 過濾條件 2: 檢查是否在邊緣區域且有附近文字
            margin = 50  # 邊緣容忍度（像素）
            in_edge_region = (
                x1 < margin or x1 > width - margin or 
                x2 < margin or x2 > width - margin or
                y1 < margin or y1 > height - margin or 
                y2 < margin or y2 > height - margin
            )
            
            if in_edge_region and ocr_results:
                # 在邊緣區域，檢查是否有附近尺寸文字
                if self._has_nearby_dimension_text(line, ocr_results):
                    continue  # 有尺寸標註 → 輔助線，跳過
            
            # 過濾條件 3: 非常短的線（可能是箭頭端點）
            if length < 10:
                continue  # 跳過過短線段
            
            # 通過過濾 → 保留為零件線
            part_lines.append(line)
        
        return part_lines
    
    def _has_nearby_dimension_text(
        self,
        line: Tuple[int, int, int, int],
        ocr_results: List,
        distance_threshold: int = 30
    ) -> bool:
        """
        檢查線條附近是否有尺寸數字
        
        Args:
            line: Line coordinates (x1, y1, x2, y2).
            ocr_results: List of OCR results.
            distance_threshold: Maximum distance to consider (pixels).
        
        Returns:
            True if dimension text found nearby.
        """
        import re
        
        x1, y1, x2, y2 = line
        line_center = ((x1 + x2) / 2, (y1 + y2) / 2)
        
        for ocr in ocr_results:
            # 檢查是否為數字文字 (包含常見尺寸標註)
            text = ocr.text.strip()
            
            # 匹配尺寸標註模式:
            # - 純數字: "150", "20.5"
            # - 直徑符號: "φ20", "Φ30"
            # - 半徑符號: "R10", "r5"
            # - 螺紋: "M6", "M8"
            # - 角度: "45°", "90°"
            dimension_pattern = r'[\d.]+|φ\d+|Φ\d+|R\d+|r\d+|M\d+|\d+°'
            
            if re.search(dimension_pattern, text):
                # 計算到線條中心的距離
                if hasattr(ocr, 'bbox') and ocr.bbox:
                    # bbox format: [x, y, w, h]
                    ocr_center_x = ocr.bbox[0] + ocr.bbox[2] / 2
                    ocr_center_y = ocr.bbox[1] + ocr.bbox[3] / 2
                    
                    distance = np.sqrt(
                        (line_center[0] - ocr_center_x)**2 + 
                        (line_center[1] - ocr_center_y)**2
                    )
                    
                    if distance < distance_threshold:
                        return True
        
        return False
    
    def visualize(
        self,
        image: np.ndarray,
        features: GeometryFeatures,
        show_lines: bool = True,
        show_bend_lines: bool = True,
        show_circles: bool = True,
        show_holes: bool = True
    ) -> np.ndarray:
        """
        Visualize detected geometry features.
        
        Args:
            image: Input image.
            features: GeometryFeatures object.
            show_lines: Draw detected lines.
            show_bend_lines: Draw classified bend lines.
            show_circles: Draw detected circles.
            show_holes: Draw classified holes.
        
        Returns:
            Image with drawn features.
        """
        vis_image = image.copy()
        
        # Draw all lines (gray)
        if show_lines:
            for line in features.lines:
                x1, y1, x2, y2 = line['x1'], line['y1'], line['x2'], line['y2']
                cv2.line(vis_image, (x1, y1), (x2, y2), (128, 128, 128), 1)
        
        # Draw bend lines (green, thicker)
        if show_bend_lines:
            for line in features.bend_lines:
                x1, y1, x2, y2 = line['x1'], line['y1'], line['x2'], line['y2']
                cv2.line(vis_image, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(
                    vis_image,
                    "BEND",
                    (x1, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.4,
                    (0, 255, 0),
                    1
                )
        
        # Draw all circles (blue)
        if show_circles:
            for circle in features.circles:
                x, y, r = circle['x'], circle['y'], circle['radius']
                cv2.circle(vis_image, (x, y), r, (255, 0, 0), 1)
                cv2.circle(vis_image, (x, y), 2, (255, 0, 0), -1)
        
        # Draw holes (red, thicker)
        if show_holes:
            for hole in features.holes:
                x, y, r = hole['x'], hole['y'], hole['radius']
                cv2.circle(vis_image, (x, y), r, (0, 0, 255), 2)
                cv2.putText(
                    vis_image,
                    "HOLE",
                    (x, y - r - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.4,
                    (0, 0, 255),
                    1
                )
        
        return vis_image
    
    def extract_from_file(
        self,
        image_path: str,
        min_contour_area: int = 100
    ) -> GeometryFeatures:
        """
        Extract geometry features from image file.
        
        Args:
            image_path: Path to image file.
            min_contour_area: Minimum contour area to consider.
        
        Returns:
            GeometryFeatures object.
        """
        if not Path(image_path).exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Failed to load image: {image_path}")
        
        return self.extract(image, min_contour_area)


# Convenience function
def extract_geometry(image: np.ndarray) -> GeometryFeatures:
    """
    Quick geometry extraction without creating extractor object.
    
    Args:
        image: Input image.
    
    Returns:
        GeometryFeatures object.
    """
    extractor = GeometryExtractor()
    return extractor.extract(image)
