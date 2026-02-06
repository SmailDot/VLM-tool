"""
Manufacturing Process Recognition - Data Schemas
製程辨識系統 - 資料結構定義

Defines dataclasses for:
- Features: Extracted features from engineering drawings
- Case: Knowledge base case record
- Prediction: Process recognition result
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, TYPE_CHECKING
from enum import Enum
import numpy as np

if TYPE_CHECKING:
    from .extractors.parent_parser import ParentImageContext


class FeatureType(Enum):
    """Feature type enumeration"""
    VISUAL = "visual"  # 圖像特徵 (embeddings, geometry)
    TEXT = "text"      # 文字特徵 (OCR tokens)
    SYMBOL = "symbol"  # 符號特徵 (welding, surface finish, etc.)
    GEOMETRY = "geometry"  # 幾何特徵 (lines, holes, bends)


class ProcessCategory(Enum):
    """Manufacturing process categories"""
    CUTTING = "切割"      # B, C: Cutting operations
    BENDING = "折彎"      # D: Bending operations
    FINISHING = "表面處理"  # E: Deburring, polishing, etc.
    WELDING = "焊接"      # F: Welding operations
    CLEANING = "清潔"     # H: Cleaning operations
    INSPECTION = "檢驗"   # I: Quality inspection
    ASSEMBLY = "組裝"     # Q: Assembly operations
    OTHER = "其他"       # O, P, K, J: Other operations


@dataclass
class OCRResult:
    """OCR extraction result"""
    text: str                    # Raw text
    confidence: float           # OCR confidence (0-1)
    bbox: Optional[List[int]] = None  # [x, y, w, h]
    normalized_text: str = ""   # Cleaned/normalized text
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional metadata (e.g., language)
    
    def __post_init__(self):
        if not self.normalized_text:
            # Auto-normalize: remove whitespace, lowercase
            self.normalized_text = self.text.strip().lower()


@dataclass
class SymbolDetection:
    """Symbol detection result"""
    symbol_type: str             # e.g., "welding", "surface_finish", "spot"
    label: str                   # Specific label (e.g., "weld_fillet", "m3_hole")
    confidence: float           # Detection confidence (0-1)
    bbox: Optional[List[int]] = None  # [x, y, w, h]
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional info


@dataclass
class GeometryFeatures:
    """Geometric features extracted from drawing"""
    lines: List[Dict] = field(default_factory=list)        # Hough lines
    circles: List[Dict] = field(default_factory=list)      # Detected circles
    contours: List[Dict] = field(default_factory=list)     # Contours
    holes: List[Dict] = field(default_factory=list)        # Hole patterns
    bend_lines: List[Dict] = field(default_factory=list)   # Potential bend lines
    
    @property
    def has_bends(self) -> bool:
        """Check if drawing likely has bending features"""
        return len(self.bend_lines) > 0
    
    @property
    def hole_count(self) -> int:
        """Total number of detected holes"""
        return len(self.holes)


@dataclass
class ExtractedFeatures:
    """
    Complete features extracted from an engineering drawing
    完整的圖紙特徵
    """
    # Visual embeddings
    visual_embedding: Optional[np.ndarray] = None  # DINOv2/CLIP (512 or 768 dim)
    
    # Text features
    ocr_results: List[OCRResult] = field(default_factory=list)
    text_embedding: Optional[np.ndarray] = None  # CLIP text embedding
    
    # Symbol detections
    symbols: List[SymbolDetection] = field(default_factory=list)
    
    # Geometry
    geometry: GeometryFeatures = field(default_factory=GeometryFeatures)
    
    # Tolerances (NEW)
    tolerances: List[Any] = field(default_factory=list)  # List[ToleranceSpec] - Any to avoid circular import
    
    # VLM Analysis (NEW - Vision Language Model)
    vlm_analysis: Optional[Dict[str, Any]] = None  # VLM-based process recognition result
    
    # Metadata
    image_shape: Optional[tuple] = None  # (H, W, C)
    extraction_time: float = 0.0  # seconds
    
    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dict"""
        return {
            "visual_embedding": self.visual_embedding.tolist() if self.visual_embedding is not None else None,
            "text_embedding": self.text_embedding.tolist() if self.text_embedding is not None else None,
            "ocr_results": [
                {
                    "text": ocr.text,
                    "confidence": ocr.confidence,
                    "bbox": ocr.bbox,
                    "normalized": ocr.normalized_text
                }
                for ocr in self.ocr_results
            ],
            "symbols": [
                {
                    "type": sym.symbol_type,
                    "label": sym.label,
                    "confidence": sym.confidence,
                    "bbox": sym.bbox,
                    "metadata": sym.metadata
                }
                for sym in self.symbols
            ],
            "geometry": {
                "lines": self.geometry.lines if self.geometry else [],
                "circles": self.geometry.circles if self.geometry else [],
                "contours": self.geometry.contours if self.geometry else [],
                "holes": self.geometry.holes if self.geometry else [],
                "bend_lines": self.geometry.bend_lines if self.geometry else []
            },
            "tolerances": [
                {
                    "value": tol.value,
                    "text": tol.text,
                    "bbox": tol.bbox,
                    "tolerance_type": tol.tolerance_type,
                    "upper_value": tol.upper_value,
                    "lower_value": tol.lower_value
                }
                for tol in self.tolerances
            ],
            "vlm_analysis": self.vlm_analysis,
            "image_shape": self.image_shape,
            "extraction_time": self.extraction_time
        }


