"""Feature-sliced modules for project portability."""

from .analysis_actions import run_analysis, save_rag_entry, build_analysis_request
from .knowledge_admin import list_kb_entries, update_kb_entry_description
from .symbol_library import save_symbol_templates, list_symbol_templates, delete_symbol_template
from .upload_flow import (
    decode_bom_uploads,
    scan_ocr_text,
    decode_child_views,
    build_collage_or_single,
    persist_temp_preview_image,
)

__all__ = [
    "run_analysis",
    "build_analysis_request",
    "save_rag_entry",
    "list_kb_entries",
    "update_kb_entry_description",
    "save_symbol_templates",
    "list_symbol_templates",
    "delete_symbol_template",
    "decode_bom_uploads",
    "scan_ocr_text",
    "decode_child_views",
    "build_collage_or_single",
    "persist_temp_preview_image",
]
