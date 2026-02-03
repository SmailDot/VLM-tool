"""
Tolerance Parser for Engineering Drawings.

Extracts tolerance specifications from OCR text to guide manufacturing process selection.
Tolerance values indicate required manufacturing precision and influence process choices.

Patterns supported:
- Symmetric: ±0.3, ±0.05, ± 0.02
- Asymmetric: +0.3/-0.2, +0.05/-0.03
- Implied: 0.05 (when context suggests tolerance)
"""

from typing import List, Optional, Tuple
import re
from dataclasses import dataclass

from ..schema import OCRResult


@dataclass
class ToleranceSpec:
    """
    Tolerance specification extracted from drawing.
    
    Attributes:
        value: Tolerance value in mm (always positive, represents ± range)
        text: Original text string (e.g., "±0.05", "+0.3/-0.2")
        bbox: Bounding box [x, y, w, h] if available
        tolerance_type: Type of tolerance ("symmetric", "asymmetric", "implied")
        upper_value: Upper tolerance (for asymmetric tolerances)
        lower_value: Lower tolerance (for asymmetric tolerances)
    """
    value: float  # Main tolerance value (mm)
    text: str  # Original text
    bbox: Optional[List[int]] = None  # [x, y, w, h]
    tolerance_type: str = "symmetric"  # "symmetric", "asymmetric", "implied"
    upper_value: Optional[float] = None  # For asymmetric: +0.3
    lower_value: Optional[float] = None  # For asymmetric: -0.2
    
    def get_max_tolerance(self) -> float:
        """Get maximum tolerance value (worst case)"""
        if self.tolerance_type == "asymmetric":
            return max(abs(self.upper_value or 0), abs(self.lower_value or 0))
        return self.value
    
    def is_tight_tolerance(self, threshold: float = 0.1) -> bool:
        """Check if tolerance requires high precision manufacturing"""
        return self.get_max_tolerance() < threshold


