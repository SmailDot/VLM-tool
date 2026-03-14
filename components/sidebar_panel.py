"""Sidebar panel helpers for cleaner app composition."""

from pathlib import Path
from typing import Callable

import streamlit as st


def render_sidebar_status_block() -> None:
    """Render runtime status summary block."""
    with st.expander("系統狀態", expanded=False):
        pipeline_status = "已初始化" if st.session_state.mfg_pipeline else "未初始化"
        st.text(f"管線狀態: {pipeline_status}")

        if st.session_state.uploaded_drawing is not None:
            h, w = st.session_state.uploaded_drawing.shape[:2]
            st.text(f"圖紙: {w}×{h}")

        if st.session_state.recognition_result:
            desc_exists = bool(st.session_state.recognition_result.features.raw_vlm_description)
            st.text(f"VLM 描述: {'已產生' if desc_exists else '尚未產生'}")


def render_sidebar_about_block() -> None:
    """Render static sidebar about section."""
    st.markdown(
        """
    ### ℹ️ 關於系統

    **NKUST 工程圖分析系統**專為工程圖紙分析設計，以 VLM 視覺語言模型產出結構化描述。

    **核心功能:**
    - 工程圖紙自動分析
    - VLM 多視圖描述 + 信心度標記
    - BOM / 父圖全域資訊注入
    - 人工修正與 RAG 知識庫持續增強

    **Version**: 2.1.0 (Enhanced)
    **Date**: 2026-02-03
    """
    )


def render_sidebar_clear_button(clear_action: Callable[[], None]) -> None:
    """Render clear-all button and trigger callback when clicked."""
    st.divider()
    if st.button("清除所有資料", width="stretch"):
        clear_action()
        st.rerun()


def render_no_result_placeholder() -> None:
    """Render no-result placeholder and lightweight system info."""
    st.info("上傳工程圖紙並執行辨識後，結果將顯示在此處")

    with st.expander("📈 系統資訊", expanded=False):
        st.markdown(
            """
            **工程圖分析系統 v2.1**

            - 分析主軸: VLM 工程圖敘述
            - 輔助能力: OCR + 幾何 + 符號
            - 知識增強: Multi-Model RAG

            **技術架構:**
            - OCR: PaddleOCR (多語言支援)
            - 幾何: OpenCV Hough + Contours
            - 符號: Template Matching
            - VLM: Vision Language Model (需 LM Studio)
            """
        )


def render_symbol_library_block(
    symbol_lib_dir: Path,
    save_action,
    list_action,
    delete_action,
) -> None:
    """Render symbol library uploader/list manager block."""
    symbol_lib_dir.mkdir(parents=True, exist_ok=True)
    with st.expander("🏷️ 符號庫管理員", expanded=False):
        st.caption("上傳去背 PNG 作為符號模板，系統將在辨識時掃描圖紙。")
        uploaded_sym = st.file_uploader(
            "上傳符號模板 (去背 PNG)",
            type=["png"],
            accept_multiple_files=True,
            key="symbol_lib_uploader",
        )
        if uploaded_sym:
            saved = save_action(symbol_lib_dir, uploaded_sym)
            st.success(f"已儲存 {len(saved)} 個符號模板：{', '.join(saved)}")

        existing_syms = list_action(symbol_lib_dir)
        if existing_syms:
            st.markdown("**目前符號庫：**")
            for sym_path in existing_syms:
                col_name, col_del = st.columns([4, 1])
                col_name.text(sym_path.stem)
                if col_del.button("✕", key=f"del_sym_{sym_path.stem}"):
                    ok, msg = delete_action(sym_path)
                    if ok:
                        st.rerun()
                    else:
                        st.warning(msg)
        else:
            st.info("符號庫尚無模板，請上傳去背 PNG。")
