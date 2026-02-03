"""
NKUST 製程辨識系統 - Manufacturing Process Recognition Tool
工程圖紙製程辨識核心應用

重構版本：以製程辨識為核心，移除所有影像辨識演算法相關功能
"""

import streamlit as st
import cv2
import numpy as np
import time
from PIL import Image

# 製程辨識核心模組
from app.manufacturing import ManufacturingPipeline

# UI 樣式
from components.style import apply_custom_style

# ==================== Page Config ====================

st.set_page_config(
    page_title="NKUST 製程辨識系統",
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

# 新增父圖支援
if 'parent_drawing' not in st.session_state:
    st.session_state.parent_drawing = None
    
if 'recognition_result' not in st.session_state:
    st.session_state.recognition_result = None

# 儲存上次的設定 (用於特徵視覺化)
if 'last_settings' not in st.session_state:
    st.session_state.last_settings = {
        'use_ocr': False,
        'use_geometry': True,
        'use_symbols': True,
        'show_visualization': False
    }

# ==================== Header ====================

st.markdown("""
<div style='text-align: center; padding: 2rem 0;'>
    <h1 style='color: #1f77b4; font-size: 3rem; margin-bottom: 0.5rem;'>
        🏭 NKUST 製程辨識系統
    </h1>
    <p style='font-size: 1.2rem; color: #666; margin-top: 0;'>
        Manufacturing Process Recognition from Engineering Drawings
    </p>
    <p style='font-size: 1rem; color: #888;'>
        國立高雄科技大學 視覺實驗室 | FPGA-aware CV Pipeline Generator
    </p>
</div>
""", unsafe_allow_html=True)

st.divider()

# ==================== Main Layout ====================

col_left, col_right = st.columns([1, 1.5], gap="large")

# ==================== Left Column: Upload & Settings ====================

with col_left:
    st.markdown("### 📤 上傳工程圖紙")
    
    st.info("💡 **雙圖辨識模式**: 父圖提供全域資訊（材質、客戶、特殊要求），子圖提供局部特徵（形狀、標註、符號）")
    
    # 父圖上傳（選填）
    with st.expander("🗂️ 父圖（選填）- 全視圖/標題欄/備註", expanded=False):
        parent_file = st.file_uploader(
            "上傳父圖（可選）",
            type=['jpg', 'jpeg', 'png', 'bmp'],
            help="父圖包含：標題欄、技術要求、材質說明、客戶資訊等全域文字",
            key="parent_uploader"
        )
        
        if parent_file is not None:
            parent_bytes = np.asarray(bytearray(parent_file.read()), dtype=np.uint8)
            parent_image = cv2.imdecode(parent_bytes, cv2.IMREAD_COLOR)
            
            if parent_image is not None:
                st.session_state.parent_drawing = parent_image
                st.image(
                    cv2.cvtColor(parent_image, cv2.COLOR_BGR2RGB),
                    caption=f"父圖: {parent_file.name}",
                    use_container_width=True
                )
                h, w = parent_image.shape[:2]
                st.caption(f"✅ 已載入父圖 | 尺寸: {w} × {h} px")
            else:
                st.error("無法讀取父圖")
        else:
            st.session_state.parent_drawing = None
            st.caption("⚪ 未上傳父圖（將僅依子圖特徵判定）")
    
    # 子圖上傳（必填）
    st.markdown("#### 📋 子圖（必填）- 零件局部特徵")
    uploaded_file = st.file_uploader(
        "選擇子圖檔案 *",
        type=['jpg', 'jpeg', 'png', 'bmp'],
        help="子圖為必要上傳，包含零件局部特徵、標註數字、符號等",
        key="drawing_uploader"
    )
    
    if uploaded_file is not None:
        # 讀取圖片
        file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
        drawing_image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        
        if drawing_image is not None:
            st.session_state.uploaded_drawing = drawing_image
            
            # 顯示圖紙預覽
            st.image(
                cv2.cvtColor(drawing_image, cv2.COLOR_BGR2RGB),
                caption=f"圖紙: {uploaded_file.name}",
                use_container_width=True
            )
            
            # 圖紙資訊
            h, w = drawing_image.shape[:2]
            st.caption(f"尺寸: {w} × {h} px | 檔案大小: {uploaded_file.size / 1024:.1f} KB")
            
            st.divider()
            
            # ==================== 辨識設定 ====================
            st.markdown("### ⚙️ 辨識設定")
            
            with st.expander("特徵提取選項", expanded=True):
                use_ocr = st.checkbox(
                    "📝 OCR 文字辨識",
                    value=False,
                    help="需要安裝 PaddlePaddle (可選功能)"
                )
                
                use_geometry = st.checkbox(
                    "📐 幾何特徵分析",
                    value=True,
                    help="分析線條、孔洞、折彎線等幾何特徵 (建議啟用)"
                )
                
                use_symbols = st.checkbox(
                    "🔣 符號辨識",
                    value=True,
                    help="辨識焊接符號、表面處理標記等"
                )
            
            with st.expander("進階選項", expanded=False):
                top_n = st.slider(
                    "顯示前 N 個預測結果",
                    min_value=3,
                    max_value=15,
                    value=8,
                    step=1
                )
                
                min_confidence = st.slider(
                    "最低信心度門檻",
                    min_value=0.1,
                    max_value=0.9,
                    value=0.25,
                    step=0.05,
                    help="低於此門檻的預測結果將被過濾"
                )
                
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
                    'show_visualization': show_visualization
                }
            
            st.divider()
            
            # ==================== 執行辨識 ====================
            if st.button("🚀 開始辨識製程", type="primary", use_container_width=True):
                with st.spinner("正在分析工程圖紙..."):
                    try:
                        # 初始化管線
                        if st.session_state.mfg_pipeline is None:
                            st.session_state.mfg_pipeline = ManufacturingPipeline(
                                use_ocr=use_ocr,
                                use_geometry=use_geometry,
                                use_symbols=use_symbols,
                                use_visual=False  # DINOv2 可選 (耗時)
                            )
                        
                        # 執行辨識（支援雙圖模式）
                        start_time = time.time()
                        
                        # 檢查是否有父圖
                        parent_img = st.session_state.parent_drawing
                        if parent_img is not None:
                            st.info("📊 雙圖模式: 正在解析父圖全域資訊...")
                        
                        result = st.session_state.mfg_pipeline.recognize(
                            drawing_image,
                            parent_image=parent_img,  # 傳遞父圖
                            top_n=top_n,
                            min_confidence=min_confidence,
                            frequency_filter=freq_options if freq_options else None
                        )
                        elapsed = time.time() - start_time
                        
                        st.session_state.recognition_result = result
                        
                        if parent_img is not None:
                            st.success(f"✅ 雙圖辨識完成！處理時間: {elapsed:.2f} 秒")
                        else:
                            st.success(f"✅ 辨識完成！處理時間: {elapsed:.2f} 秒")
                        st.rerun()
                        
                    except ImportError as e:
                        st.error(f"❌ 模組載入失敗: {str(e)}")
                        st.info("請確認已安裝相關依賴套件 (參考 requirements.txt)")
                    except Exception as e:
                        st.error(f"❌ 辨識過程發生錯誤: {str(e)}")
                        with st.expander("查看錯誤詳情"):
                            import traceback
                            st.code(traceback.format_exc())
        else:
            st.error("無法讀取圖片，請確認檔案格式正確")
    else:
        # 無圖紙時顯示說明
        st.info("👆 請上傳工程圖紙以開始製程辨識")
        
        with st.expander("ℹ️ 使用說明", expanded=True):
            st.markdown("""
            ### 📋 系統功能
            - 🔍 自動分析工程圖紙內容
            - 📐 幾何特徵辨識 (線條、孔洞、折彎線)
            - 🔣 符號辨識 (焊接符號、表面處理標記)
            - 📝 OCR 文字辨識 (可選)
            - 🎯 製程推薦 (96 種製程類型)
            
            ### 🏭 支援製程類別
            - **切割**: 雷射切割、水刀切割、剪板機等
            - **折彎**: 折彎、滾圓、滾弧等
            - **焊接**: 點焊、氬焊、電焊、CO2焊接等
            - **表面處理**: 噴砂、烤漆、鍍鋅、陽極處理等
            - **組裝**: 自攻牙、螺絲、鉚接、拉釘等
            - **檢驗**: 成品全檢、尺寸檢驗、外觀檢驗等
            
            ### ✨ 建議圖紙品質
            - **解析度**: 300 DPI 以上
            - **格式**: JPG, PNG, BMP
            - **類型**: 工程圖 (白底黑線)
            - **內容**: 包含完整標註與符號
            """)

