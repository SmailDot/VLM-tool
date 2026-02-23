"""
NKUST 製程辨識系統 - Manufacturing Process Recognition Tool
工程圖紙製程辨識核心應用

重構版本：以製程辨識為核心，移除所有影像辨識演算法相關功能
"""

# ==================== 重要：PaddleOCR 環境變數設定 ====================
# 必須在任何 import 之前設定
import os
# 問題 1: 禁用 PaddleX model source check（避免 modelscope/PyTorch DLL 錯誤）
os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'
# 問題 2: 禁用 OneDNN 後端（避免 PIR 相容性錯誤）
os.environ['FLAGS_use_mkldnn'] = 'False'
os.environ['FLAGS_use_onednn'] = 'False'

import streamlit as st
import cv2
import numpy as np
import time
import tempfile
from typing import Dict, List
from PIL import Image

# 製程辨識核心模組
from app.manufacturing import ManufacturingPipeline

# UI 樣式
from components.style import apply_custom_style

# 製程管理界面
from components.process_manager import render_process_manager
from components.sidebar import render_recognition_sidebar

# ==================== Page Config ====================

st.set_page_config(
    page_title="製程辨識系統",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

apply_custom_style()

# ==================== Session State ====================

# 初始化製程辨識管線 (延遲載入)
if 'mfg_pipeline' not in st.session_state:
    # Initialize pipeline early to make process_defs available for smart matching
    # This lightweight initialization only loads process library, no heavy extractors yet
    st.session_state.mfg_pipeline = ManufacturingPipeline(
        use_ocr=False,  # Will be reconfigured on first recognition
        use_geometry=False,
        use_symbols=False,
        use_visual=False,
        use_vlm=False
    )

if 'uploaded_drawing' not in st.session_state:
    st.session_state.uploaded_drawing = None

if 'uploaded_drawings' not in st.session_state:
            st.session_state.uploaded_drawings = []

# 新增父圖支援
if 'parent_drawing' not in st.session_state:
    st.session_state.parent_drawing = None
    
if 'recognition_result' not in st.session_state:
    st.session_state.recognition_result = None

if 'use_rag' not in st.session_state:
    st.session_state.use_rag = False

if 'use_vlm' not in st.session_state:
    st.session_state.use_vlm = False

if 'min_confidence' not in st.session_state:
    st.session_state.min_confidence = 0.25

if 'temp_file_path' not in st.session_state:
    st.session_state.temp_file_path = None

# 暫存區機制 (Batch Editing) - 必須在 editing_predictions 之前初始化
if 'pending_changes' not in st.session_state:
    st.session_state.pending_changes = []  # List[Dict]: [{"action": "add/remove", "process_id": str, "process_name": str, "reasoning": str, "confidence": float}]

if 'reasoning_input_key' not in st.session_state:
    st.session_state.reasoning_input_key = 0  # 用於清空理由欄位

if 'pending_unknown_process' not in st.session_state:
    st.session_state.pending_unknown_process = None  # Dict or None: {"input", "looks_like_id", "action", "reasoning"}

if 'is_corrected' not in st.session_state:
    st.session_state.is_corrected = False  # 標記是否已進行人工校正

# 儲存上次的設定 (用於特徵視覺化)
if 'last_settings' not in st.session_state:
    st.session_state.last_settings = {
        'use_ocr': False,
        'use_geometry': True,
        'use_symbols': True,
        'use_vlm': False,
        'show_visualization': False
    }

# ==================== Header ====================

st.markdown("""
<div style='text-align: center; padding: 2rem 0;'>
    <h1 style='color: #1f77b4; font-size: 3rem; margin-bottom: 0.5rem;'>
        NKUST 製程辨識系統
    </h1>
    
</div>
""", unsafe_allow_html=True)

st.divider()

# ==================== Main Tabs ====================

tab1, tab2, tab3 = st.tabs(["製程辨識", "知識庫管理", "製程管理"])

# ==================== Tab 1: 製程辨識 ====================

with tab1:
    # ==================== Main Layout ====================
    
    col_left, col_right = st.columns([1, 1.5], gap="large")

# ==================== Left Column: Upload & Settings ====================

with col_left:
    st.markdown("### 上傳工程圖紙")

    st.info("**雙圖辨識模式**: 父圖提供全域資訊（材質、客戶、特殊要求），子圖提供局部特徵（形狀、標註、符號）")

    # 父圖上傳（選填）
    st.markdown("#### 📂 上傳父圖/全域規範 (Parent Drawing/BOM)")
    parent_file = st.file_uploader(
        "選擇父圖檔案 (可選)",
        type=['jpg', 'jpeg', 'png', 'bmp', 'pdf'],
        help="父圖包含：標題欄、技術要求、材質說明、客戶資訊等全域文字。支援 PDF 格式（將以 300 DPI 高解析度渲染）",
        key="parent_uploader"
    )

    if parent_file is not None:
        # 檢查檔案類型
        file_extension = parent_file.name.lower().split('.')[-1]

        if file_extension == 'pdf':
            # PDF 檔案 → 使用 PDFImageExtractor
            st.info("📄 偵測到 PDF 檔案，正在以高解析度（300 DPI）渲染...")
            try:
                from app.manufacturing.extractors import PDFImageExtractor, is_pdf_available

                if not is_pdf_available():
                    st.error("PyMuPDF 未安裝，無法處理 PDF。請執行：pip install pymupdf")
                    st.session_state.parent_drawing = None
                else:
                    # 儲存 PDF 到臨時檔案
                    import tempfile
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                        tmp_file.write(parent_file.read())
                        tmp_pdf_path = tmp_file.name

                    # 提取高解析度圖片
                    pdf_extractor = PDFImageExtractor(target_dpi=300)
                    parent_image = pdf_extractor.extract_full_page(tmp_pdf_path, page_num=0)

                    # 清理臨時檔案
                    import os
                    os.unlink(tmp_pdf_path)

                    if parent_image is not None:
                        st.session_state.parent_drawing = parent_image
                        st.image(
                            cv2.cvtColor(parent_image, cv2.COLOR_BGR2RGB),
                            caption=f"父圖（PDF 渲染）: {parent_file.name}",
                            width="stretch"
                        )
                        h, w = parent_image.shape[:2]
                        st.success(f"✅ PDF 已成功轉換 | 解析度: {w} × {h} px (300 DPI)")
                    else:
                        st.error("無法渲染 PDF")
                        st.session_state.parent_drawing = None

            except Exception as e:
                st.error(f"PDF 處理失敗: {str(e)}")
                st.session_state.parent_drawing = None

        else:
            # 一般圖片檔案
            parent_bytes = np.asarray(bytearray(parent_file.read()), dtype=np.uint8)
            parent_image = cv2.imdecode(parent_bytes, cv2.IMREAD_COLOR)

            if parent_image is not None:
                st.session_state.parent_drawing = parent_image
                st.image(
                    cv2.cvtColor(parent_image, cv2.COLOR_BGR2RGB),
                    caption=f"父圖: {parent_file.name}",
                    width="stretch"
                )
                h, w = parent_image.shape[:2]
                st.caption(f"已載入父圖 | 尺寸: {w} × {h} px")
            else:
                st.error("無法讀取父圖")
                st.session_state.parent_drawing = None
    else:
        st.session_state.parent_drawing = None
        st.caption("未上傳父圖（將僅依子圖特徵判定）")

    # --- 多視角圖片上傳區 (替換原本的 file_uploader) ---
    st.markdown("### 👁️ 多視角零件圖上傳 (VLM 視覺重建)")
    st.caption("請上傳此零件的不同視角，幫助 VLM 建立 3D 空間認知 (可只上傳部分視角)")
    
    col1, col2, col3, col4 = st.columns(4)
    vlm_images = {}  # 收集多視角圖片
    
    with col1:
        top_view = st.file_uploader("1. 俯視圖 (Top View)", type=['png', 'jpg', 'jpeg'], key="top_view")
        if top_view: vlm_images["Top View"] = top_view
    with col2:
        front_view = st.file_uploader("2. 前視圖 (Front View)", type=['png', 'jpg', 'jpeg'], key="front_view")
        if front_view: vlm_images["Front View"] = front_view
    with col3:
        side_view = st.file_uploader("3. 側視圖 (Side View)", type=['png', 'jpg', 'jpeg'], key="side_view")
        if side_view: vlm_images["Side View"] = side_view
    with col4:
        iso_view = st.file_uploader("4. 立體/細部圖 (Detail/Iso)", type=['png', 'jpg', 'jpeg'], key="iso_view")
        if iso_view: vlm_images["Detail/Iso View"] = iso_view
    
    # 為了相容原本管線，將第一張上傳的圖設為主力分析圖
    if vlm_images:
        uploaded_files = list(vlm_images.values())  # 所有視角的圖片
    else:
        uploaded_files = []
    
    if uploaded_files:
        drawing_images: List[np.ndarray] = []
        drawing_names: List[str] = []

        for uploaded_file in uploaded_files:
            file_extension = uploaded_file.name.lower().split('.')[-1]
            drawing_image = None
            
            if file_extension == 'pdf':
                st.info("📄 偵測到 PDF 檔案，正在以高解析度（300 DPI）渲染...")
                try:
                    from app.manufacturing.extractors import PDFImageExtractor, is_pdf_available
                    
                    if not is_pdf_available():
                        st.error("PyMuPDF 未安裝，無法處理 PDF。請執行：pip install pymupdf")
                    else:
                        import tempfile
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                            tmp_file.write(uploaded_file.read())
                            tmp_pdf_path = tmp_file.name
                        
                        pdf_extractor = PDFImageExtractor(target_dpi=300)
                        drawing_image = pdf_extractor.extract_full_page(tmp_pdf_path, page_num=0)
                        
                        import os
                        os.unlink(tmp_pdf_path)
                
                except Exception as e:
                    st.error(f"PDF 處理失敗: {str(e)}")
            
            else:
                file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
                drawing_image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            
            if drawing_image is not None:
                drawing_images.append(drawing_image)
                drawing_names.append(uploaded_file.name)
        
        if drawing_images:
            primary_image = drawing_images[0]
            
            st.session_state.uploaded_drawing = primary_image
            st.session_state.uploaded_drawings = drawing_images

            # Save all temp images for knowledge base
            temp_paths = []
            for idx, img in enumerate(drawing_images):
                with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{idx}.png") as tmp_image:
                    cv2.imwrite(tmp_image.name, img)
                    temp_paths.append(tmp_image.name)
            st.session_state.temp_file_path = temp_paths[0]  # Primary image (backward compatibility)
            st.session_state.temp_file_paths = temp_paths  # All images
            
            # 顯示圖紙預覽
            for idx, drawing_image in enumerate(drawing_images):
                st.image(
                    cv2.cvtColor(drawing_image, cv2.COLOR_BGR2RGB),
                    caption=f"圖紙 {idx + 1}: {drawing_names[idx]}",
                    width="stretch"
                )
                h, w = drawing_image.shape[:2]
                st.caption(
                    f"尺寸: {w} × {h} px | 檔案大小: {uploaded_files[idx].size / 1024:.1f} KB"
                )
            
            # ==================== VLM 形狀描述 ====================
            st.markdown("### 🔍 VLM 零件幾何描述")
            st.caption("讓 VLM 根據上傳的多視角圖，描述它所『看到』並『組合』出來的零件形狀")

            # 初始化 session_state key
            if "vlm_shape_description" not in st.session_state:
                st.session_state.vlm_shape_description = None

            if st.button("🧠 請 VLM 描述零件形狀", use_container_width=True):
                from app.manufacturing.extractors.vlm_client import VLMClient
                from app.manufacturing.prompts import get_vlm_descriptive_prompt
                _vlm = VLMClient()
                if not _vlm.is_available():
                    st.warning("⚠️ VLM 服務未運行 — 請確認 LM Studio 已啟動 (http://localhost:1234)")
                else:
                    with st.spinner("VLM 正在分析並組合多視角圖形... 請稍候"):
                        _images = list(st.session_state.temp_file_paths)
                        _prompt = get_vlm_descriptive_prompt()
                        _desc = _vlm.analyze_image(_images, _prompt, response_format="text", temperature=0.1, max_tokens=1500)
                        if _desc:
                            st.session_state.vlm_shape_description = _desc
                        else:
                            st.session_state.vlm_shape_description = None
                            st.error("VLM 未回傳結果，請確認模型已載入")

            if st.session_state.vlm_shape_description:
                with st.expander("📋 VLM 零件形狀描述報告", expanded=True):
                    st.markdown(st.session_state.vlm_shape_description)
            st.divider()
            
            # ==================== 辨識設定 ====================
            st.markdown("### 辨識設定")
            
            with st.expander("特徵提取選項", expanded=True):
                use_ocr = st.checkbox(
                    "OCR 文字辨識",
                    value=False,
                    help="需要安裝 PaddlePaddle (可選功能)"
                )
                
                use_geometry = st.checkbox(
                    "幾何特徵分析",
                    value=True,
                    help="分析線條、孔洞、折彎線等幾何特徵 (建議啟用)"
                )
                
                use_symbols = st.checkbox(
                    "符號辨識",
                    value=True,
                    help="辨識焊接符號、表面處理標記等"
                )
                
                use_vlm = st.session_state.use_vlm

                # VLM 狀態檢查
                if use_vlm:
                    from app.manufacturing.extractors.vlm_client import VLMClient
                    try:
                        vlm_test = VLMClient()
                        if vlm_test.is_available():
                            st.success("✅ VLM 服務已連接 (LM Studio)")
                        else:
                            st.warning("⚠️ VLM 服務未運行 - 請確認 LM Studio 已啟動 (http://localhost:1234)")
                    except Exception as e:
                        st.error(f"❌ VLM 初始化失敗: {str(e)}")
            
            with st.expander("進階選項", expanded=False):
                st.markdown("**頻率過濾** (選擇要顯示的製程頻率)")
                freq_options = st.multiselect(
                    "製程頻率",
                    options=["高", "中", "低", "無"],
                    default=["高", "中"],
                    help="只顯示選定頻率的製程。高=常用、中=中等、低=少用、無=未分類"
                )
                
                show_visualization = st.checkbox(
                    "顯示特徵視覺化",
                    value=False,
                    help="在圖紙上標註檢測到的特徵"
                )
                
                # 儲存設定到 session_state
                st.session_state.last_settings = {
                    'use_ocr': use_ocr,
                    'use_geometry': use_geometry,
                    'use_symbols': use_symbols,
                    'use_vlm': use_vlm,
                    'show_visualization': show_visualization
                }
            
            st.divider()
            
            # ==================== 執行辨識 ====================
            if st.button("🚀 開始辨識製程", type="primary", use_container_width=True):
                with st.spinner("正在分析工程圖紙..."):
                    try:
                        # Reconfigure pipeline with user's selected options
                        # Pipeline was initialized early with defaults, now apply actual settings
                        st.session_state.mfg_pipeline = ManufacturingPipeline(
                            use_ocr=use_ocr,
                            use_geometry=use_geometry,
                            use_symbols=use_symbols,
                            use_visual=False,  # DINOv2 可選 (耗時)
                            use_vlm=use_vlm  # VLM 視覺語言模型 (實驗功能)
                        )
                        
                        # 執行辨識（支援雙圖模式）
                        start_time = time.time()
                        
                        # 檢查是否有父圖
                        parent_img = st.session_state.parent_drawing
                        if parent_img is not None:
                            st.info("雙圖模式: 正在解析父圖全域資訊...")
                        
                        result = st.session_state.mfg_pipeline.recognize(
                            primary_image,
                            parent_image=parent_img,  # 傳遞父圖
                            top_n=None,
                            min_confidence=st.session_state.min_confidence,
                            frequency_filter=freq_options if freq_options else None,
                            use_rag=st.session_state.use_rag,
                            child_images=st.session_state.uploaded_drawings
                        )
                        elapsed = time.time() - start_time
                        
                        st.session_state.recognition_result = result
                        
                        if parent_img is not None:
                            st.success(f"雙圖辨識完成！處理時間: {elapsed:.2f} 秒")
                        else:
                            st.success(f"辨識完成！處理時間: {elapsed:.2f} 秒")
                        st.rerun()
                        
                    except ImportError as e:
                        st.error(f"模組載入失敗: {str(e)}")
                        st.info("請確認已安裝相關依賴套件 (參考 requirements.txt)")
                    except Exception as e:
                        st.error(f"辨識過程發生錯誤: {str(e)}")
                        with st.expander("查看錯誤詳情"):
                            import traceback
                            st.code(traceback.format_exc())
        else:
            st.error("無法讀取圖片，請確認檔案格式正確")
    else:
        # 無圖紙時顯示說明
        st.info("請上傳工程圖紙以開始製程辨識")
        
        with st.expander("使用說明", expanded=True):
            st.markdown("""
            ### 系統功能
            - 自動分析工程圖紙內容
            - 幾何特徵辨識 (線條、孔洞、折彎線)
            - 符號辨識 (焊接符號、表面處理標記)
            - OCR 文字辨識 (可選)
            - 製程推薦 (多種製程類型)
            
            ### 支援製程類別
            - **切割**: 雷射切割、水刀切割、剪板機等
            - **折彎**: 折彎、滾圓、滾弧等
            - **焊接**: 點焊、氬焊、電焊、CO2焊接等
            - **表面處理**: 噴砂、烤漆、鍍鋅、陽極處理等
            - **組裝**: 自攻牙、螺絲、鉚接、拉釘等
            - **檢驗**: 成品全檢、尺寸檢驗、外觀檢驗等
            
            ### 建議圖紙品質
            - **解析度**: 300 DPI 以上
            - **格式**: JPG, PNG, BMP
            - **類型**: 工程圖 (白底黑線)
            - **內容**: 包含完整標註與符號
            """)

# ==================== Right Column: Results ====================

with col_right:
    st.markdown("### 辨識結果")
    
    if st.session_state.recognition_result is not None:
        result = st.session_state.recognition_result
        
        # 顯示摘要資訊
        col_info1, col_info2, col_info3 = st.columns(3)
        
        with col_info1:
            st.metric(
                "處理時間",
                f"{result.total_time:.2f}s"
            )
        
        with col_info2:
            st.metric(
                "檢測到製程",
                len(result.predictions)
            )
        
        with col_info3:
            if result.predictions:
                top_conf = result.predictions[0].confidence * 100
                st.metric(
                    "最高信心度",
                    f"{top_conf:.1f}%"
                )
        
        st.divider()

        # === [新增] 製程預測與人工校正 (互動卡片清單) ===
        st.markdown("### 製程預測與人工校正")

        pipeline = st.session_state.mfg_pipeline
        process_defs: Dict[str, Dict[str, object]] = {}
        if pipeline is not None:
            process_defs = {
                pid: {
                    "name": getattr(proc, "name", proc.get("name", ""))
                    if isinstance(proc, dict)
                    else getattr(proc, "name", "")
                }
                for pid, proc in pipeline.decision_engine.processes.items()
            }

        def _sorted_process_options() -> List[str]:
            def _sort_key(pid: str) -> tuple:
                prefix = pid[0] if pid else "Z"
                return (prefix, pid)

            return [
                f"{pid} - {process_defs[pid].get('name', '')}"
                for pid in sorted(process_defs.keys(), key=_sort_key)
            ]

        def _display_label(process_id: str) -> str:
            if not process_id:
                return ""
            name = process_defs.get(process_id, {}).get("name", "")
            return f"{process_id} - {name}" if name else process_id

        def _extract_id(label: str) -> str:
            if not isinstance(label, str):
                return ""
            return label.split(" - ")[0].strip()

        options = _sorted_process_options()

        if "editing_predictions" not in st.session_state:
            st.session_state.editing_predictions = []

        if "editing_source_signature" not in st.session_state:
            st.session_state.editing_source_signature = None

        signature = "|".join(
            [f"{p.process_id}:{p.confidence:.3f}:{p.reasoning}" for p in result.predictions]
        )

        if st.session_state.editing_source_signature != signature:
            st.session_state.editing_predictions = [
                {
                    "process_id": pred.process_id,
                    "process_name": pred.name,
                    "confidence": pred.confidence,
                    "reasoning": pred.reasoning
                }
                for pred in result.predictions
            ]
            st.session_state.editing_source_signature = signature

        # ========== A-B-C 單列表單 (Single-Row Form) ==========
        st.markdown("#### ⚙️ 製程修正表單")
        
        with st.form(key="correction_form", clear_on_submit=True, enter_to_submit=False):
            col_a, col_b, col_c, col_submit = st.columns([3, 2, 4, 1])
            
            with col_a:
                # 製程選單 - 格式: [代碼] 名稱
                process_options_formatted = [
                    f"[{pid}] {process_defs[pid].get('name', '')}"
                    for pid in sorted(process_defs.keys())
                ]
                selected_process_label = st.selectbox(
                    "A - 製程",
                    options=process_options_formatted,
                    help="支援搜尋代碼或名稱"
                )
                
                # 手動輸入代碼（選填）- Task 4 Integration
                manual_code = st.text_input(
                    "手動輸入代碼或名稱（選填）",
                    placeholder="如：X99 或 鑽孔",
                    help="若清單中沒有要的製程，可手動輸入代碼或名稱",
                    key="manual_code_input"
                )
            
            with col_b:
                # 動作選擇
                action_type = st.radio(
                    "B - 動作",
                    options=["新增 (Add)", "移除 (Remove)"],
                    index=0,
                    horizontal=True
                )
            
            with col_c:
                # 理由輸入 (使用 key 來控制清空)
                reasoning_input = st.text_input(
                    "C - 理由（RAG關鍵數據）",
                    placeholder="例如：BOM表分開列出，故非折彎...",
                    help="這段理由會記錄到知識庫，供 RAG 檢索使用",
                    key=f"reasoning_input_{st.session_state.reasoning_input_key}"
                )
            
            with col_submit:
                st.write("")  # 對齊用
                st.write("")  # 對齊用
                form_submitted = st.form_submit_button("▶️ 執行", use_container_width=True)
        
        # Enter-hook JS: 在手動輸入欄按 Enter 時，跳到理由欄
        import streamlit.components.v1 as components
        components.html("""
        <script>
        (function() {
            function hookEnterOnManualCode() {
                // Find all text inputs in the parent frame
                var allInputs = window.parent.document.querySelectorAll('input[type="text"]');
                allInputs.forEach(function(inp) {
                    var placeholder = inp.getAttribute('placeholder') || '';
                    var label = '';
                    // Try to find associated label
                    var wrapper = inp.closest('[data-testid="stTextInput"]');
                    if (wrapper) {
                        var labelEl = wrapper.querySelector('label');
                        if (labelEl) label = labelEl.textContent || '';
                    }
                    // Match the manual code input:
                    // by placeholder 'X99' OR label containing '手動輸入'
                    var isManualCodeInput = (
                        placeholder.indexOf('X99') !== -1 ||
                        label.indexOf('\u624b\u52d5\u8f38\u5165') !== -1
                    );
                    if (isManualCodeInput) {
                        if (!inp.__enterHooked) {
                            inp.__enterHooked = true;
                            inp.addEventListener('keydown', function(e) {
                                if (e.key === 'Enter') {
                                    e.preventDefault();
                                    e.stopPropagation();
                                    // Find the reasoning input (C column) and focus it
                                    // Match by placeholder OR label text for robustness
                                    var allInputs2 = window.parent.document.querySelectorAll('input[type="text"]');
                                    for (var i = 0; i < allInputs2.length; i++) {
                                        var ph2 = allInputs2[i].getAttribute('placeholder') || '';
                                        var lbl2 = '';
                                        var w2 = allInputs2[i].closest('[data-testid="stTextInput"]');
                                        if (w2) {
                                            var lEl2 = w2.querySelector('label');
                                            if (lEl2) lbl2 = lEl2.textContent || '';
                                        }
                                        var isReasoningInput = (
                                            ph2.indexOf('BOM') !== -1 ||
                                            ph2.indexOf('\u975e\u6298\u5f4e') !== -1 ||
                                            lbl2.indexOf('C - \u7406\u7531') !== -1 ||
                                            lbl2.indexOf('RAG') !== -1
                                        );
                                        if (isReasoningInput) {
                                            allInputs2[i].focus();
                                            break;
                                        }
                                    }
                                }
                            });
                        }
                    }
                });
            }
            // Run after DOM is ready, and retry to handle dynamic rendering
            setTimeout(hookEnterOnManualCode, 800);
            setTimeout(hookEnterOnManualCode, 1600);
            setTimeout(hookEnterOnManualCode, 3000);
        })();
        </script>
        """, height=0)
        # 處理表單提交 - Task 4 Smart Matching Logic
        if form_submitted:
            # 決定製程代碼 - 優先使用手動輸入
            target_process_id = None
            target_process_name = "(未知製程)"
            is_new_process = False
            
            if manual_code.strip():
                # Task 4: Smart matching logic
                manual_input = manual_code.strip()
                matched_id = None
                matched_name = None
                
                # Try to match by ID first (normalized, case-insensitive)
                manual_normalized = manual_input.strip().upper()
                norm_id_map = {k.strip().upper(): k for k in process_defs.keys()}
                if manual_normalized in norm_id_map:
                    matched_id = norm_id_map[manual_normalized]
                    matched_name = process_defs[matched_id].get("name", "")
                else:
                    # Check if input matches a process name (strip + case-insensitive)
                    manual_lower = manual_input.strip().lower()
                    for pid, pdata in process_defs.items():
                        pname = pdata.get("name", "")
                        if isinstance(pname, str) and pname.strip().lower() == manual_lower:
                            matched_id = pid
                            matched_name = pname
                            break
                if matched_id:
                    # Found existing process
                    target_process_id = matched_id
                    target_process_name = matched_name
                else:
                    # Unknown process - store in session_state for persistent UI outside form
                    is_new_process = True
                    looks_like_id = len(manual_input.strip()) <= 5 and any(c.isdigit() for c in manual_input)
                    st.session_state.pending_unknown_process = {
                        "input": manual_input.strip(),
                        "looks_like_id": looks_like_id,
                        "action": "add" if "新增" in action_type else "remove",
                        "reasoning": reasoning_input if reasoning_input else ""
                    }
            else:
                # 從選單提取代碼 [I01] 雷射切割 -> I01
                import re
                match = re.match(r"\[([^\]]+)\]", selected_process_label)
                if match:
                    target_process_id = match.group(1)
                    target_process_name = process_defs.get(target_process_id, {}).get("name", "(未知製程)")
                else:
                    st.error("無法解析選擇的製程")
                    target_process_id = None
            
            if target_process_id and not is_new_process:
                action = "add" if "新增" in action_type else "remove"
                
                # 檢查是否已在暫存區
                existing_pending = [p for p in st.session_state.pending_changes if p["process_id"] == target_process_id and p["action"] == action]
                
                if existing_pending:
                    st.warning(f"⚠️ {target_process_id} 的 {action} 操作已在待確認區")
                else:
                    # 新增到暫存區
                    st.session_state.pending_changes.append({
                        "action": action,
                        "process_id": target_process_id,
                        "process_name": target_process_name,
                        "reasoning": reasoning_input if reasoning_input else "",
                        "confidence": 1.0  # 新增時預設 100%
                    })
                    
                    # 清空理由欄位 (遞增 key)
                    st.session_state.reasoning_input_key += 1
                    
                    # Task 3: No st.rerun() - let Streamlit naturally refresh
        
        # ========== 未知製程補充 UI（持久顯示，不受 form 提交影響） ==========
        if st.session_state.pending_unknown_process:
            pup = st.session_state.pending_unknown_process
            st.markdown("---")
            st.warning(f"⚠️ 未知製程：請補充資料後加入待確認區")
            if pup["looks_like_id"]:
                new_name_val = st.text_input(
                    f"請輸入製程代碼 **{pup['input']}** 的中文名稱",
                    key="unknown_process_name_supplement",
                    placeholder="例如: 鑽孔"
                )
                col_uk1, col_uk2 = st.columns([2, 1])
                with col_uk1:
                    if st.button("確認並加入待確認區", key="confirm_unknown_from_id", type="primary"):
                        if new_name_val.strip():
                            action_uk = pup["action"]
                            existing_uk = [p for p in st.session_state.pending_changes if p["process_id"] == pup["input"].upper() and p["action"] == action_uk]
                            if not existing_uk:
                                st.session_state.pending_changes.append({
                                    "action": action_uk,
                                    "process_id": pup["input"].upper(),
                                    "process_name": new_name_val.strip(),
                                    "reasoning": pup["reasoning"],
                                    "confidence": 1.0
                                })
                            st.session_state.pending_unknown_process = None
                            st.session_state.reasoning_input_key += 1
                            st.toast(f"已加入待確認區：{pup['input'].upper()} - {new_name_val.strip()}")
                        else:
                            st.error("請輸入製程名稱")
                with col_uk2:
                    if st.button("取消", key="cancel_unknown_process_id"):
                        st.session_state.pending_unknown_process = None
            else:
                new_id_val = st.text_input(
                    f"請輸入製程名稱 **{pup['input']}** 的代碼",
                    key="unknown_process_id_supplement",
                    placeholder="例如: F01"
                )
                col_uk3, col_uk4 = st.columns([2, 1])
                with col_uk3:
                    if st.button("確認並加入待確認區", key="confirm_unknown_from_name", type="primary"):
                        if new_id_val.strip():
                            action_uk = pup["action"]
                            existing_uk = [p for p in st.session_state.pending_changes if p["process_id"] == new_id_val.strip().upper() and p["action"] == action_uk]
                            if not existing_uk:
                                st.session_state.pending_changes.append({
                                    "action": action_uk,
                                    "process_id": new_id_val.strip().upper(),
                                    "process_name": pup["input"],
                                    "reasoning": pup["reasoning"],
                                    "confidence": 1.0
                                })
                            st.session_state.pending_unknown_process = None
                            st.session_state.reasoning_input_key += 1
                            st.toast(f"已加入待確認區：{new_id_val.strip().upper()} - {pup['input']}")
                        else:
                            st.error("請輸入製程代碼")
                with col_uk4:
                    if st.button("取消", key="cancel_unknown_process_name"):
                        st.session_state.pending_unknown_process = None

        # ========== 待確認區 (Pending Changes) ==========
        if st.session_state.pending_changes:
            st.markdown("---")
            st.markdown("#### 待確認操作")
            
            with st.container():
                st.warning(f"📝 共有 {len(st.session_state.pending_changes)} 個待處理操作")
                
                for idx, change in enumerate(st.session_state.pending_changes):
                    action = change["action"]
                    pid = change["process_id"]
                    pname = change["process_name"]
                    reason = change.get("reasoning", "")
                    
                    # 根據動作類型選擇顏色和圖標（使用更深的顏色對比）
                    if action == "add":
                        icon = "➕"
                        color = "#c8e6c9"  # 更深的綠色背景
                        text_color = "#1b5e20"  # 更深的綠色文字
                        action_text = "新增"
                    else:  # remove
                        icon = "➖"
                        color = "#ffcdd2"  # 更深的紅色背景
                        text_color = "#b71c1c"  # 更深的紅色文字
                        action_text = "移除"
                    
                    # 顯示待確認項目
                    col_badge, col_remove = st.columns([10, 1])
                    
                    with col_badge:
                        badge_html = f"""
                        <div style='background-color:{color} !important; padding:8px 12px; border-radius:8px; margin:4px 0; 
                                    border-left:4px solid {text_color};'>
                            <span style='font-size:16px;'>{icon}</span>
                            <strong style='color:{text_color} !important;'>{action_text}</strong>
                            <span style='background-color:rgba(0,0,0,0.7) !important; color:#fff !important; padding:2px 8px; 
                                         border-radius:12px; margin:0 8px; font-weight:bold;'>[{pid}]</span>
                            <span style='color:{text_color} !important; font-weight:500;'>{pname}</span>
                            {f"<span style='color:{text_color} !important; font-size:0.9em; margin-left:8px; opacity:0.8;'>({reason})</span>" if reason else ""}
                        </div>
                        """
                        st.markdown(badge_html, unsafe_allow_html=True)
                    
                    with col_remove:
                        if st.button("❌", key=f"remove_pending_{idx}", help="撤銷此操作"):
                            st.session_state.pending_changes.pop(idx)
                            pass  # No rerun needed - Streamlit will naturally refresh
                
                # 新增：將待確認操作套用至當前製程清單（不儲存知識庫）
                st.markdown("---")
                col_apply, col_clear = st.columns([3, 1])
                with col_apply:
                    if st.button("📋 將以上製程套用至當前清單", use_container_width=True, type="primary"):
                        # 套用所有 pending_changes 到 editing_predictions
                        for change in st.session_state.pending_changes:
                            if change["action"] == "add":
                                # 新增製程到清單（如果不存在）
                                existing_ids = [p["process_id"] for p in st.session_state.editing_predictions]
                                if change["process_id"] not in existing_ids:
                                    st.session_state.editing_predictions.append({
                                        "process_id": change["process_id"],
                                        "process_name": change["process_name"],
                                        "confidence": change["confidence"],
                                        "reasoning": change["reasoning"] or "(人工新增)"
                                    })
                            elif change["action"] == "remove":
                                # 從清單移除製程
                                st.session_state.editing_predictions = [
                                    p for p in st.session_state.editing_predictions
                                    if p["process_id"] != change["process_id"]
                                ]
                        
                        # 清空待確認清單
                        st.session_state.pending_changes = []
                        st.toast("✅ 已套用至當前製程清單")
                        pass  # No rerun needed - Streamlit will naturally refresh
                
                with col_clear:
                    if st.button("🗑️ 清空", use_container_width=True):
                        st.session_state.pending_changes = []
                        pass  # No rerun needed
        
        # ========== 目前製程清單（彩色標籤顯示） ==========
        st.markdown("---")
        if st.session_state.is_corrected:
            st.markdown("#### 人工校正所需製程為以下")
        else:
            st.markdown("#### 製程預測與人工校正")
        
        if st.session_state.editing_predictions:
            # 渲染彩色標籤
            st.markdown("##### 當前製程清單")
            
            for idx, item in enumerate(st.session_state.editing_predictions):
                pid = item["process_id"]
                pname = item["process_name"]
                confidence = item["confidence"]
                reasoning = item.get("reasoning", "")
                
                # 根據信心度決定顏色（使用更深的顏色對比）
                if confidence >= 0.7:
                    bg_color = "#b2dfdb"  # 更深的青色背景
                    text_color = "#004d40"  # 更深的青色文字
                elif confidence >= 0.5:
                    bg_color = "#ffe0b2"  # 更深的橘色背景
                    text_color = "#e65100"  # 深橘色文字（保持）
                else:
                    bg_color = "#ffcdd2"  # 更深的紅色背景
                    text_color = "#b71c1c"  # 更深的紅色文字
                
                # 顯示標籤與信心度調整
                col_badge, col_conf, col_actions = st.columns([6, 2, 2])
                
                with col_badge:
                    badge_html = f"""
                    <div style='background-color:{bg_color} !important; color:{text_color} !important; padding:8px 12px; 
                                border-radius:12px; margin:4px 0; display:inline-block; 
                                border:2px solid {text_color};'>
                        <strong style='color:{text_color} !important;'>[{pid}]</strong> <span style='color:{text_color} !important;'>{pname}</span>
                        {f"<span style='font-size:0.85em; color:{text_color} !important; margin-left:8px; opacity:0.7;'>({reasoning[:30]}...)</span>" if len(reasoning) > 30 else f"<span style='font-size:0.85em; color:{text_color} !important; margin-left:8px; opacity:0.7;'>({reasoning})</span>" if reasoning else ""}
                    </div>
                    """
                    st.markdown(badge_html, unsafe_allow_html=True)
                
                with col_conf:
                    # 信心度調整滑桿
                    new_conf = st.slider(
                        "信心度",
                        min_value=0,
                        max_value=100,
                        value=int(confidence * 100),
                        step=5,
                        key=f"conf_{pid}_{idx}",
                        label_visibility="collapsed"
                    )
                    st.session_state.editing_predictions[idx]["confidence"] = new_conf / 100.0
                
                with col_actions:
                    st.caption(f"{int(confidence * 100)}%")
        else:
            st.info("目前清單為空，請使用上方表單新增製程")

        st.markdown("#### 定案並學習 (Save & Learn)")
        col_learn, col_undo = st.columns([3, 1])
        with col_learn:
            learn_clicked = st.button("定案並學習", use_container_width=True)
        with col_undo:
            undo_clicked = st.button("撤回", use_container_width=True)

        if learn_clicked:
            if not st.session_state.temp_file_path:
                st.error("找不到暫存圖片，請重新上傳圖檔")
            else:
                from app.knowledge.manager import KnowledgeBaseManager

                # ========== STEP 1: 套用所有 pending_changes 到 editing_predictions ==========
                for change in st.session_state.pending_changes:
                    if change["action"] == "add":
                        # 新增製程到清單（如果不存在）
                        existing_ids = [p["process_id"] for p in st.session_state.editing_predictions]
                        if change["process_id"] not in existing_ids:
                            st.session_state.editing_predictions.append({
                                "process_id": change["process_id"],
                                "process_name": change["process_name"],
                                "confidence": change["confidence"],
                                "reasoning": change["reasoning"] or "(人工新增)"
                            })
                    elif change["action"] == "remove":
                        # 從清單移除製程
                        st.session_state.editing_predictions = [
                            p for p in st.session_state.editing_predictions
                            if p["process_id"] != change["process_id"]
                        ]

                # Clear pending changes after applying
                st.session_state.pending_changes = []

                # ========== STEP 2: 建立最終製程清單與理由 ==========
                final_processes = [
                    item["process_id"]
                    for item in st.session_state.editing_predictions
                    if item.get("process_id")
                ]

                reasoning_lines = [
                    f"{item['process_id']}: {item.get('reasoning', '')}"
                    for item in st.session_state.editing_predictions
                    if item.get("process_id")
                ]
                
                # ========== STEP 3: 保存到知識庫 (Task 2: Multi-image support) ==========
                # Get all uploaded images (if multiple)
                additional_images = None
                if hasattr(st.session_state, 'temp_file_paths') and len(st.session_state.temp_file_paths) > 1:
                    additional_images = st.session_state.temp_file_paths

                kb_manager = KnowledgeBaseManager()
                kb_manager.add_entry(
                    image_path=st.session_state.temp_file_path,
                    features=result.features.vlm_analysis or {},
                    correct_processes=final_processes,
                    reasoning="\n".join(reasoning_lines),
                    additional_images=additional_images
                )
                
                # Show success message with count
                img_count = len(additional_images) if additional_images else 1
                st.toast(f"已保存至知識庫 ({img_count} 張圖片)")
                st.session_state.kb_save_success = True
                st.session_state.is_corrected = True
        
        if undo_clicked:
            # Clear all pending changes
            st.session_state.pending_changes = []
            pass  # No rerun needed - Streamlit will naturally refresh
        
        # Task 5: Post-learning confirmation dialog
        if st.session_state.get('kb_save_success', False):
            st.success("✅ 已成功保存至知識庫！")
            
            # Ask if user wants to re-run recognition
            st.info("💡 知識庫已更新，是否需要重新辨識以使用最新的知識庫？")
            
            col_rerun1, col_rerun2, col_rerun3 = st.columns([1, 1, 2])
            with col_rerun1:
                if st.button("🔄 是，重新辨識", type="primary", use_container_width=True):
                    # Re-run recognition with stored images and settings
                    if st.session_state.uploaded_drawing is not None:
                        with st.spinner("正在使用更新後的知識庫重新辨識..."):
                            try:
                                # Get stored settings
                                settings = st.session_state.get('last_settings', {})
                                use_ocr = settings.get('use_ocr', False)
                                use_geometry = settings.get('use_geometry', True)
                                use_symbols = settings.get('use_symbols', True)
                                use_vlm = settings.get('use_vlm', False)
                                
                                # Re-initialize pipeline with same settings
                                st.session_state.mfg_pipeline = ManufacturingPipeline(
                                    use_ocr=use_ocr,
                                    use_geometry=use_geometry,
                                    use_symbols=use_symbols,
                                    use_visual=False,
                                    use_vlm=use_vlm
                                )
                                
                                # Re-run recognition
                                start_time = time.time()
                                new_result = st.session_state.mfg_pipeline.recognize(
                                    st.session_state.uploaded_drawing,
                                    parent_image=st.session_state.get('parent_drawing'),
                                    top_n=None,
                                    min_confidence=st.session_state.min_confidence,
                                    frequency_filter=st.session_state.get('frequency_filters'),
                                    use_rag=st.session_state.use_rag,
                                    child_images=st.session_state.get('uploaded_drawings', [])
                                )
                                elapsed = time.time() - start_time
                                
                                # Update results and editing predictions
                                st.session_state.recognition_result = new_result
                                st.session_state.editing_predictions = [
                                    {
                                        "process_id": pred.process_id,
                                        "process_name": pred.name,
                                        "confidence": pred.confidence,
                                        "reasoning": pred.reasoning if pred.reasoning else ", ".join(
                                            pred.matched_text + pred.matched_symbols + pred.matched_geometry
                                        )
                                    }
                                    for pred in new_result.predictions
                                ]
                                
                                # Clear save success flag
                                st.session_state.kb_save_success = False
                                
                                st.success(f"✅ 重新辨識完成！處理時間: {elapsed:.2f} 秒")
                                st.rerun()
                                
                            except Exception as e:
                                st.error(f"重新辨識時發生錯誤: {str(e)}")
                                with st.expander("查看錯誤詳情"):
                                    import traceback
                                    st.code(traceback.format_exc())
                    else:
                        st.error("找不到上傳的圖片，請重新上傳")
            
            with col_rerun2:
                if st.button("❌ 不需要", use_container_width=True):
                    # Clear the flag without re-running
                    st.session_state.kb_save_success = False
                    pass  # No rerun needed - Streamlit will naturally refresh

        if st.session_state.use_rag and result.rag_references:
            with st.expander("本次推論參考的歷史案例 (RAG Context)"):
                for ref in result.rag_references:
                    st.info(
                        f"參考案例：{ref['features'].get('shape_description')}\n"
                        f"正確製程：{ref['correct_processes']}"
                    )
        
        # 顯示父圖注意事項（如果有的話）
        if result.parent_context and result.parent_context.important_notes:
            st.warning("⚠️ 父圖重要注意事項")
            
            # 顯示檢測到的語言
            if result.parent_context.detected_languages:
                langs_display = {
                    'chinese_cht': '繁體中文',
                    'ch': '簡體中文',
                    'en': '英文',
                    'japan': '日文',
                    'korean': '韓文'
                }
                detected_langs = [
                    langs_display.get(lang, lang)
                    for lang in result.parent_context.detected_languages
                    if isinstance(lang, str) and lang
                ]
                st.info(f"🌐 檢測到語言: {', '.join(detected_langs)}")
            
            # 顯示重要注意事項
            st.markdown("**重要提醒事項:**")
            for note in result.parent_context.important_notes:
                # 根據關鍵字決定圖示
                note_lower = note.lower()
                if any(kw in note_lower for kw in ['警告', 'warning', '禁止']):
                    icon = "🚫"
                elif any(kw in note_lower for kw in ['注意', 'caution', '小心']):
                    icon = "⚠️"
                elif any(kw in note_lower for kw in ['要求', 'requirement', '必須']):
                    icon = "✓"
                else:
                    icon = "•"
                
                st.markdown(f"{icon} {note}")
            
            # 可展開：標題欄完整內容
            if result.parent_context.title_block_text:
                with st.expander("📋 查看標題欄完整內容", expanded=False):
                    st.markdown("**標題欄所有文字:**")
                    for text in result.parent_context.title_block_text:
                        if text.strip():
                            st.text(f"  {text}")
            
            st.divider()
        
        # 診斷資訊
        with st.expander("診斷資訊 (Diagnostics)", expanded=False):
            # 基本診斷
            diag = {
                "total_time": result.total_time,
                "warnings": result.warnings,
                "errors": result.errors,
                "extraction_time": result.features.extraction_time
            }
            st.json(diag)
            
            # 特徵統計
            if result.features.geometry:
                st.markdown("**幾何特徵統計:**")
                geo = result.features.geometry
                
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    st.metric("檢測到線條", len(geo.lines))
                    st.metric("折彎線", len(geo.bend_lines))
                with col_d2:
                    st.metric("圓形", len(geo.circles))
                    st.metric("孔洞", len(geo.holes))
                
                st.metric("總形狀數", len(geo.contours))
            
            if result.features.ocr_results:
                st.markdown("**OCR 文字辨識結果:**")
                st.text(f"檢測到 {len(result.features.ocr_results)} 個文字區域")
                for ocr in result.features.ocr_results[:5]:  # 顯示前5個
                    st.caption(f"- {ocr.text} (信心度: {ocr.confidence:.2f})")
            
            if result.features.symbols:
                st.markdown("**符號辨識結果:**")
                st.text(f"檢測到 {len(result.features.symbols)} 個符號")
                for sym in result.features.symbols:
                    st.caption(f"- {sym.symbol_type} (信心度: {sym.confidence:.2f})")
            
            # VLM 分析結果 (NEW!)
            if result.features.vlm_analysis:
                st.markdown("**🤖 VLM 視覺語言模型分析:**")
                vlm = result.features.vlm_analysis
                
                # 形狀描述
                if vlm.get("shape_description"):
                    st.caption(f"形狀: {vlm['shape_description']}")
                
                # 複雜度
                if vlm.get("overall_complexity"):
                    st.caption(f"複雜度: {vlm['overall_complexity']}")
                
                # 建議製程
                if vlm.get("suggested_process_ids"):
                    st.caption(f"VLM 建議製程: {', '.join(vlm['suggested_process_ids'][:5])}")
                
                # 檢測特徵
                if vlm.get("detected_features"):
                    det_feat = vlm["detected_features"]
                    features_summary = []
                    if det_feat.get("geometry"):
                        features_summary.append(f"幾何 ({len(det_feat['geometry'])})")
                    if det_feat.get("symbols"):
                        features_summary.append(f"符號 ({len(det_feat['symbols'])})")
                    if det_feat.get("text_annotations"):
                        features_summary.append(f"文字 ({len(det_feat['text_annotations'])})")
                    if features_summary:
                        st.caption(f"檢測特徵: {', '.join(features_summary)}")
                
                # 推理依據（可展開查看）
                if vlm.get("reasoning"):
                    with st.expander("查看 VLM 推理依據"):
                        st.text(vlm["reasoning"])
            
            # 父圖上下文資訊
            if result.parent_context:
                st.markdown("**父圖上下文資訊:**")
                
                parent_info = {}
                if result.parent_context.material:
                    parent_info["材質"] = result.parent_context.material
                if result.parent_context.customer:
                    parent_info["客戶"] = result.parent_context.customer
                if result.parent_context.detected_languages:
                    parent_info["檢測語言"] = list(result.parent_context.detected_languages)
                if result.parent_context.important_notes:
                    parent_info["重要注意事項數量"] = len(result.parent_context.important_notes)
                if result.parent_context.title_block_text:
                    parent_info["標題欄文字數量"] = len(result.parent_context.title_block_text)
                
                st.json(parent_info)
        
        # 特徵視覺化
        if (st.session_state.last_settings.get('show_visualization', False) 
            and st.session_state.uploaded_drawing is not None
            and st.session_state.mfg_pipeline is not None):
            st.divider()
            st.markdown("#### 特徵視覺化")
            
            try:
                settings = st.session_state.last_settings
                vis_image = st.session_state.mfg_pipeline.visualize_features(
                    st.session_state.uploaded_drawing,
                    show_ocr=settings.get('use_ocr', False),
                    show_geometry=settings.get('use_geometry', True),
                    show_symbols=settings.get('use_symbols', True)
                )
                
                st.image(
                    cv2.cvtColor(vis_image, cv2.COLOR_BGR2RGB),
                    caption="特徵標註圖",
                    width="stretch"
                )
            except Exception as e:
                st.error(f"視覺化失敗: {str(e)}")
    
    else:
        # 無結果時顯示佔位內容
        st.info("上傳工程圖紙並執行辨識後，結果將顯示在此處")
        
        # 顯示系統資訊
        with st.expander("📈 系統資訊", expanded=False):
            # 動態取得製程數量
            process_count = "載入中..."
            if st.session_state.mfg_pipeline is not None:
                try:
                    process_count = f"{st.session_state.mfg_pipeline.total_processes} 種"
                except:
                    process_count = "無法取得"
            
            st.markdown(f"""
            **製程辨識系統 v2.1**
            
            - 支援製程: {process_count}
            - 製程類別: 8 大類
            - 特徵提取: OCR + 幾何 + 符號 + 視覺 + VLM
            - 決策引擎: 綜合特徵評分
            
            **技術架構:**
            - OCR: PaddleOCR (多語言支援)
            - 幾何: OpenCV Hough + Contours
            - 符號: Template Matching
            - 視覺: DINOv2 (可選)
            - VLM: Vision Language Model (實驗功能, 需 LM Studio)
            - 決策: 規則基礎 + 綜合特徵評分
            """)

# ==================== Footer ====================

st.divider()

col_footer1, col_footer2, col_footer3 = st.columns(3)

with col_footer1:
    st.caption("**提示**: 使用高解析度圖紙可提升辨識準確度")

with col_footer2:
    st.caption("**NKUST 視覺實驗室** © 2026")

with col_footer3:
    st.caption("[查看文件](MANUFACTURING_USER_GUIDE.md)")

# ==================== Tab 2: 知識庫管理 ====================

with tab2:
    st.header("知識庫維護 (修正過去的錯誤)")

    from app.knowledge.manager import KnowledgeBaseManager
    import json

    kb_manager = KnowledgeBaseManager()
    entries = kb_manager.db

    # Get process IDs - either from pipeline or directly from JSON
    pipeline = st.session_state.mfg_pipeline
    if pipeline is not None:
        all_process_ids = list(pipeline.decision_engine.processes.keys())
    else:
        # Pipeline not initialized - load directly from process_lib_v2.json
        try:
            process_lib_path = "app/manufacturing/process_lib_v2.json"
            with open(process_lib_path, 'r', encoding='utf-8') as f:
                process_data = json.load(f)
                all_process_ids = list(process_data.get('processes', {}).keys())
        except Exception as e:
            st.error(f"無法載入製程清單: {e}")
            all_process_ids = []

    if not entries:
        st.info("目前尚無知識庫條目")
    else:
        for entry in entries:
            with st.expander(f"ID: {entry['id']} - {entry['features'].get('shape_description')}"):
                col_a, col_b = st.columns(2)
                with col_a:
                    # 檢查圖片檔案是否存在
                    img_path = entry.get('image_rel_path', '')
                    if img_path and os.path.exists(img_path):
                        st.image(img_path, caption="原始圖檔")
                    else:
                        st.warning("⚠️ 原始圖檔已被刪除或移動")
                        if img_path:
                            st.caption(f"原路徑: {img_path}")
                with col_b:
                    new_processes = st.multiselect(
                        "修正製程",
                        options=all_process_ids,
                        default=entry.get('correct_processes', []),
                        key=f"edit_{entry['id']}"
                    )
                    if st.button("更新此條目", key=f"btn_{entry['id']}"):
                        kb_manager.update_entry(entry['id'], {"correct_processes": new_processes})
                        st.success("已更新！下次 RAG 會參考這個新答案。")

# ==================== Tab 3: 製程管理 ====================

with tab3:
    render_process_manager()

# ==================== Sidebar (Optional) ====================

with st.sidebar:
    render_recognition_sidebar()
    
    # 系統狀態
    with st.expander("系統狀態", expanded=False):
        pipeline_status = "已初始化" if st.session_state.mfg_pipeline else "未初始化"
        st.text(f"管線狀態: {pipeline_status}")
        
        if st.session_state.uploaded_drawing is not None:
            h, w = st.session_state.uploaded_drawing.shape[:2]
            st.text(f"圖紙: {w}×{h}")
        
        if st.session_state.recognition_result:
            st.text(f"辨識結果: {len(st.session_state.recognition_result.predictions)} 個製程")
    
    # 清除按鈕
    st.divider()
    if st.button("清除所有資料", width="stretch"):
        st.session_state.mfg_pipeline = None
        st.session_state.uploaded_drawing = None
        st.session_state.uploaded_drawings = []
        st.session_state.recognition_result = None
        st.rerun()
    
    # OCR 快取清除按鈕（調試用）
    if st.button("🔄 清除 OCR 快取", width="stretch"):
        st.cache_resource.clear()
        st.success("快取已清除，請重新載入頁面")
        st.rerun()
    
    # 關於
    st.divider()
    
    # 動態取得製程數量用於側邊欄
    sidebar_process_count = "多種"
    if st.session_state.mfg_pipeline is not None:
        try:
            sidebar_process_count = f"{st.session_state.mfg_pipeline.total_processes} 種"
        except:
            sidebar_process_count = "多種"
    
    st.markdown(f"""
    ### ℹ️ 關於系統
    
    **NKUST 製程辨識系統**專為工程圖紙分析設計，能自動識別所需的製造製程。
    
    **核心功能:**
    - 工程圖紙自動分析
    - {sidebar_process_count}製程自動辨識
    - 綜合特徵融合
    - 信心度評分與依據
    
    **Version**: 2.1.0 (Enhanced)  
    **Date**: 2026-02-03
    """)

# ==================== Main Entry Point ====================

if __name__ == "__main__":
    pass
