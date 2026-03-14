"""
NKUST 工程圖分析系統 - VLM Drawing Description Tool
工程圖紙 VLM 敘述分析核心應用
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
from typing import List
from pathlib import Path

# 工程圖分析核心模組
from app.core import AOVCoreService
from app.features import (
    run_analysis,
    build_analysis_request,
    save_rag_entry,
    list_kb_entries,
    update_kb_entry_description,
    save_symbol_templates,
    list_symbol_templates,
    delete_symbol_template,
    decode_bom_uploads,
    scan_ocr_text,
    decode_child_views,
    build_collage_or_single,
    persist_temp_preview_image,
)

# UI 樣式
from components.style import apply_custom_style

from components.sidebar import render_recognition_sidebar
from components.results_panel import (
    render_result_summary,
    render_vlm_description_section,
    render_hitl_rag_section,
    render_parent_notes_section,
    render_diagnostics_section,
)
from components.sidebar_panel import (
    render_symbol_library_block,
    render_sidebar_status_block,
    render_sidebar_clear_button,
    render_sidebar_about_block,
    render_no_result_placeholder,
)

# VLM 信心度色彩渲染器 helper
import re
# ==================== Page Config ====================

st.set_page_config(
    page_title="工程圖分析系統",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

apply_custom_style()

# ==================== Session State ====================

# 初始化分析管線 (延遲載入)
if 'mfg_pipeline' not in st.session_state:
    st.session_state.mfg_pipeline = None

if 'core_service' not in st.session_state:
    st.session_state.core_service = AOVCoreService()

if 'uploaded_drawing' not in st.session_state:
    st.session_state.uploaded_drawing = None

if 'uploaded_drawings' not in st.session_state:
    st.session_state.uploaded_drawings = []

# Session-state compatibility map (do not rename during modular slicing)
# - core_service, mfg_pipeline
# - uploaded_drawing, uploaded_drawings, uploaded_view_labels
# - parent_drawing, bom_drawings, bom_scanned_text, bom_context_input, locked_bom, _last_synced_bom
# - temp_file_path, recognition_result, hitl_corrected_text, _hitl_result_key
# - use_vlm, use_rag, min_confidence, last_settings

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

tab1, tab2 = st.tabs(["工程圖分析", "知識庫管理"])

# ==================== Tab 1: 工程圖分析 ====================

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

    _bom_imgs = decode_bom_uploads(bom_files)

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
                    _targets = st.session_state.bom_drawings if _has_bom_imgs else [st.session_state.parent_drawing]
                    _targets = [img for img in _targets if img is not None]
                    _scanned_text, _total_regions = scan_ocr_text(_targets)
                    if _scanned_text:
                        st.session_state.bom_scanned_text = _scanned_text
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
    st.caption("至少上傳一張視圖，其餘可留空。第一張有效圖將作為主辨識來源。Iso / 3D 欄位可放等角視圖或立體圖，VLM 均作為輔助參考。")

    _view_labels = ["Top（俯視圖）", "Front（前視圖）", "Side（側視圖）", "Iso / 3D（等角或立體視圖）"]
    _view_keys   = ["view_top", "view_front", "view_side", "view_iso"]
    _view_files  = []
    for _lbl, _key in zip(_view_labels, _view_keys):
        _f = st.file_uploader(_lbl, type=['jpg', 'jpeg', 'png', 'bmp'], key=_key)
        _view_files.append(_f)

    # Decode uploaded views
    drawing_images, drawing_names, _uploaded_labels = decode_child_views(_view_files, _view_labels)

    if drawing_images:
        primary_image = drawing_images[0]
        st.session_state.uploaded_drawing = primary_image
        st.session_state.uploaded_drawings = drawing_images
        st.session_state.uploaded_view_labels = _uploaded_labels

        # Save temp image for knowledge base
        # If multiple views are uploaded, stitch them into a 2x2 collage
        _save_img = build_collage_or_single(drawing_images)
        st.session_state.temp_file_path = persist_temp_preview_image(_save_img)

        # Preview uploaded views
        for idx, (_img, _name) in enumerate(zip(drawing_images, drawing_names)):
            st.image(cv2.cvtColor(_img, cv2.COLOR_BGR2RGB), caption=_name, width="stretch")
            _h, _w = _img.shape[:2]
            st.caption(f"尺寸: {_w} × {_h} px")

        st.divider()

        # ==================== 分析設定 ====================
        st.markdown("### 分析設定")

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
                    # ── 每次按辨識強制視為「全新一輪」─────────────────────────────────
                    # 1. 清除上一輪的辨識結果，避免 UI 殘留舊狀態
                    st.session_state.recognition_result = None
                    st.session_state.pop('hitl_corrected_text', None)
                    st.session_state.pop('_hitl_result_key', None)

                    parent_img = st.session_state.parent_drawing
                    if parent_img is not None:
                        st.info("雙圖模式: 正在解析父圖全域資訊...")
                    _tmp = st.session_state.get("temp_file_path")
                    _img_arg = _tmp if (_tmp and Path(_tmp).exists()) else primary_image
                    request = build_analysis_request(
                        image=_img_arg,
                        parent_image=parent_img,
                        child_images=st.session_state.uploaded_drawings,
                        view_labels=st.session_state.get('uploaded_view_labels'),
                        locked_bom=st.session_state.get('locked_bom', ''),
                        bom_context_input=st.session_state.get('bom_context_input', ''),
                        use_rag=st.session_state.use_rag,
                        use_ocr=use_ocr,
                        use_geometry=use_geometry,
                        use_symbols=use_symbols,
                        use_vlm=use_vlm,
                        min_confidence=st.session_state.min_confidence,
                    )
                    result, elapsed = run_analysis(st.session_state.core_service, request)
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
        st.info("請至少上傳一張視圖以開始工程圖分析")
        with st.expander("使用說明", expanded=True):
            st.markdown("""
            ### 系統功能
            - 自動分析工程圖紙內容
            - 幾何特徵辨識 (線條、孔洞、折彎線)
            - 符號辨識 (焊接符號、表面處理標記)
            - OCR 文字辨識 (可選)
            - VLM 多視圖敘述與信心度標記

            ### VLM 分析重點
            - 以 Top / Front 視角作為主要依據
            - Side / Iso 視角作為輔助確認
            - 可整合 BOM 與父圖全域資訊

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
        render_result_summary(result)
        
        st.divider()

        # === VLM 視覺描述 (主要輸出) + 信心度色彩渲染 ===
        vlm_desc = render_vlm_description_section(result)
        if vlm_desc is None:
            vlm_desc = ""

        st.divider()

        # === 人類專家修正區 (HITL) + 儲存至 RAG ===
        render_hitl_rag_section(result, vlm_desc, save_rag_entry)
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
        render_parent_notes_section(result)

        # 診斷資訊
        render_diagnostics_section(result)
        
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
        render_no_result_placeholder()

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
    entries = list_kb_entries()

    if not entries:
        st.info("目前尚無知識庫條目")
    else:
        for entry in entries:
            _feature_title = (
                entry.get("features", {}).get("shape_description")
                or entry.get("features", {}).get("raw_vlm_description", "")[:40]
                or "未命名條目"
            )
            with st.expander(f"ID: {entry['id']} - {_feature_title}"):
                col_a, col_b = st.columns(2)
                with col_a:
                    img_path = Path(entry['image_rel_path'])
                    if img_path.exists():
                        st.image(str(img_path), caption="原始圖檔")
                    else:
                        st.warning(f"⚠️ 原始圖檔已遺失：{img_path.name}")
                with col_b:
                    _existing_desc = (
                        entry.get("features", {}).get("raw_vlm_description", "")
                        or entry.get("reasoning", "")
                    )
                    _edited_desc = st.text_area(
                        "修正描述（VLM / RAG 參考主內容）",
                        value=_existing_desc,
                        height=180,
                        key=f"edit_desc_{entry['id']}"
                    )
                    if st.button("更新此條目", key=f"btn_{entry['id']}"):
                        update_kb_entry_description(
                            entry_id=entry["id"],
                            original_features=entry.get("features", {}),
                            edited_desc=_edited_desc or "",
                        )
                        st.success("已更新！RAG 將優先參考修正後描述。")

# ==================== Sidebar (Optional) ====================

with st.sidebar:
    render_recognition_sidebar()

    # 🏷️ 符號庫管理員
    _symbol_lib_dir = Path(__file__).parent / "data" / "symbol_library"

    render_symbol_library_block(
        symbol_lib_dir=_symbol_lib_dir,
        save_action=save_symbol_templates,
        list_action=list_symbol_templates,
        delete_action=delete_symbol_template,
    )
    render_sidebar_status_block()

    def _clear_all_data() -> None:
        st.session_state.mfg_pipeline = None
        st.session_state.uploaded_drawing = None
        st.session_state.uploaded_drawings = []
        st.session_state.recognition_result = None

    render_sidebar_clear_button(_clear_all_data)

    # 關於
    st.divider()
    render_sidebar_about_block()

# ==================== Main Entry Point ====================

if __name__ == "__main__":
    pass
