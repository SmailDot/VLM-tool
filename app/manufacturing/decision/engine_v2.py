"""
Enhanced Decision Engine V2 for Manufacturing Process Recognition.

Supports:
- Process library v2 format
- Frequency filtering
- Logic rules (replacement, auto-complete, exclusion)
- Region-based scanning (future)
"""

import json
from typing import List, Dict, Any, Tuple, Optional, Set, Union
from pathlib import Path
import numpy as np
import random

from ..schema import (
    ExtractedFeatures,
    ProcessPrediction,
    OCRResult,
    SymbolDetection,
    GeometryFeatures
)
from ..extractors.parent_parser import ParentImageContext


class DecisionEngineV2:
    """
    Enhanced rule-based decision engine with logic reconciliation.
    
    New Features:
    - Frequency filtering (高/中/低/無)
    - Replacement rules (D04 → D01)
    - Auto-complete rules (H34 → H33)
    - Conflict resolution (C05 vs C01)
    """
    
    def __init__(self, process_lib_path: Optional[Union[str, Path]] = None):
        """
        Initialize enhanced decision engine.
        
        Args:
            process_lib_path: Path to process_lib_v2.json.
                             If None, tries v2 then falls back to v1.
        """
        process_lib_path_path: Path

        if process_lib_path is None:
            # Try v2 first, fallback to v1
            v2_path = Path(__file__).parent.parent / "process_lib_v2.json"
            v1_path = Path(__file__).parent.parent / "process_lib.json"

            if v2_path.exists():
                process_lib_path_path = v2_path
                self.version = "2.0"
            elif v1_path.exists():
                process_lib_path_path = v1_path
                self.version = "1.0"
            else:
                raise FileNotFoundError("No process library found")
        else:
            process_lib_path_path = Path(process_lib_path)
            self.version = "2.0" if "v2" in str(process_lib_path_path) else "1.0"

        self.process_lib_path: Path = process_lib_path_path
        self.processes: Dict[str, Dict] = {}
        self.process_library: List[Dict] = []
        
        self._load_process_library()
    
    def _load_process_library(self):
        """Load process definitions from JSON."""
        if not self.process_lib_path.exists():
            raise FileNotFoundError(
                f"Process library not found: {self.process_lib_path}"
            )
        
        with self.process_lib_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Handle both direct format and wrapped format
        if "processes" in data:
            process_dict = data["processes"]
        else:
            process_dict = data
        
        # Store raw process data (v2 has more fields)
        for process_id, process_data in process_dict.items():
            self.processes[process_id] = process_data
            self.process_library.append(process_data)
    
    @property
    def total_processes(self) -> int:
        """Get total number of processes in the library."""
        return len(self.processes)
    
    def predict(
        self,
        features: ExtractedFeatures,
        parent_context: Optional[ParentImageContext] = None,
        top_n: Optional[int] = None,
        min_confidence: float = 0.3,
        frequency_filter: Optional[List[str]] = None
    ) -> List[ProcessPrediction]:
        """
        Predict manufacturing processes with logic reconciliation.
        
        Args:
            features: Extracted features from child drawing.
            parent_context: Optional parent image context (global information).
            top_n: Return top N predictions. If None, return all above threshold.
            min_confidence: Minimum confidence threshold.
            frequency_filter: Filter by frequency (e.g., ["高", "中"]).
                            If None, returns all frequencies.
        
        Returns:
            List of ProcessPrediction objects, sorted by confidence.
        """
        # Step 1: Get processes triggered by parent image (if any)
        parent_processes = []
        if parent_context and parent_context.triggered_processes:
            parent_processes = self._create_parent_predictions(parent_context)
        
        # Step 2: Score processes based on child image features
        child_candidates = self._score_all_processes(features, frequency_filter)
        
        # Step 3: Merge parent + child predictions
        candidates = self._merge_predictions(parent_processes, child_candidates)
        
        # Step 4: Apply logic rules (v2 only)
        if self.version == "2.0":
            candidates = self._apply_logic_rules(candidates, features, parent_context)
        
        # Step 5: Filter by confidence and limit
        predictions = [
            c for c in candidates
            if c.confidence >= min_confidence
        ]
        
        if top_n is None:
            return predictions
        return predictions[:top_n]
    
    def _create_parent_predictions(
        self,
        parent_context: ParentImageContext
    ) -> List[ProcessPrediction]:
        """
        Create predictions for processes triggered by parent image.
        These are given high confidence (0.85) since they come from explicit global info.
        """
        predictions = []
        
        for process_id in parent_context.triggered_processes:
            process_def = self.processes.get(process_id)
            if not process_def:
                continue
            
            # Build reasoning from parent context
            reasoning_parts = ["[父圖觸發] 由父圖全域資訊觸發"]
            
            if parent_context.material:
                reasoning_parts.append(f"材質: {parent_context.material}")
            if parent_context.customer:
                reasoning_parts.append(f"客戶: {parent_context.customer}")
            if parent_context.cleanroom_level:
                reasoning_parts.append("檢測到無塵室要求")
            if parent_context.surface_treatment:
                reasoning_parts.append(f"表面處理: {', '.join(parent_context.surface_treatment)}")
            if parent_context.special_requirements:
                reasoning_parts.append(f"特殊要求: {', '.join(parent_context.special_requirements)}")
            
            prediction = ProcessPrediction(
                process_id=process_id,
                name=process_def["name"],
                confidence=0.85,  # High confidence for parent-triggered processes
                matched_text=[],
                matched_symbols=[],
                matched_geometry=[],
                reasoning="\n".join(reasoning_parts)
            )
            
            predictions.append(prediction)
        
        return predictions
    
    def _merge_predictions(
        self,
        parent_predictions: List[ProcessPrediction],
        child_predictions: List[ProcessPrediction]
    ) -> List[ProcessPrediction]:
        """
        Merge parent and child predictions.
        
        If a process appears in both:
        - Use parent's high confidence
        - Append child's evidence ONLY if it has meaningful confidence
        """
        merged = {}
        
        # 1. 先加入所有父圖預測 (這些通常是全域規範，如材質、後處理)
        for pred in parent_predictions:
            merged[pred.process_id] = pred
        
        # 2. 加入子圖預測
        for child_pred in child_predictions:
            if child_pred.process_id in merged:
                # 狀況：父圖已經說要做這個了 (例如 I01)
                parent_pred = merged[child_pred.process_id]
                
                # [修正]：只有當子圖也很有信心 (>0.3) 時，才把子圖的證據加進去
                # 這樣可以避免 "經驗法則..." 這種廢話污染了父圖的判斷
                if child_pred.confidence > 0.3:
                    parent_pred.reasoning += f"\n\n[子圖證據]\n{child_pred.reasoning}"
                
                # 這裡我們保持父圖的高信心度 (通常是 0.85)
            else:
                # 狀況：這是子圖新發現的製程 (例如 K01 切削)
                merged[child_pred.process_id] = child_pred
        
        return list(merged.values())
    
    
    def _score_all_processes(
        self,
        features: ExtractedFeatures,
        frequency_filter: Optional[List[str]]
    ) -> List[ProcessPrediction]:
        """
        Score all processes against features.
        Integrates VLM suggestions with traditional scoring.
        """
        candidates = []
        
        # Get VLM suggested process IDs and their confidence scores
        vlm_suggestions = {}
        if features.vlm_analysis:
            suggested_ids = features.vlm_analysis.get("suggested_process_ids", [])
            confidence_scores = features.vlm_analysis.get("confidence_scores", {})
            vlm_suggestions = {pid: confidence_scores.get(pid, 0.7) for pid in suggested_ids}

        has_precision_tolerance = False
        if features.tolerances:
            try:
                has_precision_tolerance = any(
                    tol.get_max_tolerance() < 0.1 for tol in features.tolerances
                )
            except Exception:
                has_precision_tolerance = False
        
        for process_id, process_def in self.processes.items():
            # Apply frequency filter
            if frequency_filter:
                process_freq = process_def.get("frequency", "中")
                if process_freq not in frequency_filter:
                    continue
            
            # Calculate traditional scores
            text_score = self._score_text_match(
                features.ocr_results,
                process_def.get("required_text", [])
            )
            
            symbol_score = self._score_symbol_match(
                features.symbols,
                process_def.get("required_symbols", [])
            )
            
            geometry_score = self._score_geometry_match(
                features.geometry,
                process_def.get("required_geometry", [])
            )
            
            # Check if VLM suggested this process
            vlm_score = vlm_suggestions.get(process_id, 0.0)
            has_vlm_evidence = self._has_vlm_evidence(features) if vlm_score > 0 else False
            has_strong_vlm_evidence = self._has_strong_vlm_evidence(features) if vlm_score > 0 else False
            
            # Get weights (default or from process definition)
            weights = process_def.get("confidence_weights", {
                "text": 0.4,
                "symbol": 0.3,
                "geometry": 0.2,
                "visual": 0.0,
                "vlm": 0.1  # Default VLM weight
            })
            
            # If VLM is active, adjust weights dynamically
            if vlm_score > 0:
                # Increase VLM weight if it suggested this process
                weights = {
                    "text": 0.25,
                    "symbol": 0.20,
                    "geometry": 0.15,
                    "visual": 0.00,
                    "vlm": 0.40  # High confidence in VLM suggestions
                }
            
            # Fuse scores
            final_score = (
                text_score * weights.get("text", 0.4) +
                symbol_score * weights.get("symbol", 0.3) +
                geometry_score * weights.get("geometry", 0.2) +
                vlm_score * weights.get("vlm", 0.1)
                # visual score not implemented yet
            )

            # Visual primacy: if VLM provides clear evidence, keep base confidence >= 0.6
            if has_vlm_evidence:
                final_score = max(final_score, 0.6)
            if has_strong_vlm_evidence:
                final_score = max(final_score, 0.8)

            suppress_experience = False
            suppress_reason = None
            if process_id.startswith("K") and not has_precision_tolerance and not has_vlm_evidence:
                # K 類製程必須有公差或 VLM 證據
                final_score = 0.0
                suppress_experience = True
                suppress_reason = "K 類製程需公差或 VLM 證據，未符合條件。"

            # Add slight jitter to avoid rigid scores
            if final_score > 0:
                final_score = self._apply_confidence_jitter(final_score)
                if has_vlm_evidence and final_score < 0.6:
                    final_score = 0.6
                if has_strong_vlm_evidence and final_score < 0.8:
                    final_score = 0.8
            
            # Collect evidence
            evidence = self._collect_evidence(
                process_def,
                features,
                text_score,
                symbol_score,
                geometry_score,
                vlm_score,
                allow_experience=not suppress_experience,
                suppressed_reason=suppress_reason
            )
            
            # Create prediction
            prediction = ProcessPrediction(
                process_id=process_id,
                name=process_def["name"],
                confidence=float(final_score),
                matched_text=[],
                matched_symbols=[],
                matched_geometry=[],
                reasoning="\n".join(evidence)
            )
            
            candidates.append(prediction)
        
        # Sort by confidence
        candidates.sort(key=lambda p: p.confidence, reverse=True)
        
        return candidates
    
    def _apply_logic_rules(
        self,
        candidates: List[ProcessPrediction],
        features: ExtractedFeatures,
        parent_context: Optional[ParentImageContext] = None
    ) -> List[ProcessPrediction]:
        """
        Apply logic rules: replacement, auto-complete, conflict resolution.
        
        Includes special rules from ChatGPT.txt:
        - Auto-fill: F01→F14, F16→F20, H34→H33
        - Conflict: D04→remove D01+D06, H31→remove H26+H27
        - Material logic: 白鐵+焊接+無烤漆→H01
        """
        # Get processes above threshold
        active_ids = {
            p.process_id for p in candidates
            if p.confidence > 0.4  # Threshold for considering a process
        }
        
        final_candidates = list(candidates)
        
        # 1. Apply replacement rules (from process_lib.json)
        final_candidates = self._apply_replacement_rules(final_candidates, active_ids)
        
        # 2. Apply auto-complete rules (from process_lib.json)
        final_candidates = self._apply_auto_complete_rules(final_candidates, active_ids)
        
        # 3. Apply conflict resolution (from process_lib.json)
        final_candidates = self._apply_conflict_resolution(final_candidates, active_ids)
        
        # 4. Apply ChatGPT.txt hardcoded rules
        final_candidates = self._apply_chatgpt_rules(final_candidates, features, parent_context)
        
        # Re-sort
        final_candidates.sort(key=lambda p: p.confidence, reverse=True)
        
        return final_candidates
    
    def _apply_replacement_rules(
        self,
        candidates: List[ProcessPrediction],
        active_ids: Set[str]
    ) -> List[ProcessPrediction]:
        """
        Apply replacement rules.
        
        Example: If D04 (折彎/植零件) is active, remove D01 (折彎)
        """
        to_remove = set()
        
        for proc_id in active_ids:
            process_def = self.processes.get(proc_id)
            if not process_def:
                continue
            
            rules = process_def.get("rules", {})
            replace_by = rules.get("replace_by", [])
            
            if replace_by:
                # This process replaces others
                for replaced_id in replace_by:
                    if replaced_id in active_ids:
                        to_remove.add(replaced_id)
                        
                        # Add explanation
                        for c in candidates:
                            if c.process_id == proc_id:
                                if c.reasoning:
                                    c.reasoning += f"\n[取代] 取代 {replaced_id} ({self.processes[replaced_id]['name']})"
                                else:
                                    c.reasoning = f"[取代] 取代 {replaced_id} ({self.processes[replaced_id]['name']})"
        
        # Remove replaced processes
        return [c for c in candidates if c.process_id not in to_remove]
    
    def _apply_auto_complete_rules(
        self,
        candidates: List[ProcessPrediction],
        active_ids: Set[str]
    ) -> List[ProcessPrediction]:
        """
        Apply auto-complete rules.
        
        Example: If H34 (三價鉻) is active, auto-add H33 (藥劑清潔)
        """
        to_add = []
        
        for proc_id in active_ids:
            process_def = self.processes.get(proc_id)
            if not process_def:
                continue
            
            rules = process_def.get("rules", {})
            auto_adds = rules.get("auto_adds", [])
            
            for add_id in auto_adds:
                if add_id not in active_ids:
                    # Auto-add this process
                    add_proc = self.processes[add_id]
                    
                    new_prediction = ProcessPrediction(
                        process_id=add_id,
                        name=add_proc["name"],
                        confidence=0.75,  # High confidence for auto-added
                        matched_text=[],
                        matched_symbols=[],
                        matched_geometry=[],
                        reasoning=f"[自動補全] 由 {proc_id} ({process_def['name']}) 觸發"
                    )
                    
                    to_add.append(new_prediction)
        
        return candidates + to_add
    
    def _apply_conflict_resolution(
        self,
        candidates: List[ProcessPrediction],
        active_ids: Set[str]
    ) -> List[ProcessPrediction]:
        """
        Apply conflict resolution.
        
        Example: C05 (M3048) conflicts with C01 (單機切割)
                 Keep the higher confidence one
        """
        to_remove = set()
        
        for proc_id in active_ids:
            process_def = self.processes.get(proc_id)
            if not process_def:
                continue
            
            rules = process_def.get("rules", {})
            conflicts = rules.get("conflicts_with", [])
            
            for conflict_id in conflicts:
                if conflict_id in active_ids and conflict_id not in to_remove:
                    # Both processes are active, resolve conflict
                    proc_conf = next((c.confidence for c in candidates if c.process_id == proc_id), 0)
                    conflict_conf = next((c.confidence for c in candidates if c.process_id == conflict_id), 0)
                    
                    if proc_conf >= conflict_conf:
                        to_remove.add(conflict_id)
                        for c in candidates:
                            if c.process_id == proc_id:
                                if c.reasoning:
                                    c.reasoning += f"\n[衝突解決] 優先於 {conflict_id} ({self.processes[conflict_id]['name']})"
                    else:
                        to_remove.add(proc_id)
        
        return [c for c in candidates if c.process_id not in to_remove]
    
    def _apply_chatgpt_rules(
        self,
        candidates: List[ProcessPrediction],
        features: ExtractedFeatures,
        parent_context: Optional[ParentImageContext]
    ) -> List[ProcessPrediction]:
        """
        Apply hardcoded rules from ChatGPT.txt.
        
        Rules:
        1. Auto-fill: F01→F14, F16→F20, 委外→H08 before
        2. Conflict: D04→remove D01+D06, H31→remove H26+H27
        3. Material: 白鐵+焊接+無烤漆→H01
        """
        active_ids = {p.process_id for p in candidates if p.confidence > 0.4}
        final_candidates = list(candidates)
        to_add = []
        to_remove = set()
        
        # Rule 1: Welding chain - F01 > 0.6 → F14 = F01 * 0.9
        f01_conf = next((c.confidence for c in final_candidates if c.process_id == "F01"), 0)
        if f01_conf > 0.6:
            f14_def = self.processes.get("F14")
            if f14_def:
                f14_target = round(f01_conf * 0.9, 4)
                f14_pred = next((c for c in final_candidates if c.process_id == "F14"), None)
                if f14_pred:
                    if f14_pred.confidence < f14_target:
                        f14_pred.confidence = f14_target
                        f14_pred.reasoning += "\n[連動] F01 信心度高 → 提升 F14"
                else:
                    to_add.append(ProcessPrediction(
                        process_id="F14",
                        name=f14_def["name"],
                        confidence=f14_target,
                        matched_text=[],
                        matched_symbols=[],
                        matched_geometry=[],
                        reasoning="[連動] F01 信心度高 → 補全 F14"
                    ))
        
        # Rule 2: Auto-fill F16 → F20
        if "F16" in active_ids and "F20" not in active_ids:
            f20_def = self.processes.get("F20")
            if f20_def:
                to_add.append(ProcessPrediction(
                    process_id="F20",
                    name=f20_def["name"],
                    confidence=0.75,
                    matched_text=[],
                    matched_symbols=[],
                    matched_geometry=[],
                    reasoning="[自動補全] 由 F16 自動觸發"
                ))
        
        # Rule 3: Conflict - D04 (折彎/植零件) → remove D01, D06
        if "D04" in active_ids:
            if "D01" in active_ids:
                to_remove.add("D01")
            if "D06" in active_ids:
                to_remove.add("D06")
            # Add explanation
            for c in final_candidates:
                if c.process_id == "D04":
                    c.reasoning += "\n[衝突解決] 取代 D01 和 D06"
        
        # Rule 4: Conflict - H31 (無塵室清潔/包裝) → remove H26, H27
        if "H31" in active_ids:
            if "H26" in active_ids:
                to_remove.add("H26")
            if "H27" in active_ids:
                to_remove.add("H27")
            # Add explanation
            for c in final_candidates:
                if c.process_id == "H31":
                    c.reasoning += "\n[衝突解決] 取代 H26 和 H27"
        
        # Rule 5: Material logic - 白鐵 + 焊接 + 無烤漆 → H01 (除焦洗淨)
        if parent_context:
            has_welding = any(pid.startswith("F") for pid in active_ids)  # F series = welding
            is_stainless = parent_context.material == "白鐵"
            no_painting = "烤漆" not in parent_context.surface_treatment
            
            if is_stainless and has_welding and no_painting and "H01" not in active_ids:
                h01_def = self.processes.get("H01")
                if h01_def:
                    to_add.append(ProcessPrediction(
                        process_id="H01",
                        name=h01_def["name"],
                        confidence=0.80,
                        matched_text=[],
                        matched_symbols=[],
                        matched_geometry=[],
                        reasoning="[材質邏輯] 白鐵+焊接+無烤漆 → 需除焦洗淨"
                    ))
        
        # Rule 6: Precision tolerance logic - Tolerance < 0.1mm → K01 (切削)
        if features.tolerances:
            # Get tightest tolerance
            min_tolerance = min(tol.get_max_tolerance() for tol in features.tolerances)
            
            # High precision required (< 0.1mm)
            if min_tolerance < 0.1:
                # Add K01 (切削/milling) if not present
                if "K01" not in active_ids:
                    k01_def = self.processes.get("K01")
                    if k01_def:
                        to_add.append(ProcessPrediction(
                            process_id="K01",
                            name=k01_def["name"],
                            confidence=0.90,  # Very high confidence for precision requirement
                            matched_text=[],
                            matched_symbols=[],
                            matched_geometry=[],
                            reasoning=f"[精密公差] 檢測到 ±{min_tolerance:.2f}mm 公差 → 需切削加工"
                        ))
                
                # Reduce confidence of laser cutting processes (C01, C02)
                for c in final_candidates:
                    if c.process_id in ["C01", "C02"]:  # Laser cutting
                        original_conf = c.confidence
                        c.confidence *= 0.6  # Reduce by 40%
                        c.reasoning += f"\n[精密公差] 因 ±{min_tolerance:.2f}mm 公差要求，信心度降低 ({original_conf:.2f} → {c.confidence:.2f})"
        
        # Apply removals
        final_candidates = [c for c in final_candidates if c.process_id not in to_remove]

        # Apply additions
        final_candidates.extend(to_add)

        # Rule 7: Conflict suppression - C05 >> C04
        c05_conf = next((c.confidence for c in final_candidates if c.process_id == "C05"), 0)
        c04_pred = next((c for c in final_candidates if c.process_id == "C04"), None)
        if c04_pred and c05_conf - c04_pred.confidence >= 0.1:
            c04_pred.confidence = 0.0
            c04_pred.reasoning += "\n[衝突抑制] C05 明顯高於 C04，抑制 C04"

        return final_candidates
    
    # ==================================================================
    # Scoring Functions (same as v1)
    # ==================================================================
    
    def _score_text_match(
        self,
        ocr_results: List[OCRResult],
        required_text: List[str]
    ) -> float:
        """Score text matching."""
        if not required_text:
            return 0.5  # Neutral
        
        if not ocr_results:
            return 0.0
        
        # Combine all OCR text
        all_text = " ".join([r.text for r in ocr_results])
        
        # Count matches
        matches = 0
        for keyword in required_text:
            if keyword.lower() in all_text.lower():
                matches += 1
        
        if len(required_text) == 0:
            return 0.5
        
        return matches / len(required_text)
    
    def _score_symbol_match(
        self,
        symbols: List[SymbolDetection],
        required_symbols: List[str]
    ) -> float:
        """Score symbol matching."""
        if not required_symbols:
            return 0.5  # Neutral
        
        if not symbols:
            return 0.0
        
        detected_types = {s.symbol_type for s in symbols}
        
        matches = 0
        for required_type in required_symbols:
            if required_type in detected_types:
                matches += 1
        
        if len(required_symbols) == 0:
            return 0.5
        
        return matches / len(required_symbols)
    
    def _score_geometry_match(
        self,
        geometry: GeometryFeatures,
        required_geometry: List[str]
    ) -> float:
        """Score geometry matching."""
        if not required_geometry or geometry is None:
            return 0.5  # Neutral
        
        feature_checks = {
            "bend_lines": len(geometry.bend_lines) > 0,
            "holes": len(geometry.holes) > 0,
            "circles": len(geometry.circles) > 0,
            "lines": len(geometry.lines) > 0,
            "complex_shapes": len(geometry.contours) > 5,
            "angles": len(geometry.bend_lines) > 0,  # Proxy for angles
            "thickness": False,  # Not implemented
        }
        
        matches = 0
        for required_feature in required_geometry:
            if required_feature in feature_checks and feature_checks[required_feature]:
                matches += 1
        
        if len(required_geometry) == 0:
            return 0.5
        
        return matches / len(required_geometry)
    
    def _collect_evidence(
        self,
        process_def: Dict,
        features: ExtractedFeatures,
        text_score: float,
        symbol_score: float,
        geometry_score: float,
        vlm_score: float = 0.0,
        allow_experience: bool = True,
        suppressed_reason: Optional[str] = None
    ) -> List[str]:
        """Collect evidence for prediction with conversational tone."""
        evidence = []
        
        # VLM evidence (highest priority)
        if vlm_score > 0.3 and features.vlm_analysis:
            shape_desc = features.vlm_analysis.get("shape_description")
            if shape_desc:
                evidence.append(f"VLM: 我看到它長得像 {shape_desc}。")

            detected_features = features.vlm_analysis.get("detected_features", {})
            geometry_features = detected_features.get("geometry", []) if detected_features else []
            symbols_features = detected_features.get("symbols", []) if detected_features else []
            if geometry_features or symbols_features:
                parts = []
                if geometry_features:
                    translated_geo = [self._translate_term(t) for t in geometry_features[:3]]
                    parts.append(f"幾何特徵：{', '.join(translated_geo)}")
                if symbols_features:
                    translated_sym = [self._translate_term(t) for t in symbols_features[:3]]
                    parts.append(f"符號：{', '.join(translated_sym)}")
                evidence.append(f"VLM: 我看到 { '，'.join(parts) }。")
        
        # Text evidence
        if text_score > 0.3 and process_def.get("required_text"):
            detected_keywords = [
                kw for kw in process_def["required_text"]
                if any(kw.lower() in r.text.lower() for r in features.ocr_results)
            ]
            if detected_keywords:
                evidence.append(f"我在圖上看到這些字：{', '.join(detected_keywords[:3])}。")
        
        # Symbol evidence
        if symbol_score > 0.3 and process_def.get("required_symbols"):
            detected_symbols = [
                s.symbol_type for s in features.symbols
                if s.symbol_type in process_def["required_symbols"]
            ]
            if detected_symbols:
                evidence.append(f"我有看到符號：{', '.join(detected_symbols)}。")
        
        # Geometry evidence
        if geometry_score > 0.3 and process_def.get("required_geometry") and features.geometry:
            geo_ev = []
            if "bend_lines" in process_def["required_geometry"] and features.geometry.bend_lines:
                geo_ev.append(f"折彎線 {len(features.geometry.bend_lines)} 條")
            if "holes" in process_def["required_geometry"] and features.geometry.holes:
                geo_ev.append(f"孔洞 {len(features.geometry.holes)} 個")
            if "circles" in process_def["required_geometry"] and features.geometry.circles:
                geo_ev.append(f"圓形 {len(features.geometry.circles)} 個")
            
            if geo_ev:
                evidence.append(f"我看到的幾何特徵有：{', '.join(geo_ev)}。")
        
        # Default evidence
        if not evidence:
            if allow_experience:
                evidence.append("經驗法則：這類鈑金件，大家多半會做。")
            else:
                evidence.append(suppressed_reason or "未偵測到有效證據。")

        return evidence

    def _has_vlm_evidence(self, features: ExtractedFeatures) -> bool:
        """Check whether VLM provides explicit visual evidence."""
        if not features.vlm_analysis:
            return False
        detected = features.vlm_analysis.get("detected_features", {})
        geometry_features = detected.get("geometry", []) if detected else []
        symbol_features = detected.get("symbols", []) if detected else []
        return bool(geometry_features or symbol_features)

    def _has_strong_vlm_evidence(self, features: ExtractedFeatures) -> bool:
        """Check whether VLM mentions strong visual evidence keywords."""
        if not features.vlm_analysis:
            return False
        detected = features.vlm_analysis.get("detected_features", {})
        geometry_features = detected.get("geometry", []) if detected else []
        symbol_features = detected.get("symbols", []) if detected else []
        keywords = {"welding", "oval hole"}
        for item in geometry_features + symbol_features:
            if isinstance(item, str):
                lowered = item.lower()
                if any(keyword in lowered for keyword in keywords):
                    return True
        return False

    def _translate_term(self, term: str) -> str:
        """Translate common professional terms to Chinese."""
        if not isinstance(term, str):
            return str(term)
        mapping = {
            "welding": "焊接",
            "weld": "焊接",
            "oval hole": "橢圓孔",
            "countersink": "沉頭孔",
            "counterbore": "沉孔",
            "rib": "肋條",
            "hole": "孔",
            "holes": "孔洞",
            "bend": "折彎",
            "bend lines": "折彎線"
        }
        lower = term.lower()
        for key, value in mapping.items():
            if key in lower:
                return lower.replace(key, value)
        return term

    def _apply_confidence_jitter(self, score: float) -> float:
        """
        Apply a small random jitter to make confidence look natural.

        Args:
            score: Raw confidence score.

        Returns:
            float: Jittered confidence score in [0, 1].
        """
        jitter = random.uniform(-0.02, 0.02)
        adjusted = score + jitter
        return max(0.0, min(1.0, adjusted))
    
    def get_process_by_id(self, process_id: str) -> Optional[Dict]:
        """Get process definition by ID."""
        return self.processes.get(process_id)
    
    def get_all_processes(self) -> Dict[str, Dict]:
        """Get all loaded process definitions."""
        return self.processes
    
    def get_frequency_options(self) -> List[str]:
        """Get all unique frequency values."""
        frequencies = set()
        for proc in self.processes.values():
            freq = proc.get("frequency", "中")
            frequencies.add(freq)
        return sorted(list(frequencies))
