"""Text formatting helpers for VLM confidence-tag rendering."""

import re


def format_streamlit_colors(text: str) -> str:
    """Convert <green>/<orange>/<red> tags into Streamlit color markdown."""
    if not text:
        return ""
    text = re.sub(r"<green>(.*?)</green>", r":green[**\1**]", text)
    text = re.sub(r"<orange>(.*?)</orange>", r":orange[**\1**]", text)
    text = re.sub(r"<red>(.*?)</red>", r":red[**\1**]", text)
    return text


def strip_confidence_tags(raw_text: str) -> str:
    """Remove confidence XML-like tags and return plain text."""
    return re.sub(r"</?(?:green|orange|red)>", "", raw_text)
