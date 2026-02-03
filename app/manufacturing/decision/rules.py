"""
Decision Engine for Manufacturing Process Recognition.

Loads process_lib.json and scores each process based on extracted features
using rule-based logic and multimodal evidence fusion.
"""

import json
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path
import numpy as np

from ..schema import (
    ExtractedFeatures,
    ProcessDefinition,
    ProcessPrediction,
    OCRResult,
    SymbolDetection,
    GeometryFeatures
)


class DecisionEngine:
    """
    Rule-based decision engine for process recognition.
    
    Workflow:
    1. Load process definitions from process_lib.json
    2. For each process, calculate score based on:
       - Text matching (OCR results vs required_text)
       - Symbol matching (detected symbols vs required_symbols)
       - Geometry matching (detected features vs required_geometry)
       - Visual similarity (optional, via RAG)
    3. Fuse scores using weighted combination
    4. Return top-N predictions with evidence
    """
    
    def __init__(self, process_lib_path: Optional[str] = None):
        """
        Initialize decision engine.
        
        Args:
            process_lib_path: Path to process_lib.json.
                             If None, uses default location.
        """
        if process_lib_path is None:
            # Default location
            process_lib_path = Path(__file__).parent.parent / "process_lib.json"
        
        self.process_lib_path = Path(process_lib_path)
        self.processes: Dict[str, ProcessDefinition] = {}
        self.process_library: List[ProcessDefinition] = []  # Add public list attribute
        
        self._load_process_library()
    
    def _load_process_library(self):
        """Load process definitions from JSON."""
        if not self.process_lib_path.exists():
            raise FileNotFoundError(
                f"process_lib.json not found: {self.process_lib_path}"
            )
        
        with open(self.process_lib_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Handle both direct format and wrapped format
        if "processes" in data:
            process_dict = data["processes"]
        else:
            process_dict = data
        
        # Parse into ProcessDefinition objects
        for process_id, process_data in process_dict.items():
            process_def = ProcessDefinition(
                process_id=process_id,
                name=process_data["name"],
                category=process_data["category"],
                frequency=process_data.get("frequency", "中"),
                decision_factors=process_data.get("decision_factors", ""),
                required_text=process_data.get("required_text", []),
                required_symbols=process_data.get("required_symbols", []),
                required_geometry=process_data.get("required_geometry", []),
                confidence_weights=process_data.get("confidence_weights", {
                    "text": 0.4,
                    "symbol": 0.3,
                    "geometry": 0.2,
                    "visual": 0.1
                })
            )
            self.processes[process_id] = process_def
            self.process_library.append(process_def)  # Add to public list
    
    def predict(
        self,
        features: ExtractedFeatures,
        top_n: int = 5,
        min_confidence: float = 0.3
    ) -> List[ProcessPrediction]:
        """
        Predict manufacturing processes based on extracted features.
        
        Args:
            features: ExtractedFeatures object from extractors.
            top_n: Return top N predictions.
            min_confidence: Minimum confidence threshold (0.0-1.0).
        
        Returns:
            List of ProcessPrediction objects, sorted by confidence.
        """
        predictions = []
        
        for process_id, process_def in self.processes.items():
            # Calculate individual scores
            text_score = self._score_text_match(
                features.ocr_results,
                process_def.required_text
            )
            
            symbol_score = self._score_symbol_match(
                features.symbols,
                process_def.required_symbols
            )
            
            geometry_score = self._score_geometry_match(
                features.geometry,
                process_def.required_geometry
            )
            
            # Visual similarity (placeholder - will integrate with RAG later)
            visual_score = 0.5  # Neutral score
            
            # Weighted fusion
            weights = process_def.confidence_weights
            final_score = (
                text_score * weights.get("text", 0.4) +
                symbol_score * weights.get("symbol", 0.3) +
                geometry_score * weights.get("geometry", 0.2) +
                visual_score * weights.get("visual", 0.1)
            )
            
            # Collect evidence
            evidence = self._collect_evidence(
                process_def,
                features,
                text_score,
                symbol_score,
                geometry_score
            )
            
            # Create prediction
            if final_score >= min_confidence:
                predictions.append(ProcessPrediction(
                    process_id=process_id,
                    name=process_def.name,
                    confidence=float(final_score),
                    matched_text=[],
                    matched_symbols=[],
                    matched_geometry=[],
                    reasoning="\n".join(evidence)
                ))
        
        # Sort by confidence
        predictions.sort(key=lambda p: p.confidence, reverse=True)
        
        return predictions[:top_n]
    
    def _score_text_match(
        self,
        ocr_results: List[OCRResult],
        required_text: List[str]
    ) -> float:
        """
        Score text matching.
        
        Args:
            ocr_results: OCR detection results.
            required_text: List of required keywords.
        
        Returns:
            Score (0.0-1.0).
        """
        if not required_text:
            return 0.5  # Neutral score if no text requirement
        
        # Extract all detected text
        detected_texts = [result.text for result in ocr_results]
        
        # Check how many required keywords are found
        matches = 0
        for keyword in required_text:
            # Case-insensitive matching
            if any(keyword.lower() in text.lower() for text in detected_texts):
                matches += 1
        
        # Score = percentage of required keywords found
        if len(required_text) == 0:
            return 0.5
        
        return matches / len(required_text)
    
    def _score_symbol_match(
        self,
        symbols: List[SymbolDetection],
        required_symbols: List[str]
    ) -> float:
        """
        Score symbol matching.
        
        Args:
            symbols: Detected symbols.
            required_symbols: List of required symbol types.
        
        Returns:
            Score (0.0-1.0).
        """
        if not required_symbols:
            return 0.5  # Neutral score if no symbol requirement
        
        # Extract detected symbol types
        detected_types = [symbol.symbol_type for symbol in symbols]
        
        # Check how many required symbols are found
        matches = 0
        for required_type in required_symbols:
            if required_type in detected_types:
                matches += 1
        
        # Score = percentage of required symbols found
        if len(required_symbols) == 0:
            return 0.5
        
        return matches / len(required_symbols)
    
    def _score_geometry_match(
        self,
        geometry: Optional[GeometryFeatures],
        required_geometry: List[str]
    ) -> float:
        """
        Score geometry matching.
        
        Args:
            geometry: Detected geometry features.
            required_geometry: List of required geometric features.
        
        Returns:
            Score (0.0-1.0).
        """
        if not required_geometry or geometry is None:
            return 0.5  # Neutral score if no geometry requirement
        
        # Map requirement strings to feature checks
        feature_checks = {
            "bend_lines": len(geometry.bend_lines) > 0,
            "holes": len(geometry.holes) > 0,
            "circles": len(geometry.circles) > 0,
            "lines": len(geometry.lines) > 0,
            "complex_shapes": len(geometry.contours) > 5
        }
        
        # Check how many required features are present
        matches = 0
        for required_feature in required_geometry:
            if required_feature in feature_checks and feature_checks[required_feature]:
                matches += 1
        
        # Score = percentage of required geometry found
        if len(required_geometry) == 0:
            return 0.5
        
        return matches / len(required_geometry)
    
    def _collect_evidence(
        self,
        process_def: ProcessDefinition,
        features: ExtractedFeatures,
        text_score: float,
        symbol_score: float,
        geometry_score: float
    ) -> List[str]:
        """
        Collect human-readable evidence for prediction.
        
        Args:
            process_def: Process definition.
            features: Extracted features.
            text_score: Text matching score.
            symbol_score: Symbol matching score.
            geometry_score: Geometry matching score.
        
        Returns:
            List of evidence strings.
        """
        evidence = []
        
        # Text evidence
        if text_score > 0.5 and process_def.required_text:
            detected_keywords = [
                keyword for keyword in process_def.required_text
                if any(
                    keyword.lower() in result.text.lower()
                    for result in features.ocr_results
                )
            ]
            if detected_keywords:
                evidence.append(f"檢測到關鍵字: {', '.join(detected_keywords)}")
        
        # Symbol evidence
        if symbol_score > 0.5 and process_def.required_symbols:
            detected_symbols = [
                symbol.symbol_type
                for symbol in features.symbols
                if symbol.symbol_type in process_def.required_symbols
            ]
            if detected_symbols:
                evidence.append(f"檢測到符號: {', '.join(detected_symbols)}")
        
        # Geometry evidence
        if geometry_score > 0.5 and process_def.required_geometry and features.geometry:
            geo_evidence = []
            if "bend_lines" in process_def.required_geometry and features.geometry.bend_lines:
                geo_evidence.append(f"折彎線 ({len(features.geometry.bend_lines)}條)")
            if "holes" in process_def.required_geometry and features.geometry.holes:
                geo_evidence.append(f"孔洞 ({len(features.geometry.holes)}個)")
            if "circles" in process_def.required_geometry and features.geometry.circles:
                geo_evidence.append(f"圓形 ({len(features.geometry.circles)}個)")
            
            if geo_evidence:
                evidence.append(f"檢測到幾何特徵: {', '.join(geo_evidence)}")
        
        # If no evidence, add general statement
        if not evidence:
            evidence.append("基於視覺相似度推測")
        
        return evidence
    
    def get_process_by_id(self, process_id: str) -> Optional[ProcessDefinition]:
        """Get process definition by ID."""
        return self.processes.get(process_id)
    
    def get_all_processes(self) -> Dict[str, ProcessDefinition]:
        """Get all loaded process definitions."""
        return self.processes
    
    def get_processes_by_category(self, category: str) -> List[ProcessDefinition]:
        """Get all processes in a category."""
        return [
            process for process in self.processes.values()
            if process.category == category
        ]


# Convenience function
def predict_processes(
    features: ExtractedFeatures,
    top_n: int = 5
) -> List[ProcessPrediction]:
    """
    Quick process prediction without creating engine object.
    
    Args:
        features: ExtractedFeatures object.
        top_n: Return top N predictions.
    
    Returns:
        List of ProcessPrediction objects.
    """
    engine = DecisionEngine()
    return engine.predict(features, top_n)
