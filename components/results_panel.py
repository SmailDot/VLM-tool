"""Results rendering helpers for review-friendly UI composition."""

import re
from typing import Callable, Tuple

import streamlit as st

from .text_format import format_streamlit_colors, strip_confidence_tags


def render_result_summary(result) -> None:
    """Render top metrics for one analysis result."""
    col_info1, col_info2, col_info3 = st.columns(3)

    with col_info1:
        st.metric("處理時間", f"{result.total_time:.2f}s")

    with col_info2:
        vlm_desc = result.features.raw_vlm_description or ""
        st.metric("VLM 描述字數", len(vlm_desc))

    with col_info3:
        orange_count = len(re.findall(r"<orange>(.*?)</orange>", result.features.raw_vlm_description or ""))
        red_count = len(re.findall(r"<red>(.*?)</red>", result.features.raw_vlm_description or ""))
        st.metric("需人工覆核項目", orange_count + red_count)


def render_vlm_description_section(result) -> str:
    """Render VLM description block and return raw description string."""
    vlm_desc = result.features.raw_vlm_description
    if vlm_desc:
        st.markdown("### 🤖 VLM 視覺重建結果")
        st.caption(
            "🟢 高信心（AI 確認可見）　"
            "🟠 中信心（AI 存疑，建議確認）　"
            "🔴 低信心（AI 沒把握，**請人工核對**）"
        )

        orange_items = re.findall(r"<orange>(.*?)</orange>", vlm_desc)
        red_items = re.findall(r"<red>(.*?)</red>", vlm_desc)
        if orange_items or red_items:
            warn_parts = []
            if red_items:
                warn_parts.append("🔴 沒把握（強烈建議人工核對）：" + "、".join(f"**{x}**" for x in red_items))
            if orange_items:
                warn_parts.append("🟠 存疑（建議確認）：" + "、".join(f"**{x}**" for x in orange_items))
            st.warning("⚠️ **AI 不確定以下項目，請人類專家務必核對：**\n\n" + "\n\n".join(warn_parts))

        colored_report = format_streamlit_colors(vlm_desc)
        st.markdown("###  VLM 視覺描述預覽")
        st.markdown(colored_report)
    else:
        st.info("⚠️ VLM 未返回效描述。請確認：① LM Studio 已啟動 ② 左侧「辨識設定」已勾選 VLM")

    return vlm_desc or ""


def render_hitl_rag_section(
    result,
    vlm_desc: str,
    save_action: Callable[[str, str, str], Tuple[bool, str]],
) -> None:
    """Render HITL correction and RAG save block."""
    st.markdown("### 修正區")

    vlm_key = id(result)
    if st.session_state.get("_hitl_result_key") != vlm_key:
        st.session_state["hitl_corrected_text"] = strip_confidence_tags(vlm_desc)
        st.session_state["_hitl_result_key"] = vlm_key

    st.text_area(
        "修正區 (可修正 AI 的錯誤描述)",
        height=200,
        placeholder="AI 的描述將自動填入此處，您可直接修改...",
        key="hitl_corrected_text",
        help="此處顯示的文字將在按下「儲存至 RAG 知識庫」時一併寫入。",
    )

    if st.button("💾 儲存至 RAG 知識庫", type="primary", key="btn_save_rag"):
        ok, msg = save_action(
            st.session_state.get("temp_file_path", ""),
            st.session_state.get("hitl_corrected_text", ""),
            st.session_state.get("bom_context_input", ""),
        )
        if ok:
            st.toast(msg, icon="✅")
        else:
            st.error(msg)