# ==================== Right Column: Results ====================

with col_right:
    st.markdown("### 📊 辨識結果")
    
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
        
        # 顯示預測結果
        if result.predictions:
            st.markdown("#### 🎯 製程預測結果")
            
            for i, pred in enumerate(result.predictions, 1):
                confidence_pct = pred.confidence * 100
                
                # 信心度顏色標記
                if confidence_pct >= 70:
                    color_emoji = "🟢"
                    color_tag = "高信心度"
                elif confidence_pct >= 50:
                    color_emoji = "🟡"
                    color_tag = "中等信心度"
                else:
                    color_emoji = "🔴"
                    color_tag = "低信心度"
                
                with st.expander(
                    f"{color_emoji} **{i}. {pred.name}** ({confidence_pct:.1f}%) - {color_tag}",
                    expanded=(i <= 3)  # 展開前3個結果
                ):
                    # 信心度進度條
                    st.progress(pred.confidence)
                    
                    # 辨識依據
                    if pred.reasoning:
                        st.markdown("**辨識依據:**")
                        for evidence_item in pred.reasoning.split("\n"):
                            if evidence_item.strip():
                                st.markdown(f"- {evidence_item}")
                    else:
                        st.caption("(基於視覺相似度推測)")
                    
                    # 製程資訊 (如果有的話)
                    st.caption(f"製程 ID: {pred.process_id}")
        else:
            st.warning("⚠️ 未找到符合條件的製程")
            st.info("建議:\n- 降低信心度門檻\n- 啟用更多特徵提取選項\n- 檢查圖紙品質與解析度")
        
        st.divider()
        
        # 診斷資訊
        with st.expander("🔍 診斷資訊 (Diagnostics)", expanded=False):
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
        
        # 特徵視覺化
        if (st.session_state.last_settings.get('show_visualization', False) 
            and st.session_state.uploaded_drawing is not None
            and st.session_state.mfg_pipeline is not None):
            st.divider()
            st.markdown("#### 🎨 特徵視覺化")
            
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
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"視覺化失敗: {str(e)}")
    
    else:
        # 無結果時顯示佔位內容
        st.info("📋 上傳工程圖紙並執行辨識後，結果將顯示在此處")
        
        # 顯示系統資訊
        with st.expander("📈 系統資訊", expanded=False):
            st.markdown("""
            **製程辨識系統 v2.0**
            
            - 支援製程: 96 種
            - 製程類別: 8 大類
            - 特徵提取: OCR + 幾何 + 符號 + 視覺
            - 決策引擎: 多模態融合評分
            
            **技術架構:**
            - OCR: PaddleOCR (中英文)
            - 幾何: OpenCV Hough + Contours
            - 符號: Template Matching
            - 視覺: DINOv2 (可選)
            - 決策: 規則基礎 + 加權融合
            """)

