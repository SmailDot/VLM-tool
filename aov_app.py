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
from pathlib import Path
from PIL import Image

# 製程辨識核心模組
from app.manufacturing import ManufacturingPipeline

# UI 樣式
from components.style import apply_custom_style

# 製程管理界面
from components.process_manager import render_process_manager
from components.sidebar import render_recognition_sidebar

# VLM 信心度色彩渲染器 helper
import re


def format_streamlit_colors(text: str) -> str:
    """
    將 VLM 輸出的 <green>/<orange>/<red> XML 標籤
    轉換為 Streamlit 原生顏色語法（加粗體），不需要 unsafe_allow_html。

    Args:
        text: VLM 原始輸出字串（含 XML 信心度標籤）。

    Returns:
        str: 替換後的 Streamlit markdown 字串。
    """
    if not text:
        return ""
    # 將 XML 標籤轉換為 Streamlit 原生顏色語法 (加粗體)
    text = re.sub(r'<green>(.*?)</green>', r':green[**\1**]', text)
    text = re.sub(r'<orange>(.*?)</orange>', r':orange[**\1**]', text)
    text = re.sub(r'<red>(.*?)</red>', r':red[**\1**]', text)
    return text


# 相容性別名，保留舊呼叫點可繼續使用
_render_vlm_with_confidence = format_streamlit_colors