class ToleranceParser:
    """
    Extract tolerance specifications from OCR results.
    
    Tolerances indicate manufacturing precision requirements:
    - ±0.3mm or larger: Standard precision (laser cutting OK)
    - ±0.1mm to ±0.05mm: Medium precision (careful machining)
    - ±0.05mm or tighter: High precision (milling/cutting required)
    """
    
    # Regex patterns for tolerance detection
    PATTERNS = {
        # Symmetric tolerances: ±0.3, ± 0.05, ±0.02
        'symmetric': [
            r'[±]\s*(\d+\.?\d*)',  # ±0.3, ± 0.05
            r'[+]\s*(\d+\.?\d*)\s*/\s*[-]\s*(\d+\.?\d*)',  # +0.3/-0.3 (equal)
        ],
        # Asymmetric tolerances: +0.3/-0.2, +0.05/-0.03
        'asymmetric': [
            r'[+]\s*(\d+\.?\d*)\s*/\s*[-]\s*(\d+\.?\d*)',  # +0.3/-0.2
        ],
        # Contextual tolerance: "0.05" near dimension
        'implied': [
            r'^\s*(\d+\.?\d{2,})\s*$',  # 0.05, 0.02 (2+ decimals suggests tolerance)
        ],
    }
    
    def __init__(self, min_tolerance: float = 0.01, max_tolerance: float = 5.0):
        """
        Initialize tolerance parser.
        
        Args:
            min_tolerance: Minimum valid tolerance value (mm)
            max_tolerance: Maximum valid tolerance value (mm)
        """
        self.min_tolerance = min_tolerance
        self.max_tolerance = max_tolerance
        
        # Compile regex patterns
        self.compiled_patterns = {
            tol_type: [re.compile(pattern) for pattern in patterns]
            for tol_type, patterns in self.PATTERNS.items()
        }
    
    def extract_tolerances(self, ocr_results: List[OCRResult]) -> List[ToleranceSpec]:
        """
        Extract all tolerance specifications from OCR results.
        
        Args:
            ocr_results: List of OCR text detections
        
        Returns:
            List of ToleranceSpec objects (sorted by value, tightest first)
        """
        tolerances = []
        
        for ocr in ocr_results:
            text = ocr.text.strip()
            
            # Try each tolerance type
            tol_spec = self._parse_tolerance_text(text, ocr.bbox)
            if tol_spec:
                tolerances.append(tol_spec)
        
        # Sort by tolerance value (tightest first)
        tolerances.sort(key=lambda t: t.get_max_tolerance())
        
        return tolerances
    
    def _parse_tolerance_text(
        self, 
        text: str, 
        bbox: Optional[List[int]] = None
    ) -> Optional[ToleranceSpec]:
        """
        Parse tolerance from single OCR text.
        
        Args:
            text: OCR text string
            bbox: Bounding box [x, y, w, h]
        
        Returns:
            ToleranceSpec if valid tolerance found, None otherwise
        """
        # Try symmetric tolerance patterns
        for pattern in self.compiled_patterns['symmetric']:
            match = pattern.search(text)
            if match:
                try:
                    value = float(match.group(1))
                    if self._is_valid_tolerance(value):
                        return ToleranceSpec(
                            value=value,
                            text=text,
                            bbox=bbox,
                            tolerance_type="symmetric"
                        )
                except (ValueError, IndexError):
                    continue
        
        # Try asymmetric tolerance patterns
        for pattern in self.compiled_patterns['asymmetric']:
            match = pattern.search(text)
            if match:
                try:
                    upper = float(match.group(1))
                    lower = float(match.group(2))
                    
                    # Check if both values are valid
                    if self._is_valid_tolerance(upper) and self._is_valid_tolerance(lower):
                        # Check if they're equal (actually symmetric)
                        if abs(upper - lower) < 0.001:
                            return ToleranceSpec(
                                value=upper,
                                text=text,
                                bbox=bbox,
                                tolerance_type="symmetric"
                            )
                        else:
                            # True asymmetric tolerance
                            max_tol = max(upper, lower)
                            return ToleranceSpec(
                                value=max_tol,
                                text=text,
                                bbox=bbox,
                                tolerance_type="asymmetric",
                                upper_value=upper,
                                lower_value=lower
                            )
                except (ValueError, IndexError):
                    continue
        
        # Try implied tolerance patterns (more restrictive)
        # Only consider if value looks like a tolerance (2+ decimal places)
        for pattern in self.compiled_patterns['implied']:
            match = pattern.search(text)
            if match:
                try:
                    value = float(match.group(1))
                    # Implied tolerances should be small values
                    if self._is_valid_tolerance(value) and value < 1.0:
                        return ToleranceSpec(
                            value=value,
                            text=text,
                            bbox=bbox,
                            tolerance_type="implied"
                        )
                except (ValueError, IndexError):
                    continue
        
        return None
    
    def _is_valid_tolerance(self, value: float) -> bool:
        """
        Check if tolerance value is within valid range.
        
        Args:
            value: Tolerance value to check
        
        Returns:
            True if valid, False otherwise
        """
        return self.min_tolerance <= value <= self.max_tolerance
    
    def get_tightest_tolerance(
        self, 
        tolerances: List[ToleranceSpec]
    ) -> Optional[ToleranceSpec]:
        """
        Get the tightest (smallest) tolerance from list.
        
        Args:
            tolerances: List of tolerance specifications
        
        Returns:
            ToleranceSpec with smallest value, or None if list is empty
        """
        if not tolerances:
            return None
        
        return min(tolerances, key=lambda t: t.get_max_tolerance())
    
    def requires_precision_machining(
        self, 
        tolerances: List[ToleranceSpec],
        threshold: float = 0.1
    ) -> bool:
        """
        Check if any tolerance requires precision machining (cutting/milling).
        
        Args:
            tolerances: List of tolerance specifications
            threshold: Precision threshold in mm (default: 0.1mm)
        
        Returns:
            True if precision machining required
        """
        if not tolerances:
            return False
        
        tightest = self.get_tightest_tolerance(tolerances)
        return tightest.is_tight_tolerance(threshold)
    
    def get_precision_summary(
        self, 
        tolerances: List[ToleranceSpec]
    ) -> dict:
        """
        Get summary of precision requirements.
        
        Args:
            tolerances: List of tolerance specifications
        
        Returns:
            Dictionary with precision analysis:
            - tightest_tolerance: Smallest tolerance value
            - requires_precision: Boolean flag
            - tolerance_count: Number of tolerances found
            - precision_category: "high" (<0.1mm), "medium" (0.1-0.3mm), "standard" (>0.3mm)
        """
        if not tolerances:
            return {
                'tightest_tolerance': None,
                'requires_precision': False,
                'tolerance_count': 0,
                'precision_category': 'standard'
            }
        
        tightest = self.get_tightest_tolerance(tolerances)
        tightest_value = tightest.get_max_tolerance()
        
        # Categorize precision
        if tightest_value < 0.1:
            category = "high"
        elif tightest_value < 0.3:
            category = "medium"
        else:
            category = "standard"
        
        return {
            'tightest_tolerance': tightest_value,
            'requires_precision': tightest_value < 0.1,
            'tolerance_count': len(tolerances),
            'precision_category': category,
            'tightest_spec': tightest
        }


# Convenience function
def extract_tolerances_from_ocr(ocr_results: List[OCRResult]) -> List[ToleranceSpec]:
    """
    Quick tolerance extraction without creating parser object.
    
    Args:
        ocr_results: List of OCR results
    
    Returns:
        List of ToleranceSpec objects
    """
    parser = ToleranceParser()
    return parser.extract_tolerances(ocr_results)
