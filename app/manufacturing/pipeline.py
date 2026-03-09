"""
Manufacturing Process Recognition Pipeline.

End-to-end workflow:
1. Load image (from file or numpy array)
2. Extract multimodal features (OCR, Geometry, Symbols, Visual embeddings)
3. Run decision engine to predict processes
4. Return results with confidence and evidence
"""

from typing import Optional, Union, List, Dict, Any, Sequence
from pathlib import Path
import numpy as np
import cv2
import time
import re

from .schema import (
    ExtractedFeatures,
    RecognitionResult,
    ProcessPrediction
)
from .extractors import (
    OCRExtractor,
    GeometryExtractor,
    SymbolDetector,
    VisualEmbedder,
    PDFImageExtractor,
    is_pdf_available
)
from .extractors.parent_parser import ParentImageParser, ParentImageContext
from .extractors.tolerance_parser import ToleranceParser
from .extractors.vlm_client import VLMClient
from .prompts import EngineeringPrompts, get_vlm_descriptive_prompt
from .decision import DecisionEngine
from .decision.rule_router import plan_vision_skills, describe_skills
from .decision.engine_v2 import DecisionEngineV2
from .schema import GeometryFeatures


class ManufacturingPipeline:
    """
    Complete pipeline for engineering drawing process recognition.
    
    Usage:
        pipeline = ManufacturingPipeline()
        result = pipeline.recognize("path/to/drawing.jpg")
        
        # Access predictions
        for pred in result.predictions:
            print(f"{pred.process_name}: {pred.confidence:.2f}")
            print(f"  Evidence: {pred.evidence}")
    """
    
    def __init__(
        self,
        use_ocr: bool = True,
        use_geometry: bool = True,
        use_symbols: bool = True,
        use_visual: bool = False,  # Visual embeddings optional (expensive)
        use_vlm: bool = False,  # VLM analysis optional (requires LM Studio)
        template_dir: Optional[str] = None,
        process_lib_path: Optional[str] = None,
        use_v2_engine: bool = True  # Use DecisionEngineV2 by default
    ):
        """
        Initialize pipeline.
        
        Args:
            use_ocr: Enable OCR text extraction.
            use_geometry: Enable geometry analysis.
            use_symbols: Enable symbol detection.
            use_visual: Enable visual embedding (DINOv2).
            use_vlm: Enable VLM-based process recognition (requires LM Studio).
            template_dir: Directory for symbol templates.
            process_lib_path: Path to process_lib.json or process_lib_v2.json.
            use_v2_engine: Use DecisionEngineV2 (supports logic rules).
        """
        self.use_ocr = use_ocr
        self.use_geometry = use_geometry
        self.use_symbols = use_symbols
        self.use_visual = use_visual
        self.use_vlm = use_vlm
        
        # Initialize extractors
        self.ocr_extractor = OCRExtractor() if use_ocr else None
        self.geometry_extractor = GeometryExtractor() if use_geometry else None
        self.symbol_detector = SymbolDetector(template_dir) if use_symbols else None
        
        # Initialize visual embedder (gracefully handle unavailability)
        self.visual_embedder = None
        if use_visual:
            try:
                self.visual_embedder = VisualEmbedder()
                # Check if it actually loaded successfully
                if self.visual_embedder.model is None:
                    print("Info: Visual embeddings unavailable - using OCR + Geometry + Symbols")
                    self.visual_embedder = None
                    self.use_visual = False
            except Exception as e:
                print(f"Warning: Failed to initialize visual embedder: {e}")
                print("   Continuing with OCR + Geometry + Symbols only")
                self.visual_embedder = None
                self.use_visual = False
        
        # Initialize VLM client (gracefully handle unavailability)
        self.vlm_client = None
        self.vlm_prompt_template = None
        if use_vlm:
            try:
                self.vlm_client = VLMClient()
                # Check if VLM service is available
                if not self.vlm_client.is_available():
                    print("Info: VLM service not available - LM Studio may not be running")
                    print("   Continuing with traditional feature extraction only")
                    self.vlm_client = None
                    self.use_vlm = False
                else:
                    # Prompt template is no longer used; get_vlm_descriptive_prompt()
                    # is called at analysis time so the latest vocabulary is always used.
                    self.vlm_prompt_template = True  # marker: VLM is ready
                    print("Info: VLM service connected successfully")
            except Exception as e:
                print(f"Warning: Failed to initialize VLM client: {e}")
                print("   Continuing with traditional feature extraction only")
                self.vlm_client = None
                self.use_vlm = False
        
        # Initialize parent image parser
        self.parent_parser = ParentImageParser(self.ocr_extractor)
        
        # Initialize PDF extractor (if available)
        self.pdf_extractor = None
        if is_pdf_available():
            try:
                self.pdf_extractor = PDFImageExtractor(target_dpi=300)
            except ImportError:
                pass  # PDF功能不可用
        
        # Initialize decision engine (v2 by default)
        if use_v2_engine:
            self.decision_engine = DecisionEngineV2(process_lib_path)
        else:
            self.decision_engine = DecisionEngine(process_lib_path)
    
    @property
    def total_processes(self) -> int:
        """Get total number of processes in the loaded library."""
        return self.decision_engine.total_processes
    
    def recognize(
        self,
        image: Optional[Union[str, np.ndarray]],
        parent_image: Optional[Union[str, np.ndarray]] = None,
        top_n: Optional[int] = None,
        min_confidence: float = 0.3,
        ocr_threshold: float = 0.5,
        symbol_threshold: float = 0.6,
        frequency_filter: Optional[List[str]] = None,
        use_rag: bool = False,
        child_images: Optional[Sequence[Union[str, Path, np.ndarray]]] = None,
        view_labels: Optional[List[str]] = None,
        bom_context: str = ""
    ) -> RecognitionResult:
        """
        Recognize manufacturing processes from engineering drawing.
        
        Args:
            image: Child image file path or numpy array (BGR). REQUIRED.
            parent_image: Parent image file path or numpy array (BGR). OPTIONAL.
                         Contains global information (title block, technical notes, etc.)
            top_n: Return top N process predictions.
            min_confidence: Minimum confidence threshold for predictions.
            ocr_threshold: Minimum confidence for OCR detections.
            symbol_threshold: Minimum confidence for symbol detections.
            frequency_filter: List of frequencies to include (e.g., ["高", "中"]).
                            If None, all frequencies are included.
            use_rag: Enable RAG-based context augmentation.
            child_images: Optional list of child images for VLM context.
            view_labels: Optional list of view names matching child_images order
                         (e.g. ['Top', 'Front', 'Side']). Top and Front are treated
                         as primary evidence; Side/Iso as supporting reference.
            bom_context: Free-text BOM / global notes typed by user (injected into VLM prompt).
            bom_context: Free-text BOM / global notes typed by user (injected into VLM prompt).
        
        Returns:
            RecognitionResult with predictions and diagnostics.
        """
        start_time = time.time()
        
        # Parse parent image (optional)
        parent_context = None
        parent_context_text = ""
        parent_context_payload: Dict[str, Any] = {}
        if parent_image is not None:
            # Load parent image (支援 PDF)
            if isinstance(parent_image, str):
                if parent_image.lower().endswith('.pdf') and self.pdf_extractor:
                    # PDF → 高解析度圖片
                    try:
                        parent_img_array = self.pdf_extractor.extract_full_page(parent_image, page_num=0)
                    except Exception as e:
                        raise ValueError(f"Failed to extract parent image from PDF: {e}")
                else:
                    # 一般圖片檔案
                    parent_img_array = cv2.imread(parent_image)
                    if parent_img_array is None:
                        raise ValueError(f"Failed to load parent image: {parent_image}")
            else:
                parent_img_array = parent_image
            
            # Parse parent image for global context
            parent_context = self.parent_parser.parse(
                parent_img_array,
                ocr_threshold
            )
            parent_context_text = self.parent_parser.analyze_parent_context(parent_img_array)
            if parent_context_text:
                parent_context_payload = {}
                parent_context.vlm_context = parent_context_payload

            if image is None:
                processing_time = time.time() - start_time
                parent_report = self._build_parent_report(parent_context, parent_context_payload)
                warnings = [
                    f"這是父圖，已提取資訊：{parent_context_text}" if parent_context_text else "這是父圖，已提取資訊。"
                ]
                if parent_report:
                    warnings.append(f"父圖全域分析報告：{parent_report}")
                return RecognitionResult(
                    predictions=[],
                    features=ExtractedFeatures(),
                    parent_context=parent_context,
                    total_time=processing_time,
                    warnings=warnings
                )
        
        # Load child image (required)
        if image is None:
            raise ValueError("Child image is required for recognition.")
        # 支援 PDF 檔案自動轉換
        if isinstance(image, str):
            image_path = image
            if image.lower().endswith('.pdf') and self.pdf_extractor:
                # PDF → 高解析度圖片
                try:
                    img_array = self.pdf_extractor.extract_full_page(image, page_num=0)
                except Exception as e:
                    raise ValueError(f"Failed to extract image from PDF: {e}")
            else:
                # 一般圖片檔案
                img_array = cv2.imread(image)
                if img_array is None:
                    raise ValueError(f"Failed to load image: {image}")
        else:
            img_array = image
            image_path = None
        
        # Extract features from child image
        parent_prompt = ""
        if parent_context_text or bom_context:
            effective_bom = bom_context or parent_context_text
            parent_report = self._build_parent_report(parent_context, parent_context_payload)
            parent_prompt = get_vlm_descriptive_prompt(bom_context=effective_bom)
            structure = parent_context_payload.get("3d_structure")
            if structure:
                parent_prompt = (
                    f"【全域幾何背景】 此零件為一個 {structure}。"
                    "請基於此背景分析當前圖片的製程與特徵。\n\n"
                    f"{parent_prompt}"
                )
            if parent_report:
                parent_prompt = f"【父圖全域分析報告】{parent_report}\n\n{parent_prompt}"

        vlm_images: List[Union[str, Path, np.ndarray]] = []
        if child_images:
            vlm_images = [img for img in child_images if img is not None]
        if not vlm_images:
            if image_path is not None:
                vlm_images = [image_path]
            else:
                vlm_images = [img_array]

        # ── BUG A 修復：SymbolMatcher 先於 VLM 執行，命中結果注入初次 prompt ────
        system_anchors: List[str] = []
        try:
            from app.vision.symbol_matcher import SymbolMatcher
            _sym_matcher = SymbolMatcher()
            if _sym_matcher.symbol_names:  # 只在有模板時才掃描
                _sm_hits = _sym_matcher.match_symbols(img_array)
                for _hit in _sm_hits:
                    _hname = _hit["name"]
                    if _hname not in system_anchors:
                        system_anchors.append(_hname)
        except Exception as _sm_err:
            print(f"Warning: SymbolMatcher scan failed: {_sm_err}")

        # ── Rule-based 技能路由：依 BOM 文字觸發 Dummy CV 掃描 ─────────────────
        _effective_bom = bom_context or parent_context_text
        _routed_skills = plan_vision_skills(_effective_bom)
        if _routed_skills:
            print(f"Info: Rule router triggered skills: {describe_skills(_routed_skills)}")
        # Dummy CV 執行器：將技能名稱映射為視覺錨點文字
        _DUMMY_CV_MAP: Dict[str, str] = {
            "scan_weld_symbols":    "Weld Symbol",
            "scan_thread_marks":    "Thread / Tap Mark",
            "scan_holes":           "Hole / Thru-hole",
            "scan_bend_lines":      "Bend Line",
            "scan_surface_marks":   "Surface Finish Mark",
            "scan_tolerance_marks": "Tolerance Callout",
            "scan_insert_marks":    "Insert / Rivet",
        }
        for _skill in _routed_skills:
            _anchor = _DUMMY_CV_MAP.get(_skill, _skill)
            _tagged  = f"[System] Detected {_anchor}"
            if _tagged not in system_anchors:
                system_anchors.append(_tagged)

        # 組裝初次 VLM prompt（帶入 system_anchors，不論 RAG 是否啟用）
        if parent_prompt:
            _initial_prompt = parent_prompt
        elif system_anchors:
            _initial_prompt = get_vlm_descriptive_prompt(system_anchors=system_anchors)
        else:
            _initial_prompt = ""

        features = self._extract_features(
            img_array,
            ocr_threshold,
            symbol_threshold,
            image_path=image_path,
            prompt_override=_initial_prompt,
            vlm_images=vlm_images,
            view_labels=view_labels
        )

        rag_references: List[Dict[str, Any]] = []
        rag_context_text = ""

        # RAG retrieval: hash 優先比對（不依賴 VLM，只要有 image_path 就能跑）
        # 後備：vlm_analysis dict 的 shape 文字比對
        if use_rag:
            try:
                from app.knowledge.manager import KnowledgeBaseManager
                kb = KnowledgeBaseManager()
                _vlm_feats = features.vlm_analysis if isinstance(features.vlm_analysis, dict) else {}
                similar_cases = kb.retrieve_similar(
                    _vlm_feats,
                    image_path=image_path or "",
                    top_k=3,
                    raw_vlm_text=features.raw_vlm_description or ""
                )
                if similar_cases:
                    rag_references = similar_cases
                    best_case = similar_cases[0]
                    _ref_desc = (
                        best_case.get("features", {}).get("raw_vlm_description", "")
                        or best_case.get("reasoning", "")
                    )
                    rag_context_text = _ref_desc
                    # 組裝 system_anchors：CV 偵測符號 + RAG rag_priors 幾何名詞
                    _cv_symbols: List[str] = []
                    if features.symbols:
                        for sym in features.symbols:
                            _label = getattr(sym, 'symbol_type', None) or sym.get('symbol_type', '') if isinstance(sym, dict) else str(sym)
                            if _label:
                                _cv_symbols.append(str(_label))
                    _rag_priors: List[str] = best_case.get('rag_priors', [])
                    system_anchors = list(system_anchors) + [p for p in _cv_symbols if p not in system_anchors] + [p for p in _rag_priors if p not in system_anchors]
            except Exception as e:
                print(f"Warning: RAG retrieval failed: {e}")
        # If RAG context exists, re-run VLM with injected prompt
        if rag_context_text and self.vlm_client:
            try:
                input_images: List[Union[str, Path, np.ndarray]] = list(vlm_images)
                prompt = get_vlm_descriptive_prompt(bom_context=parent_context_text, rag_context=rag_context_text, system_anchors=system_anchors)
                structure = parent_context_payload.get("3d_structure")
                if structure:
                    prompt = (
                        f"【全域幾何背景】 此零件為一個 {structure}。"
                        "請基於此背景分析當前圖片的製程與特徵。\n\n"
                        f"{prompt}"
                    )
                vlm_result = self.vlm_client.analyze_image(
                    image_path=input_images,
                    prompt=prompt,
                    response_format="text",
                    temperature=0.15,
                    max_tokens=512,
                    stop=["[END OF REPORT]"],
                )
                if vlm_result and isinstance(vlm_result, str):
                    features.raw_vlm_description = ManufacturingPipeline._clean_vlm_output(vlm_result)
            except Exception as e:
                print(f"Warning: RAG VLM analysis failed: {e}")
        
        # Run decision engine (pass parent_context if available)
        if isinstance(self.decision_engine, DecisionEngineV2):
            predictions = self.decision_engine.predict(
                features,
                parent_context=parent_context,
                top_n=top_n,
                min_confidence=min_confidence,
                frequency_filter=frequency_filter
            )
        else:
            fallback_top_n = top_n if top_n is not None else len(self.decision_engine.processes)
            predictions = self.decision_engine.predict(
                features,
                top_n=fallback_top_n,
                min_confidence=min_confidence
            )
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Create result (include parent_context if available)
        result = RecognitionResult(
            predictions=predictions,
            features=features,
            parent_context=parent_context,
            total_time=processing_time,
            rag_references=rag_references
        )
        
        return result

    def _build_parent_report(
        self,
        parent_context: Optional[ParentImageContext],
        parent_context_payload: Dict[str, Any]
    ) -> str:
        """
        Build a child-usable global report from parent context.

        Args:
            parent_context: Parsed parent context (OCR-derived).
            parent_context_payload: VLM JSON payload (3d structure, features).

        Returns:
            str: Concise report string for prompts/UI.
        """
        if not parent_context and not parent_context_payload:
            return ""

        name = ""
        if parent_context and parent_context.title_block_text:
            name = parent_context.title_block_text[0].strip()

        material_spec = parent_context_payload.get("material_spec")
        structure = parent_context_payload.get("3d_structure")
        global_features = parent_context_payload.get("global_features", [])

        if not material_spec and parent_context and parent_context.material:
            material_spec = parent_context.material

        parts = []
        if name:
            parts.append(f"零件名稱：{name}")
        if material_spec:
            parts.append(f"材質：{material_spec}")
        if structure:
            parts.append(f"結構：{structure}")
        if global_features:
            features_text = ", ".join(global_features) if isinstance(global_features, list) else str(global_features)
            parts.append(f"特徵：{features_text}")

        return " / ".join(parts)
    
    def _extract_features(
        self,
        image: np.ndarray,
        ocr_threshold: float,
        symbol_threshold: float,
        image_path: Optional[str] = None,
        prompt_override: str = "",
        vlm_images: Optional[Sequence[Union[str, Path, np.ndarray]]] = None,
        view_labels: Optional[List[str]] = None
    ) -> ExtractedFeatures:
        """
        Extract all features from image.
        
        Args:
            image: Input image (BGR).
            ocr_threshold: OCR confidence threshold.
            symbol_threshold: Symbol confidence threshold.
            image_path: Optional image file path (for VLM).
        
        Returns:
            ExtractedFeatures object.
        """
        # OCR extraction
        ocr_results = []
        if self.use_ocr and self.ocr_extractor:
            ocr_results = self.ocr_extractor.extract(image, ocr_threshold)
        
        # Tolerance extraction from OCR results (NEW!)
        tolerances = []
        if ocr_results:
            tolerance_parser = ToleranceParser()
            tolerances = tolerance_parser.extract_tolerances(ocr_results)
        
        # Geometry extraction (pass OCR results for dimension line filtering)
        geometry = None
        if self.use_geometry and self.geometry_extractor:
            geometry = self.geometry_extractor.extract(image, ocr_results=ocr_results)
        
        # Symbol detection
        symbols = []
        if self.use_symbols and self.symbol_detector:
            symbols = self.symbol_detector.detect(image, symbol_threshold)
        
        # Visual embedding
        visual_embedding = None
        if self.use_visual and self.visual_embedder:
            visual_embedding = self.visual_embedder.extract(image)
        
        # VLM analysis (NEW!)
        vlm_analysis = None
        if self.use_vlm and self.vlm_client:
            try:
                # Use image_path if available, otherwise use numpy array
                input_image: Union[str, Path, np.ndarray, List[Union[str, Path, np.ndarray]]]
                if vlm_images:
                    input_image = list(vlm_images)
                elif image_path is not None:
                    input_image = image_path
                else:
                    input_image = image
                prompt = prompt_override or get_vlm_descriptive_prompt()
                # 注入視角說明到 prompt：告討 VLM 每張圖的角色
                if view_labels and len(view_labels) > 0:
                    _primary = ['Top', 'Front']
                    _label_lines = []
                    for i, lbl in enumerate(view_labels):
                        _role = '(Primary — main evidence)' if any(p.lower() in lbl.lower() for p in _primary) else '(Supporting reference only)'
                        _label_lines.append(f'  Image {i+1}: {lbl} View {_role}')
                    _view_context = (
                        'IMAGES PROVIDED (analyse in this order):\n'
                        + '\n'.join(_label_lines)
                        + '\nTop View and Front View are your PRIMARY evidence for shape and features. '
                        + 'Side/Iso views are SUPPORTING only — use them to confirm, not as main source.\n\n'
                    )
                    prompt = _view_context + prompt
                vlm_result = self.vlm_client.analyze_image(
                    image_path=input_image,
                    prompt=prompt,
                    response_format="text",
                    temperature=0.1,
                    max_tokens=512,
                    stop=["[END OF REPORT]"],
                )
                
                if vlm_result:
                    vlm_analysis = ManufacturingPipeline._clean_vlm_output(vlm_result)
                    chars = len(vlm_analysis)
                    print(f"Info: VLM analysis completed - {chars} chars (after dimension strip)")
                else:
                    print("Warning: VLM analysis returned None")
            except Exception as e:
                print(f"Warning: VLM analysis failed: {e}")
                vlm_analysis = None
        
        return ExtractedFeatures(
            ocr_results=ocr_results,
            geometry=geometry or GeometryFeatures(),
            symbols=symbols,
            visual_embedding=visual_embedding,
            tolerances=tolerances,  # NEW!
            raw_vlm_description=vlm_analysis  # NEW!
        )
    
    @staticmethod
    def _clean_vlm_output(raw: str) -> str:
        """
        Post-process raw VLM output: strip dimension numbers, truncate repetition.

        Args:
            raw: Raw string from VLM API.

        Returns:
            str: Cleaned VLM description.
        """
        _cleaned = re.sub(
            r'\b\d+\.?\d*\s*(?:mm|cm|m|in|inch|inches|\xb0|deg)\b',
            '',
            raw,
            flags=re.IGNORECASE
        )
        # 擴大清洗：公差符號、圓角半徑、螺紋規格、角度數值
        _cleaned = re.sub(r'[\u00b1]\s*\d+\.?\d*', '', _cleaned)   # ±0.1
        _cleaned = re.sub(r'\bR\d+\.?\d*\b', '', _cleaned)         # R3, R0.5
        _cleaned = re.sub(r'\bM\d+(\.[\d]+)?\b', '', _cleaned)     # M6, M8x1.25
        _cleaned = re.sub(r'\b\d+\.?\d*\s*\u00b0', '', _cleaned)  # 45°, 90°
        # 清除 dimension chain 句型
        _cleaned = re.sub(r'\s+x\s+x\s+', ' ', _cleaned)
        _cleaned = re.sub(r'dimensions?\s+(\S+\s+x\s+)*\S+', '', _cleaned, flags=re.IGNORECASE)
        # [END OF REPORT] 截斷
        if '[END OF REPORT]' in _cleaned:
            _cleaned = _cleaned.split('[END OF REPORT]')[0]
        # 備援截斷：第二個 Section 3 header 之後的內容全部丟棄
        _parts = re.split(r'(?m)^(?:###\s+)?[3-9]\.', _cleaned)
        if len(_parts) > 2:
            _head = re.search(r'(?m)^(?:###\s+)?3\.', _cleaned)
            _prefix = ('### 3.' if (_head and '###' in _head.group()) else '3.')
            _cleaned = _parts[0] + _prefix + _parts[1]
        # 備援截斷：偵測 Section 3 內的重複句型（同一句出現 2 次以上即截斷）
        _sec3_match = re.search(r'(?m)^(?:###\s+)?3\.', _cleaned)
        if _sec3_match:
            _before = _cleaned[:_sec3_match.end()]
            _sec3_body = _cleaned[_sec3_match.end():]
            _sentences = [s.strip() for s in re.split(r'\.\s+', _sec3_body) if len(s.strip()) > 20]
            _seen: set = set()
            _cut_idx = len(_sec3_body)
            for _sent in _sentences:
                _key = re.sub(r'<[^>]+>', '', _sent).lower().strip()
                if _key in _seen:
                    _pos = _sec3_body.find(_sent)
                    if _pos >= 0:  # fix: was `> 0`, missed position-0 duplicates
                        _cut_idx = _pos
                    break
                _seen.add(_key)
            _cleaned = _before + _sec3_body[:_cut_idx].rstrip()
        # 移除多餘空白
        _cleaned = re.sub(r'[ \t]+', ' ', _cleaned)
        _cleaned = re.sub(r'  +', ' ', _cleaned).strip()
        return _cleaned

    def batch_recognize(
        self,
        images: List[Union[str, np.ndarray]],
        **kwargs
    ) -> List[RecognitionResult]:
        """
        Batch process multiple images.
        
        Args:
            images: List of image paths or numpy arrays.
            **kwargs: Additional arguments for recognize().
        
        Returns:
            List of RecognitionResult objects.
        """
        results = []
        for image in images:
            try:
                result = self.recognize(image, **kwargs)
                results.append(result)
            except Exception as e:
                # Create error result
                results.append(RecognitionResult(
                    predictions=[],
                    features=ExtractedFeatures(
                        ocr_results=[],
                        geometry=GeometryFeatures(),
                        symbols=[],
                        visual_embedding=None
                    ),
                    total_time=0.0,
                    errors=[str(e)]
                ))
        
        return results
    
    def visualize_features(
        self,
        image: Union[str, np.ndarray],
        show_ocr: bool = True,
        show_geometry: bool = True,
        show_symbols: bool = True
    ) -> np.ndarray:
        """
        Visualize extracted features on image (for debugging).
        
        Args:
            image: Input image path or numpy array.
            show_ocr: Draw OCR bounding boxes.
            show_geometry: Draw geometry features.
            show_symbols: Draw symbol detections.
        
        Returns:
            Image with drawn features.
        """
        # Load image
        if isinstance(image, str):
            img_array = cv2.imread(image)
            if img_array is None:
                raise ValueError(f"Failed to load image: {image}")
        else:
            img_array = image.copy()
        
        # Extract features
        features = self._extract_features(
            img_array, 
            0.5, 
            0.6,
            image_path=image if isinstance(image, str) else None
        )
        
        # Draw features
        vis_image = img_array.copy()
        
        if show_geometry and features.geometry and self.geometry_extractor:
            vis_image = self.geometry_extractor.visualize(vis_image, features.geometry)
        
        if show_symbols and features.symbols and self.symbol_detector:
            vis_image = self.symbol_detector.visualize(vis_image, features.symbols)
        
        if show_ocr and features.ocr_results and self.ocr_extractor:
            vis_image = self.ocr_extractor.visualize(vis_image, features.ocr_results)
        
        return vis_image


# Convenience function
def recognize(
    image: Union[str, np.ndarray],
    top_n: int = 5
) -> RecognitionResult:
    """
    Quick recognition without creating pipeline object.
    
    Args:
        image: Image file path or numpy array.
        top_n: Return top N predictions.
    
    Returns:
        RecognitionResult object.
    """
    pipeline = ManufacturingPipeline()
    return pipeline.recognize(image, top_n=top_n)