def _strip_confidence_tags(raw_text: str) -> str:
    """去除所有信心度 XML 標籤，返回純文字。"""
    return re.sub(r"</?(?:green|orange|red)>", "", raw_text)
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

    # ==================== BOM Context ====================
    st.markdown("#### 📝 BOM 表圖片 + 內容備註 (可選)")

    # BOM 表圖片上傳（支援多張）
    bom_files = st.file_uploader(
        "上傳 BOM 表圖片 (可上傳多張)",
        type=['jpg', 'jpeg', 'png', 'bmp'],
        accept_multiple_files=True,
        help="BOM 表圖片，支援多張。上傳後可點擊「掃描內容」自動填入文字框",
        key="bom_uploader"
    )

    if 'bom_drawings' not in st.session_state:
        st.session_state.bom_drawings = []

    _bom_imgs: List[np.ndarray] = []
    for _bf in (bom_files or []):
        _bb = np.asarray(bytearray(_bf.read()), dtype=np.uint8)
        _bi = cv2.imdecode(_bb, cv2.IMREAD_COLOR)
        if _bi is not None:
            _bom_imgs.append(_bi)

    st.session_state.bom_drawings = _bom_imgs

    if _bom_imgs:
        for _i, (_bi, _bf) in enumerate(zip(_bom_imgs, bom_files)):
            st.image(cv2.cvtColor(_bi, cv2.COLOR_BGR2RGB), caption=f"BOM 表 {_i+1}: {_bf.name}", width="stretch")

    # 「掃描內容」按鈕：優先掃描 BOM 圖片（全部頁合併），否則 fallback 父圖
    _has_bom_imgs = len(st.session_state.bom_drawings) > 0
    _has_parent   = st.session_state.parent_drawing is not None

    if _has_bom_imgs or _has_parent:
        _btn_label = f"🔍 掃描 BOM 表內容 ({len(st.session_state.bom_drawings)}張)" if _has_bom_imgs else "🔍 掃描父圖內容"
        if st.button(
            _btn_label,
            help="OCR 掃描圖片，將辨識到的文字填入下方文字框",
            type="secondary",
            use_container_width=True
        ):
            with st.spinner("正在掃描..."):
                try:
                    from app.manufacturing.extractors.ocr import OCRExtractor
                    _ocr = OCRExtractor()
                    _targets = st.session_state.bom_drawings if _has_bom_imgs else [st.session_state.parent_drawing]
                    _all_texts: List[str] = []
                    _total_regions = 0
                    for _page_idx, _target_img in enumerate(_targets):
                        _page_results = _ocr.extract(_target_img)
                        if _page_results:
                            _total_regions += len(_page_results)
                            if len(_targets) > 1:
                                _all_texts.append(f"--- 第 {_page_idx+1} 頁 ---")
                            _all_texts.extend([r.text for r in _page_results if r.text.strip()])
                    if _all_texts:
                        st.session_state.bom_scanned_text = "\n".join(_all_texts)
                        st.success(f"✅ 掃描完成，共辨識到 {_total_regions} 個文字區域")
                    else:
                        st.warning("⚠️ 未掃描到任何文字，請確認圖片品質")
                        st.session_state.bom_scanned_text = ""
                except Exception as _ocr_err:
                    st.error(f"掃描失敗：{str(_ocr_err)}")
                    st.info("提示：OCR 功能需要安裝 PaddlePaddle。您仍可手動輸入 BOM 內容。")
                    st.session_state.bom_scanned_text = ""
            st.rerun()
    else:
        st.caption("💡 上傳 BOM 表圖片或父圖後，可使用「掃描內容」自動填入文字")

    if 'bom_context_input' not in st.session_state:
        st.session_state.bom_context_input = ""
    if 'bom_scanned_text' not in st.session_state:
        st.session_state.bom_scanned_text = ""
    # 掃描完成後同步到 text_area key（讓使用者可繼續手動修改）
    if st.session_state.bom_scanned_text and st.session_state.bom_scanned_text != st.session_state.get('_last_synced_bom', ''):
        st.session_state.bom_context_input = st.session_state.bom_scanned_text
        st.session_state['_last_synced_bom'] = st.session_state.bom_scanned_text

    st.text_area(
        "輸入 BOM 內容或全域技術備註",
        height=120,
        placeholder="例如：材質 SUS304、表面陽極處理、批量 500 pcs...",
        help="此文字將注入 VLM 提示詞作為全域背景資訊（權重最高，VLM 必須遵守）",
        key="bom_context_input"
    )
    if st.button('🔒 確認並鎖定此 BOM 資訊作為已知事實', type='secondary', use_container_width=True):
        st.session_state.locked_bom = st.session_state.get('bom_context_input', '')
        st.success('✅ BOM 資訊已成功鎖定！這將成為 AI 看圖時的鐵證。')
    if st.session_state.get('locked_bom'):
        st.info(f"🔒 已鎖定 BOM：{st.session_state.locked_bom[:80]}{'...' if len(st.session_state.locked_bom) > 80 else ''}")

    # ==================== 四視圖上傳 ====================
    st.markdown("#### 📐 上傳零件四視圖 (Child Drawing)")
    st.caption("至少上傳一張視圖，其餘可留空。第一張有效圖將作為主辨識來源。")

    _view_labels = ["Top（俯視圖）", "Front（前視圖）", "Side（側視圖）", "Iso（等角視圖）"]
    _view_keys   = ["view_top", "view_front", "view_side", "view_iso"]
    _view_files  = []
    for _lbl, _key in zip(_view_labels, _view_keys):
        _f = st.file_uploader(_lbl, type=['jpg', 'jpeg', 'png', 'bmp'], key=_key)
        _view_files.append(_f)

    # Decode uploaded views
    drawing_images: List[np.ndarray] = []
    drawing_names: List[str] = []
    for _uf, _lbl in zip(_view_files, _view_labels):
        if _uf is not None:
            _fb = np.asarray(bytearray(_uf.read()), dtype=np.uint8)
            _img = cv2.imdecode(_fb, cv2.IMREAD_COLOR)
            if _img is not None:
                drawing_images.append(_img)
                drawing_names.append(f"{_lbl}: {_uf.name}")

    if drawing_images:
        primary_image = drawing_images[0]
        st.session_state.uploaded_drawing = primary_image
        st.session_state.uploaded_drawings = drawing_images

        # Save temp image for knowledge base
        # If multiple views are uploaded, stitch them into a 2x2 collage
        _views = drawing_images
        if len(_views) > 1:
            _max_h = max(v.shape[0] for v in _views)
            _max_w = max(v.shape[1] for v in _views)
            # Pad each view to uniform size
            def _pad_view(v):
                _canvas = np.zeros((_max_h, _max_w, 3), dtype=np.uint8)
                _canvas[:v.shape[0], :v.shape[1]] = v[:, :, :3] if v.shape[2] == 3 else cv2.cvtColor(v, cv2.COLOR_BGRA2BGR)
                return _canvas
            _padded = [_pad_view(v) for v in _views[:4]]
            while len(_padded) < 4:
                _padded.append(np.zeros((_max_h, _max_w, 3), dtype=np.uint8))
            _row1 = np.hstack(_padded[:2])
            _row2 = np.hstack(_padded[2:4])
            _collage = np.vstack([_row1, _row2])
            _save_img = _collage
        else:
            _save_img = drawing_images[0]
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_image:
            cv2.imwrite(tmp_image.name, _save_img)
            st.session_state.temp_file_path = tmp_image.name

        # Preview uploaded views
        for idx, (_img, _name) in enumerate(zip(drawing_images, drawing_names)):
            st.image(cv2.cvtColor(_img, cv2.COLOR_BGR2RGB), caption=_name, width="stretch")
            _h, _w = _img.shape[:2]
            st.caption(f"尺寸: {_w} × {_h} px")

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
            if use_vlm:
                from app.manufacturing.extractors.vlm_client import VLMClient
                try:
                    _vlm_test = VLMClient()
                    if _vlm_test.is_available():
                        st.success("✅ VLM 服務已連接 (LM Studio)")
                    else:
                        st.warning("⚠️ VLM 服務未運行 - 請確認 LM Studio 已啟動 (http://localhost:1234)")
                except Exception as _ve:
                    st.error(f"❌ VLM 初始化失敗: {str(_ve)}")

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
            st.session_state.last_settings = {
                'use_ocr': use_ocr,
                'use_geometry': use_geometry,
                'use_symbols': use_symbols,
                'use_vlm': use_vlm,
                'show_visualization': show_visualization
            }

        st.divider()

        # ==================== 執行辨識 ====================
        if st.button("▶️ 確認無誤，開始 VLM 視覺重建", type="primary", use_container_width=True):
            with st.spinner("正在分析工程圖紙..."):
                try:
                    if st.session_state.mfg_pipeline is None:
                        st.session_state.mfg_pipeline = ManufacturingPipeline(
                            use_ocr=use_ocr,
                            use_geometry=use_geometry,
                            use_symbols=use_symbols,
                            use_visual=False,
                            use_vlm=use_vlm
                        )
                    start_time = time.time()
                    parent_img = st.session_state.parent_drawing
                    if parent_img is not None:
                        st.info("雙圖模式: 正在解析父圖全域資訊...")
                    _tmp = st.session_state.get("temp_file_path")
                    _img_arg = _tmp if (_tmp and Path(_tmp).exists()) else primary_image
                    result = st.session_state.mfg_pipeline.recognize(
                        _img_arg,
                        parent_image=parent_img,
                        top_n=None,
                        min_confidence=st.session_state.min_confidence,
                        frequency_filter=freq_options if freq_options else None,
                        use_rag=st.session_state.use_rag,
                        child_images=st.session_state.uploaded_drawings,
                        bom_context=st.session_state.get('locked_bom') or st.session_state.get('bom_context_input', '')
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
        st.info("請至少上傳一張視圖以開始製程辨識")
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

        # === VLM 視覺描述 (主要輸出) + 信心度色彩渲染 ===
        vlm_desc = result.features.raw_vlm_description
        if vlm_desc:
            st.markdown("### \U0001f916 VLM 視覺重建結果")

            # 色彩圖例 + 警示說明
            st.caption(
                "\U0001f7e2 高信心（AI 確認可見）\u3000"
                "\U0001f7e0 中信心（AI 存疑，建議確認）\u3000"
                "\U0001f534 低信心（AI 沒把握，**請人工核對**）"
            )

            # 若有 <red> 項目，主動顯示警示橫幅
            import re as _re
            _red_items = _re.findall(r'<red>(.*?)</red>', vlm_desc)
            if _red_items:
                st.warning(
                    "⚠️ **AI 不確定以下項目，請人類專家務必核對：** "
                    + "、".join(f'**{x}**' for x in _red_items)
                )

            # 使用 Streamlit 原生顏色語法渲染（不需要 unsafe_allow_html）
            colored_report = format_streamlit_colors(vlm_desc)
            st.markdown("### \u00a0VLM 視覺描述預覽")
            st.markdown(colored_report)
        else:
            st.info("⚠️ VLM 未返回效描述。請確認：① LM Studio 已啟動 ② 左侧「辨識設定」已勾選 VLM")

        st.divider()

        # === 人類專家修正區 (HITL) + 儲存至 RAG ===
        st.markdown("### ✏️ 人類專家修正區")

        # 當辨識完成新結果時，自動將原始 VLM 描述（已去標籤）填入修正區
        _vlm_key = id(result)
        if st.session_state.get('_hitl_result_key') != _vlm_key:
            st.session_state['hitl_corrected_text'] = _strip_confidence_tags(vlm_desc or "")
            st.session_state['_hitl_result_key'] = _vlm_key

        corrected_text = st.text_area(
            "✏️ 人類專家修正區 (請修正 AI 的錯誤描述)",
            height=200,
            placeholder="AI 的描述將自動填入此處，您可直接修改...",
            key="hitl_corrected_text",
            help="此處顯示的文字將在按下「儲存至 RAG 知識庫」時一併寫入。"
        )

        # 儲存按鈕
        if st.button("💾 儲存至 RAG 知識庫", type="primary", key="btn_save_rag"):
            tmp_path = st.session_state.get("temp_file_path")
            if not tmp_path or not Path(tmp_path).exists():
                st.error("⚠️ 暫存圖檔已遺失，無法加入知識庫，請重新上傳圖紙。")
            else:
                from app.knowledge.manager import KnowledgeBaseManager as _KBMgr
                _kb = _KBMgr()
                _final_desc = st.session_state.get("hitl_corrected_text", "").strip()
                _kb.add_entry(
                    image_path=tmp_path,
                    features={
                        "raw_vlm_description": _final_desc,
                    },
                    correct_processes=[],
                    reasoning=_final_desc,
                    bom_context=st.session_state.get("bom_context_text", "")
                )
                st.toast("✅ 敘述已成功寫入 RAG 知識庫＆零件圖庫已更新！", icon="✅")
        if st.session_state.use_rag and result.rag_references:
            # Hash 完全匹配提示
            _exact = next((r for r in result.rag_references if r.get("_match_type") == "exact_hash"), None)
            if _exact:
                st.success("🎯 發現 100% 匹配的歷史圖面！已自動載入過往校正資訊。")
            with st.expander("本次推論參考的歷史案例 (RAG Context)"):
                for ref in result.rag_references:
                    _features = ref.get('features', {})
                    _desc = _features.get('raw_vlm_description') or _features.get('shape_description', '')
                    st.info(
                        f"參考案例：{_desc[:120]}...…\n"
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
            
            # VLM 純文字描述 (raw_vlm_description)
            if result.features.raw_vlm_description:
                st.markdown("**🤖 VLM 視覺語言模型分析 (純文字描述):**")
                st.markdown(result.features.raw_vlm_description)
            elif result.features.vlm_analysis:
                st.markdown("**🤖 VLM 分析 (文字):**")
                st.text(str(result.features.vlm_analysis))
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
        try:
            import json as _json
            with open('app/manufacturing/process_lib_v2.json', encoding='utf-8') as _f:
                _data = _json.load(_f)
                all_process_ids = list(_data.get('processes', {}).keys())
        except Exception:
            all_process_ids = []

    if not entries:
        st.info("目前尚無知識庫條目")
    else:
        for entry in entries:
            with st.expander(f"ID: {entry['id']} - {entry['features'].get('shape_description')}"):
                col_a, col_b = st.columns(2)
                with col_a:
                    img_path = Path(entry['image_rel_path'])
                    if img_path.exists():
                        st.image(str(img_path), caption="原始圖檔")
                    else:
                        st.warning(f"⚠️ 原始圖檔已遺失：{img_path.name}")
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
