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
from app.manufacturing.decision import InstructionParser

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
    st.session_state.mfg_pipeline = None

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
if 'teacher_actions' not in st.session_state:
    st.session_state.teacher_actions = []
if 'teacher_rag_knowledge' not in st.session_state:
    st.session_state.teacher_rag_knowledge = ""
if 'teacher_response' not in st.session_state:
    st.session_state.teacher_response = ""
if 'teacher_pending' not in st.session_state:
    st.session_state.teacher_pending = False
if 'teacher_last_input' not in st.session_state:
    st.session_state.teacher_last_input = ""
if 'last_kb_entry_id' not in st.session_state:
    st.session_state.last_kb_entry_id = ""

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

    # 子圖上傳（必填）
    st.markdown("#### 📄 上傳零件圖 (Child Drawing)")
    uploaded_files = st.file_uploader(
        "選擇子圖檔案 *",
        type=['jpg', 'jpeg', 'png', 'bmp', 'pdf'],
        help=(
            "子圖為必要上傳，包含零件局部特徵、標註數字、符號等。"
            "支援 PDF 格式（將以 300 DPI 高解析度渲染），可多選上傳。"
        ),
        key="drawing_uploader",
        accept_multiple_files=True
    )
    
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

            # Save temp image for knowledge base
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_image:
                cv2.imwrite(tmp_image.name, primary_image)
                st.session_state.temp_file_path = tmp_image.name
            
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
            if st.button("開始辨識製程", type="primary", width="stretch"):
                with st.spinner("正在分析工程圖紙..."):
                    try:
                        # 初始化管線
                        if st.session_state.mfg_pipeline is None:
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

        for idx, item in enumerate(st.session_state.editing_predictions):
            with st.container(border=True):
                col_title, col_conf, col_action = st.columns([4, 3, 1])

                with col_title:
                    st.markdown(
                        f"**{item['process_id']} - {item['process_name']}**"
                    )

                with col_conf:
                    st.progress(item["confidence"])
                    st.caption(f"信心度: {item['confidence'] * 100:.1f}%")

                with col_action:
                    if st.button("🗑️ 刪除", key=f"del_{idx}"):
                        st.session_state.editing_predictions.pop(idx)
                        st.rerun()

                st.markdown(f"**理由**: {item['reasoning']}")

        st.markdown("#### 專家指令區 (Teacher Mode)")
        teacher_input = st.chat_input("若有錯誤，請在這描述你想要的修改（例如：'移除 I01，新增 K01，理由是...')")
        if teacher_input and not st.session_state.teacher_pending:
            st.session_state.teacher_last_input = teacher_input
            st.session_state.teacher_pending = True
            st.rerun()

        if st.session_state.teacher_pending:
            with st.spinner("🧠 系統思考中，請稍候..."):
                parser = InstructionParser()
                parsed = parser.parse(
                    st.session_state.teacher_last_input,
                    context={"predictions": st.session_state.editing_predictions}
                )
                if parsed is None:
                    st.warning("⚠️ LLM 未啟動或解析失敗，已跳過指令處理")
                    st.session_state.teacher_pending = False
                else:
                    actions = parsed.get("actions", [])
                    rag_knowledge = parsed.get("rag_knowledge", "")
                    st.session_state.teacher_actions = actions
                    st.session_state.teacher_rag_knowledge = rag_knowledge

                    response_parts = []
                    for action in actions:
                        action_type = action.get("type")
                        target_id = action.get("target_id")
                        if action_type == "remove" and target_id:
                            st.session_state.editing_predictions = [
                                item for item in st.session_state.editing_predictions
                                if item.get("process_id") != target_id
                            ]
                            response_parts.append(f"已移除 {target_id}")
                        elif action_type == "add" and target_id:
                            new_name = process_defs.get(target_id, {}).get("name", "")
                            st.session_state.editing_predictions.append({
                                "process_id": target_id,
                                "process_name": new_name,
                                "confidence": 0.5,
                                "reasoning": action.get("reason", "")
                            })
                            response_parts.append(f"已新增 {target_id}")

                    if response_parts:
                        st.session_state.teacher_response = "收到，" + " 並 ".join(response_parts) + "。"
                    else:
                        st.session_state.teacher_response = "收到，我已記錄你的指令。"
                    st.session_state.teacher_pending = False
                    st.rerun()

        if st.session_state.teacher_response:
            st.info(st.session_state.teacher_response)

        st.markdown("#### 定案並學習 (Save & Learn)")
        col_learn, col_undo = st.columns([3, 1])
        with col_learn:
            learn_clicked = st.button("✅ 定案並學習", width="stretch")
        with col_undo:
            undo_clicked = st.button("↩️ 撤回", width="stretch")

        if learn_clicked:
            if not st.session_state.temp_file_path:
                st.error("找不到暫存圖片，請重新上傳圖檔")
            else:
                from app.knowledge.manager import KnowledgeBaseManager

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

                rag_knowledge = st.session_state.teacher_rag_knowledge
                if rag_knowledge:
                    reasoning_lines.append(f"RAG: {rag_knowledge}")

                kb_manager = KnowledgeBaseManager()
                entry = kb_manager.add_entry(
                    image_path=st.session_state.temp_file_path,
                    features=result.features.vlm_analysis or {},
                    correct_processes=final_processes,
                    reasoning="\n".join(reasoning_lines)
                )
                st.session_state.last_kb_entry_id = entry.get("id", "")
                st.toast("已保存並學習")

        if undo_clicked:
            last_entry_id = st.session_state.last_kb_entry_id
            if not last_entry_id:
                st.warning("沒有可撤回的條目")
            else:
                from app.knowledge.manager import KnowledgeBaseManager
                kb_manager = KnowledgeBaseManager()
                if kb_manager.delete_entry(last_entry_id):
                    st.session_state.last_kb_entry_id = ""
                    st.toast("已撤回最近一次學習")
                else:
                    st.warning("撤回失敗，請到知識庫管理確認")

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

    kb_manager = KnowledgeBaseManager()
    entries = kb_manager.db

    pipeline = st.session_state.mfg_pipeline
    if pipeline is not None:
        all_process_ids = list(pipeline.decision_engine.processes.keys())
    else:
        all_process_ids = []

    if not entries:
        st.info("目前尚無知識庫條目")
    else:
        for entry in entries:
            with st.expander(f"ID: {entry['id']} - {entry['features'].get('shape_description')}"):
                col_a, col_b = st.columns(2)
                with col_a:
                    st.image(entry['image_rel_path'], caption="原始圖檔")
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
