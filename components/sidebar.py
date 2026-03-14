
import streamlit as st
from typing import Dict, Any, Optional


def render_recognition_sidebar(
    container: Optional[Any] = None,
    default_min_confidence: float = 0.25,
    default_use_vlm: bool = False,
    default_use_rag: bool = False
) -> Dict[str, Any]:
    """
    Render recognition controls in the sidebar.

    Returns:
        Dict[str, Any]: Settings for recognition.
    """
    target = container if container is not None else st.sidebar

    if "use_vlm" not in st.session_state:
        st.session_state.use_vlm = default_use_vlm
    if "use_rag" not in st.session_state:
        st.session_state.use_rag = default_use_rag
    if "min_confidence" not in st.session_state:
        st.session_state.min_confidence = default_min_confidence

    with target:
        st.title("🔧 系統設定")

        use_vlm = st.checkbox(
            "啟用 VLM 視覺語言模型",
            value=st.session_state.use_vlm
        )
        st.session_state.use_vlm = use_vlm

        use_rag = st.checkbox(
            "└─ 開啟知識庫輔助 (RAG)",
            value=st.session_state.use_rag if use_vlm else False,
            disabled=not use_vlm
        )
        st.session_state.use_rag = use_rag if use_vlm else False

        min_confidence = st.slider(
            "信心度門檻",
            min_value=0.1,
            max_value=0.9,
            value=st.session_state.min_confidence,
            step=0.01,
            help="只顯示超過門檻的製程"
        )
        st.session_state.min_confidence = min_confidence

    return {
        "use_vlm": st.session_state.use_vlm,
        "use_rag": st.session_state.use_rag,
        "min_confidence": st.session_state.min_confidence
    }


