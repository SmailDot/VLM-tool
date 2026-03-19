"""Analysis execution and RAG save actions."""

from pathlib import Path
from typing import Any, Mapping, Optional, Tuple

import time

from app.core import AOVCoreService, AnalysisRequest
from app.manufacturing.schema import RecognitionResult
from app.knowledge.manager import KnowledgeBaseManager


def run_analysis(core_service: AOVCoreService, request: AnalysisRequest) -> Tuple[RecognitionResult, float]:
    """Execute drawing analysis and return result with elapsed seconds."""
    start_time = time.time()
    result = core_service.analyze(request)
    elapsed = time.time() - start_time
    return result, elapsed


def build_analysis_request(
    image: Any,
    parent_image: Optional[Any],
    child_images: Optional[list],
    view_labels: Optional[list],
    locked_bom: str,
    bom_context_input: str,
    use_rag: bool,
    use_vlm: bool,
    min_confidence: float,
) -> AnalysisRequest:
    """Build VLM request with BOM + child-view injection as core responsibility."""
    effective_bom = locked_bom or bom_context_input
    return AnalysisRequest(
        image=image,
        parent_image=parent_image,
        child_images=child_images,
        view_labels=view_labels,
        bom_context=effective_bom,
        use_rag=use_rag,
        use_vlm=use_vlm,
        min_confidence=min_confidence,
    )


def save_rag_entry(temp_file_path: str, corrected_text: str, bom_context: str) -> Tuple[bool, str]:
    """Persist corrected VLM description into RAG knowledge base."""
    if not temp_file_path or not Path(temp_file_path).exists():
        return False, "⚠️ 暫存圖檔已遺失，無法加入知識庫，請重新上傳圖紙。"

    kb = KnowledgeBaseManager()
    final_desc = (corrected_text or "").strip()
    kb.add_entry(
        image_path=temp_file_path,
        features={"raw_vlm_description": final_desc},
        correct_processes=[],
        reasoning=final_desc,
        bom_context=bom_context,
    )
    return True, "✅ 敘述已成功寫入 RAG 知識庫＆零件圖庫已更新！"
