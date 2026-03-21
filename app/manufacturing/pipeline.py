"""
Manufacturing Process Recognition Pipeline (VLM-only).

End-to-end workflow:
1. Load image (from file or numpy array)
2. VLM descriptive analysis (via LM Studio)
3. RAG retrieval & self-correction
4. Return results with diagnostics
"""

from typing import Optional, Union, List, Dict, Any, Sequence
from pathlib import Path
import numpy as np
import cv2
import time
import re
import json

from .schema import (
    ExtractedFeatures,
    GeometryFeatures,
    RecognitionResult,
    ProcessPrediction
)
from .extractors import (
    VisualEmbedder,
    PDFImageExtractor,
    is_pdf_available
)
from .extractors.parent_parser import ParentImageParser, ParentImageContext
from .extractors.vlm_client import VLMClient
from .prompts import get_vlm_descriptive_prompt
from .decision.rule_router import plan_vision_skills, describe_skills


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
        use_visual: bool = False,  # Visual embeddings optional (expensive)
        use_vlm: bool = False,  # VLM analysis optional (requires LM Studio)
        enable_process_prediction: bool = True,
    ):
        """
        Initialize pipeline.
        
        Args:
            use_visual: Enable visual embedding (DINOv2).
            use_vlm: Enable VLM-based process recognition (requires LM Studio).
            enable_process_prediction: Enable process prediction via decision engine.
                [Compatibility parameter] This pipeline now always runs in VLM-only mode.
        """
        self.use_visual = use_visual
        self.use_vlm = use_vlm
        self.enable_process_prediction = enable_process_prediction

        # Initialize visual embedder (gracefully handle unavailability)
        self.visual_embedder = None
        if use_visual:
            try:
                self.visual_embedder = VisualEmbedder()
                # Check if it actually loaded successfully
                if self.visual_embedder.model is None:
                    print("Info: Visual embeddings unavailable")
                    self.visual_embedder = None
                    self.use_visual = False
            except Exception as e:
                print(f"Warning: Failed to initialize visual embedder: {e}")
                print("   Continuing without visual embeddings")
                self.visual_embedder = None
                self.use_visual = False
        
        # Initialize VLM client (gracefully handle unavailability)
        self.vlm_client = None
        if use_vlm:
            try:
                self.vlm_client = VLMClient()
                # Check if VLM service is available
                if not self.vlm_client.is_available():
                    print("Info: VLM service not available - LM Studio may not be running")
                    print("   Continuing with VLM disabled")
                    self.vlm_client = None
                    self.use_vlm = False
                else:
                    print("Info: VLM service connected successfully")
            except Exception as e:
                print(f"Warning: Failed to initialize VLM client: {e}")
                print("   Continuing with VLM disabled")
                self.vlm_client = None
                self.use_vlm = False
        
        # Initialize parent image parser (share VLM client)
        self.parent_parser = ParentImageParser(vlm_client=self.vlm_client)
        
        # Initialize PDF extractor (if available)
        self.pdf_extractor = None
        if is_pdf_available():
            try:
                self.pdf_extractor = PDFImageExtractor(target_dpi=300)
            except ImportError:
                pass  # PDF功能不可用
        

    def reset_vlm_client(self) -> None:
        """
        強制重建 VLMClient 實例，確保每次辨識都是全新連線。

        用途：每次使用者按下辨識按鈕時呼叫，防止 LM Studio 端隱性
        KV cache / session state 污染後續辨識結果。
        """
        if not self.use_vlm:
            return
        try:
            new_client = VLMClient()
            if new_client.is_available():
                self.vlm_client = new_client
                print("Info: VLMClient reset — fresh connection established")
            else:
                # LM Studio 暫時不可用，保留舊 client 避免崩潰
                print("Warning: VLM service unreachable during reset — keeping previous client")
        except Exception as e:
            print(f"Warning: VLMClient reset failed: {e}")

    @property
    def total_processes(self) -> int:
        """Compatibility property: process prediction is removed in VLM-only mode."""
        return 0
    
    def recognize(
        self,
        image: Optional[Union[str, np.ndarray]],
        parent_image: Optional[Union[str, np.ndarray]] = None,
        top_n: Optional[int] = None,
        min_confidence: float = 0.3,
        frequency_filter: Optional[List[str]] = None,
        use_rag: bool = False,
        child_images: Optional[Sequence[Union[str, Path, np.ndarray]]] = None,
        view_labels: Optional[List[str]] = None,
        bom_context: str = "",
        enable_process_prediction: Optional[bool] = None,
    ) -> RecognitionResult:
        """
        Recognize manufacturing processes from engineering drawing.
        
        Args:
            image: Child image file path or numpy array (BGR). REQUIRED.
            parent_image: Parent image file path or numpy array (BGR). OPTIONAL.
                         Contains global information (title block, technical notes, etc.)
            top_n: Return top N process predictions.
            min_confidence: Minimum confidence threshold for predictions.
            frequency_filter: List of frequencies to include (e.g., ["高", "中"]).
                            If None, all frequencies are included.
            use_rag: Enable RAG-based context augmentation.
            child_images: Optional list of child images for VLM context.
            view_labels: Optional list of view names matching child_images order
                         (e.g. ['Top', 'Front', 'Side']). Top and Front are treated
                         as primary evidence; Side/Iso as supporting reference.
            bom_context: Free-text BOM / global notes typed by user (injected into VLM prompt).
            enable_process_prediction: Per-call override for process prediction.
                If None, uses pipeline default from constructor.
        
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
                0.5
            )
            parent_context_text = self.parent_parser.analyze_parent_context(parent_img_array)
            if parent_context_text:
                try:
                    parent_context_payload = json.loads(parent_context_text)
                except (json.JSONDecodeError, TypeError):
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
        # 邏輯：只要任一視圖掃到符號 → 該零件確認需要此工序，立刻加入已知集合。後續視圖跳過已知符號減少重複比對消耗。
        system_anchors: List[str] = []
        try:
            from app.vision.symbol_matcher import SymbolMatcher
            _sym_matcher = SymbolMatcher()
            if _sym_matcher.symbol_names:  # 只在有模板時才掃描
                _confirmed: set = set()  # 已確認的符號名稱集合（跨視圖去重）
                _all_scan_targets: List[Union[str, Path, np.ndarray]] = list(vlm_images) if vlm_images else [img_array]
                for _vimg in _all_scan_targets:
                    # 若所有符號都已確認，提前結束
                    if len(_confirmed) == len(_sym_matcher.symbol_names):
                        break
                    # 將 path/str 轉為 np.ndarray
                    _scan_img: Optional[np.ndarray] = None
                    if isinstance(_vimg, np.ndarray):
                        _scan_img = _vimg
                    else:
                        try:
                            import cv2 as _cv2
                            _scan_img = _cv2.imread(str(_vimg))
                        except Exception:
                            pass
                    if _scan_img is None:
                        continue
                    _hits = _sym_matcher.match_symbols(_scan_img)
                    for _hit in _hits:
                        _name: str = _hit["name"]
                        if _name not in _confirmed:
                            _confirmed.add(_name)
                # 將確認的符號轉成強訊號字串注入 VLM
                for _name in _confirmed:
                    system_anchors.append(f"[CV-CONFIRMED] {_name}")
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

        # ── RAG 快速路徑：hash 命中 → 直接回傳知識庫修正結果，跳過 VLM ──
        if use_rag and image_path:
            try:
                from app.knowledge.manager import KnowledgeBaseManager
                _kb_early = KnowledgeBaseManager()
                _early_hash = _kb_early._calculate_hash(image_path)
                _hash_entry = None
                for _e in _kb_early.db:
                    if _e.get("image_hash") == _early_hash:
                        _hash_entry = _e
                if _hash_entry is not None:
                    _cached_desc = (
                        _hash_entry.get("features", {}).get("raw_vlm_description", "")
                        or _hash_entry.get("reasoning", "")
                    )
                    print(f"Info: RAG exact hash hit — skipping VLM, returning cached description ({len(_cached_desc)} chars)")
                    _hit = dict(_hash_entry)
                    _hit["_match_type"] = "exact_hash"
                    _hit["_confidence"] = 1.0
                    _kb_early._attach_rag_priors([_hit])
                    processing_time = time.time() - start_time
                    return RecognitionResult(
                        predictions=[],
                        features=ExtractedFeatures(
                            raw_vlm_description=_cached_desc,
                        ),
                        parent_context=parent_context,
                        total_time=processing_time,
                        rag_references=[_hit],
                        warnings=["RAG exact hash match — 使用知識庫已修正描述（跳過 VLM）"],
                    )
            except Exception as _hash_err:
                print(f"Warning: RAG early hash check failed: {_hash_err}")

        # 組裝初次 VLM prompt（帶入 system_anchors，不論 RAG 是否啟用）
        # Bug fix: parent_prompt 原本沒帶 system_anchors，導致有 BOM/父圖時
        # CV-CONFIRMED 符號被靜默丟棄。現在統一用 get_vlm_descriptive_prompt 重建。
        if parent_prompt and system_anchors:
            _initial_prompt = get_vlm_descriptive_prompt(
                bom_context=bom_context or parent_context_text,
                system_anchors=system_anchors,
            )
            # 保留父圖全域背景注入
            structure = parent_context_payload.get("3d_structure")
            if structure:
                _initial_prompt = (
                    f"【全域幾何背景】 此零件為一個 {structure}。"
                    "請基於此背景分析當前圖片的製程與特徵。\n\n"
                    f"{_initial_prompt}"
                )
            parent_report = self._build_parent_report(parent_context, parent_context_payload)
            if parent_report:
                _initial_prompt = f"【父圖全域分析報告】{parent_report}\n\n{_initial_prompt}"
        elif parent_prompt:
            _initial_prompt = parent_prompt
        elif system_anchors:
            # fix: bom_context 必須一併帶入，避免有符號時 bom 被静默丟棄
            _initial_prompt = get_vlm_descriptive_prompt(bom_context=bom_context, system_anchors=system_anchors)
        else:
            _initial_prompt = get_vlm_descriptive_prompt(bom_context=bom_context) if bom_context else ""

        features = self._extract_features(
            img_array,
            image_path=image_path,
            prompt_override=_initial_prompt,
            vlm_images=vlm_images,
            view_labels=view_labels
        )

        rag_references: List[Dict[str, Any]] = []
        rag_context_text = ""

        # RAG retrieval: FAISS 語意搜尋（hash 已在上方快速路徑處理過）
        if use_rag:
            try:
                from app.knowledge.manager import KnowledgeBaseManager
                kb = KnowledgeBaseManager()
                _vlm_feats = features.vlm_analysis if isinstance(features.vlm_analysis, dict) else {}
                similar_cases = kb.retrieve_similar(
                    _vlm_feats,
                    image_path=image_path or "",
                    top_k=3,
                    raw_vlm_text=features.raw_vlm_description or "",
                    query_image=img_array,
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
        # 保存第一輪 VLM 輸出，供 diff 比較用
        if features.raw_vlm_description:
            features.raw_vlm_description_v1 = features.raw_vlm_description

        # If RAG context exists, re-run VLM with injected prompt
        if rag_context_text and self.vlm_client:
            try:
                input_images: List[Union[str, Path, np.ndarray]] = list(vlm_images)
                # Bug fix: 原本寫死 parent_context_text，使用者手動輸入的 bom_context 會被丟棄
                _effective_bom_2nd = bom_context or parent_context_text
                prompt = get_vlm_descriptive_prompt(bom_context=_effective_bom_2nd, rag_context=rag_context_text, system_anchors=system_anchors)
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
        
        # Process prediction has been removed; keep empty list for compatibility.
        prediction_enabled = (
            self.enable_process_prediction
            if enable_process_prediction is None
            else enable_process_prediction
        )
        predictions: List[ProcessPrediction] = []
        warnings: List[str] = []
        if prediction_enabled:
            warnings.append("Process prediction is disabled in VLM-only mode.")
        # VLM 品質驗證 warning（最終版本，可能經過 RAG 修正）
        if features.raw_vlm_description:
            _final_issues = ManufacturingPipeline._validate_vlm_output(features.raw_vlm_description)
            for issue in _final_issues:
                warnings.append(f"VLM 輸出品質：{issue}")
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Create result (include parent_context if available)
        result = RecognitionResult(
            predictions=predictions,
            features=features,
            parent_context=parent_context,
            total_time=processing_time,
            rag_references=rag_references,
            warnings=warnings,
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
        image_path: Optional[str] = None,
        prompt_override: str = "",
        vlm_images: Optional[Sequence[Union[str, Path, np.ndarray]]] = None,
        view_labels: Optional[List[str]] = None
    ) -> ExtractedFeatures:
        """
        Extract all features from image.
        
        Args:
            image: Input image (BGR).
            image_path: Optional image file path (for VLM).
        
        Returns:
            ExtractedFeatures object.
        """
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
                    # 結構驗證：檢查 VLM 輸出是否符合 3-section 格式
                    _issues = ManufacturingPipeline._validate_vlm_output(vlm_analysis)
                    if _issues:
                        print(f"Warning: VLM output quality issues: {_issues}")
                else:
                    print("Warning: VLM analysis returned None")
            except Exception as e:
                print(f"Warning: VLM analysis failed: {e}")
                vlm_analysis = None
        
        return ExtractedFeatures(
            ocr_results=[],
            geometry=GeometryFeatures(),
            symbols=[],
            visual_embedding=visual_embedding,
            tolerances=[],
            raw_vlm_description=vlm_analysis,
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
            r'\b\d+\.?\d*\s*(?:mm|cm|m|in|inch|inches|\xb0|deg|millimeters?|centimeters?|meters?|inches?)\b',
            '',
            raw,
            flags=re.IGNORECASE
        )
        # 清除帶連字號的形式：e.g. "110-millimeter", "4-mm"
        _cleaned = re.sub(
            r'\b\d+\.?\d*[-\u2011](?:mm|cm|millimeters?|centimeters?)\b',
            '',
            _cleaned,
            flags=re.IGNORECASE
        )
        # 清除 「數字 + 空格 + 全拼單位」殘留（避免漏掉 "110 millimeters" 後的孤立數字）
        _cleaned = re.sub(r'\b(approximately|about|around|roughly|nearly|over|under)\s+\d+\.?\d*\b', r'\1', _cleaned, flags=re.IGNORECASE)
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
        # 備援截斷：Section 4+ 之後的內容全部丟棄（3-section 架構，Section 3 是最後一節）
        _parts = re.split(r'(?m)^(?:###\s+)?[4-9]\.', _cleaned)
        if len(_parts) > 1:
            _cleaned = _parts[0].rstrip()
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

    @staticmethod
    def _validate_vlm_output(text: str) -> List[str]:
        """Validate VLM output structure and return a list of issues (empty = OK).

        Checks:
        1. All 3 required sections present (### 1, ### 2, ### 3)
        2. Section 2 contains True/False answers
        3. At least one Tier-1 vocabulary term appears
        """
        issues: List[str] = []
        if not text or len(text.strip()) < 50:
            issues.append("VLM 輸出過短（< 50 字元）")
            return issues

        # Section presence check
        for sec_num in [1, 2, 3]:
            pattern = rf'(?m)^(?:###?\s*)?{sec_num}\.'
            if not re.search(pattern, text):
                issues.append(f"缺少 Section {sec_num}")

        # Section 2: should contain True or False
        sec2_match = re.search(r'(?m)^(?:###?\s*)?2\.', text)
        if sec2_match:
            sec3_match = re.search(r'(?m)^(?:###?\s*)?3\.', text)
            sec2_end = sec3_match.start() if sec3_match else len(text)
            sec2_body = text[sec2_match.end():sec2_end]
            if not re.search(r'\b(True|False)\b', sec2_body):
                issues.append("Section 2 缺少 True/False 判斷")

        # Tier-1 vocabulary check
        _tier1 = [
            "flat plate", "rectangular", "l-shaped", "u-shaped", "z-shaped",
            "hat channel", "box", "flange", "rib", "chamfer", "fillet",
            "thru-hole", "threaded hole", "countersink", "weld symbol",
            "surface finish", "notch", "cutout", "emboss", "louver",
        ]
        text_lower = text.lower()
        if not any(term in text_lower for term in _tier1):
            issues.append("未使用任何 Tier-1 標準詞彙")

        return issues

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
    
# Convenience function
def recognize(
    image: Union[str, np.ndarray],
    top_n: int = 5,
    enable_process_prediction: bool = True,
) -> RecognitionResult:
    """
    Quick recognition without creating pipeline object.
    
    Args:
        image: Image file path or numpy array.
        top_n: Return top N predictions.
        enable_process_prediction: Enable process prediction in quick call.
    
    Returns:
        RecognitionResult object.
    """
    pipeline = ManufacturingPipeline(enable_process_prediction=enable_process_prediction)
    return pipeline.recognize(image, top_n=top_n, enable_process_prediction=enable_process_prediction)
