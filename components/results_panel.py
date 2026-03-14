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


def render_parent_notes_section(result) -> None:
    """Render parent context highlights and title-block details."""
    if not (result.parent_context and result.parent_context.important_notes):
        return

    st.warning("⚠️ 父圖重要注意事項")

    if result.parent_context.detected_languages:
        langs_display = {
            "chinese_cht": "繁體中文",
            "ch": "簡體中文",
            "en": "英文",
            "japan": "日文",
            "korean": "韓文",
        }
        detected_langs = [
            langs_display.get(lang, lang)
            for lang in result.parent_context.detected_languages
            if isinstance(lang, str) and lang
        ]
        st.info(f"🌐 檢測到語言: {', '.join(detected_langs)}")

    st.markdown("**重要提醒事項:**")
    for note in result.parent_context.important_notes:
        note_lower = note.lower()
        if any(kw in note_lower for kw in ["警告", "warning", "禁止"]):
            icon = "🚫"
        elif any(kw in note_lower for kw in ["注意", "caution", "小心"]):
            icon = "⚠️"
        elif any(kw in note_lower for kw in ["要求", "requirement", "必須"]):
            icon = "✓"
        else:
            icon = "•"
        st.markdown(f"{icon} {note}")

    if result.parent_context.title_block_text:
        with st.expander("📋 查看標題欄完整內容", expanded=False):
            st.markdown("**標題欄所有文字:**")
            for text in result.parent_context.title_block_text:
                if text.strip():
                    st.text(f"  {text}")

    st.divider()


def render_diagnostics_section(result) -> None:
    """Render diagnostics and extracted-feature stats."""
    with st.expander("診斷資訊 (Diagnostics)", expanded=False):
        diag = {
            "total_time": result.total_time,
            "warnings": result.warnings,
            "errors": result.errors,
            "extraction_time": result.features.extraction_time,
        }
        st.json(diag)

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
            for ocr in result.features.ocr_results[:5]:
                st.caption(f"- {ocr.text} (信心度: {ocr.confidence:.2f})")

        if result.features.symbols:
            st.markdown("**符號辨識結果:**")
            st.text(f"檢測到 {len(result.features.symbols)} 個符號")
            for sym in result.features.symbols:
                st.caption(f"- {sym.symbol_type} (信心度: {sym.confidence:.2f})")

        if result.features.raw_vlm_description:
            st.markdown("**🤖 VLM 視覺語言模型分析 (純文字描述):**")
            st.markdown(result.features.raw_vlm_description)
        elif result.features.vlm_analysis:
            st.markdown("**🤖 VLM 分析 (文字):**")
            st.text(str(result.features.vlm_analysis))

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
