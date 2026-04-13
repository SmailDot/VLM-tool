"""Feature-sliced modules for project portability.

Modules in this package have different weight tiers — import them directly
to avoid loading the full AI stack when only a lightweight module is needed:

  Lightweight (no torch/paddle/openai):
    from app.features.shadow_test import ShadowTester

  Heavyweight (requires full AI environment):
    from app.features.analysis_actions import run_analysis, build_analysis_request
    from app.features.knowledge_admin import list_kb_entries, ...
    from app.features.upload_flow import decode_bom_uploads, ...
    from app.features.symbol_library import save_symbol_templates, ...
"""

# No eager imports — prevents loading the entire AI stack when importing
# a single lightweight module like shadow_test.

__all__ = [
    "run_analysis",
    "build_analysis_request",
    "save_rag_entry",
    "list_kb_entries",
    "update_kb_entry_description",
    "delete_kb_entry",
    "get_kb_stats",
    "get_rag_metrics_history",
    "save_symbol_templates",
    "list_symbol_templates",
    "delete_symbol_template",
    "decode_bom_uploads",
    "scan_ocr_text",
    "decode_child_views",
    "build_collage_or_single",
    "persist_temp_preview_image",
    "ShadowTester",
]