# ==================== Footer ====================

st.divider()

col_footer1, col_footer2, col_footer3 = st.columns(3)

with col_footer1:
    st.caption("💡 **提示**: 使用高解析度圖紙可提升辨識準確度")

with col_footer2:
    st.caption("🏫 **NKUST 視覺實驗室** © 2026")

with col_footer3:
    st.caption("📚 [查看文件](MANUFACTURING_USER_GUIDE.md)")

# ==================== Sidebar (Optional) ====================

with st.sidebar:
    st.markdown("### 🛠 系統設定")
    
    # 系統狀態
    with st.expander("系統狀態", expanded=False):
        pipeline_status = "✅ 已初始化" if st.session_state.mfg_pipeline else "⏳ 未初始化"
        st.text(f"管線狀態: {pipeline_status}")
        
        if st.session_state.uploaded_drawing is not None:
            h, w = st.session_state.uploaded_drawing.shape[:2]
            st.text(f"圖紙: {w}×{h}")
        
        if st.session_state.recognition_result:
            st.text(f"辨識結果: {len(st.session_state.recognition_result.predictions)} 個製程")
    
    # 清除按鈕
    st.divider()
    if st.button("🗑️ 清除所有資料", use_container_width=True):
        st.session_state.mfg_pipeline = None
        st.session_state.uploaded_drawing = None
        st.session_state.recognition_result = None
        st.rerun()
    
    # 關於
    st.divider()
    st.markdown("""
    ### ℹ️ 關於系統
    
    **NKUST 製程辨識系統**專為工程圖紙分析設計，能自動識別所需的製造製程。
    
    **核心功能:**
    - 工程圖紙自動分析
    - 96 種製程自動辨識
    - 多模態特徵融合
    - 信心度評分與依據
    
    **Version**: 2.0.0 (Refactored)  
    **Date**: 2026-02-03
    """)

# ==================== Main Entry Point ====================

if __name__ == "__main__":
    pass
