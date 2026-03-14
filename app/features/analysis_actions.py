"""Analysis execution and RAG save actions."""

from pathlib import Path
from typing import Tuple

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