@dataclass
class ProcessDefinition:
    """
    Manufacturing process definition (from process_lib.json)
    製程定義
    """
    process_id: str              # e.g., "D01", "F01"
    name: str                    # e.g., "折彎", "焊接"
    category: ProcessCategory
    frequency: str               # "低", "中", "高"
    
    # Decision factors (決定性因素)
    decision_factors: str = ""
    
    # Required cues (必要線索)
    required_text: List[str] = field(default_factory=list)      # Text tokens that indicate this process
    required_symbols: List[str] = field(default_factory=list)   # Symbol types needed
    required_geometry: List[str] = field(default_factory=list)  # Geometry flags (e.g., "holes", "bend_lines")
    
    # Exclusions (排除條件)
    excludes: List[str] = field(default_factory=list)  # Processes that exclude this one
    
    # Weights for scoring
    confidence_weights: Dict[str, float] = field(default_factory=lambda: {
        "text": 0.4,
        "symbol": 0.3,
        "geometry": 0.2,
        "visual": 0.1
    })
    
    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dict"""
        return {
            "process_id": self.process_id,
            "name": self.name,
            "category": self.category.value,
            "frequency": self.frequency,
            "decision_factors": self.decision_factors,
            "required_text": self.required_text,
            "required_symbols": self.required_symbols,
            "required_geometry": self.required_geometry,
            "excludes": self.excludes,
            "confidence_weights": self.confidence_weights
        }


@dataclass
class ManufacturingCase:
    """
    Knowledge base case for manufacturing process recognition
    製程辨識知識庫案例
    """
    case_id: str
    description: str
    
    # Raw data
    image_path: str
    
    # Extracted features
    features: ExtractedFeatures
    
    # Ground truth labels
    confirmed_processes: List[str]  # Process IDs (e.g., ["D01", "F01"])
    
    # Metadata
    author: str = "Unknown"
    created_at: str = ""
    notes: str = ""
    
    # User feedback
    user_confirmed: bool = False
    correction_notes: str = ""
    
    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dict"""
        return {
            "case_id": self.case_id,
            "description": self.description,
            "image_path": self.image_path,
            "features": self.features.to_dict(),
            "confirmed_processes": self.confirmed_processes,
            "author": self.author,
            "created_at": self.created_at,
            "notes": self.notes,
            "user_confirmed": self.user_confirmed,
            "correction_notes": self.correction_notes
        }


@dataclass
class ProcessPrediction:
    """
    Process recognition prediction result
    製程辨識預測結果
    """
    process_id: str
    name: str
    confidence: float  # 0-1
    
    # Evidence (證據)
    matched_text: List[str] = field(default_factory=list)
    matched_symbols: List[str] = field(default_factory=list)
    matched_geometry: List[str] = field(default_factory=list)
    similar_cases: List[str] = field(default_factory=list)  # Case IDs
    
    # Explanation
    reasoning: str = ""
    
    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dict"""
        return {
            "process_id": self.process_id,
            "name": self.name,
            "confidence": self.confidence,
            "evidence": {
                "text": self.matched_text,
                "symbols": self.matched_symbols,
                "geometry": self.matched_geometry,
                "similar_cases": self.similar_cases
            },
            "reasoning": self.reasoning
        }


@dataclass
class RecognitionResult:
    """
    Complete recognition result for one drawing
    完整辨識結果
    """
    predictions: List[ProcessPrediction]
    features: ExtractedFeatures
    
    # Parent context (optional, if dual-image mode)
    parent_context: Optional['ParentImageContext'] = None
    
    # Timing
    total_time: float = 0.0  # seconds
    
    # Diagnostics
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dict"""
        result = {
            "predictions": [p.to_dict() for p in self.predictions],
            "features": self.features.to_dict(),
            "total_time": self.total_time,
            "warnings": self.warnings,
            "errors": self.errors
        }
        
        # Add parent_context if available
        if self.parent_context:
            result["parent_context"] = {
                "material": self.parent_context.material,
                "thickness": self.parent_context.thickness,
                "customer": self.parent_context.customer,
                "cleanroom_level": self.parent_context.cleanroom_level,
                "surface_treatment": self.parent_context.surface_treatment,
                "special_requirements": self.parent_context.special_requirements,
                "detected_keywords": list(self.parent_context.detected_keywords),
                "triggered_processes": self.parent_context.triggered_processes,
                # NEW: 注意事項
                "important_notes": self.parent_context.important_notes if hasattr(self.parent_context, 'important_notes') else [],
                "title_block_text": self.parent_context.title_block_text if hasattr(self.parent_context, 'title_block_text') else [],
                "detected_languages": list(self.parent_context.detected_languages) if hasattr(self.parent_context, 'detected_languages') else []
            }
        
        return result
    
    def get_top_n(self, n: int = 5, min_confidence: float = 0.3) -> List[ProcessPrediction]:
        """Get top N predictions above confidence threshold"""
        filtered = [p for p in self.predictions if p.confidence >= min_confidence]
        return sorted(filtered, key=lambda x: x.confidence, reverse=True)[:n]
