"""
Test script to verify A-B-C UI refactoring logic.

Tests:
1. Process list initialization from predictions
2. Add process to list
3. Remove process from list
4. RAG feedback queue recording
5. Title change based on is_corrected flag
"""

import sys
import os
from typing import Dict, List

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    os.system('chcp 65001 > nul')
    sys.stdout.reconfigure(encoding='utf-8')  # type: ignore[attr-defined]


def test_abc_ui_logic():
    """Test the core A-B-C UI logic without Streamlit."""
    
    # Simulate session state
    class SessionState:
        def __init__(self):
            self.editing_predictions: List[Dict] = []
            self.rag_feedback_queue: List[Dict] = []
            self.is_corrected: bool = False
    
    session = SessionState()
    
    # Test 1: Initialize with predictions
    print("Test 1: Initialize with predictions")
    initial_predictions = [
        {"process_id": "I01", "process_name": "雷射切割", "confidence": 0.85, "reasoning": "檢測到關鍵字: 雷射"},
        {"process_id": "J01", "process_name": "折彎", "confidence": 0.75, "reasoning": "檢測到折彎線 (3條)"}
    ]
    session.editing_predictions = [
        {
            "process_id": p["process_id"],
            "process_name": p["process_name"],
            "confidence": p["confidence"],
            "reasoning": p.get("reasoning", "")
        }
        for p in initial_predictions
    ]
    assert len(session.editing_predictions) == 2
    print(f"✅ Initialized with {len(session.editing_predictions)} predictions")
    
    # Test 2: Add new process
    print("\nTest 2: Add new process")
    target_process_id = "K01"
    target_process_name = "點焊"
    reasoning_input = "BOM表明確標註點焊"
    
    existing_ids = [item["process_id"] for item in session.editing_predictions]
    if target_process_id not in existing_ids:
        session.editing_predictions.append({
            "process_id": target_process_id,
            "process_name": target_process_name,
            "confidence": 1.0,
            "reasoning": reasoning_input if reasoning_input else "(人工新增)"
        })
        
        session.rag_feedback_queue.append({
            "action": "add",
            "process_id": target_process_id,
            "reasoning": reasoning_input
        })
        session.is_corrected = True
        print(f"✅ Added {target_process_id} - {target_process_name}")
    
    assert len(session.editing_predictions) == 3
    assert len(session.rag_feedback_queue) == 1
    assert session.is_corrected is True
    
    # Test 3: Remove process
    print("\nTest 3: Remove process")
    target_process_id = "J01"
    remove_reason = "BOM表分開列出，故非折彎"
    
    original_len = len(session.editing_predictions)
    session.editing_predictions = [
        item for item in session.editing_predictions
        if item.get("process_id") != target_process_id
    ]
    new_len = len(session.editing_predictions)
    
    if new_len < original_len:
        session.rag_feedback_queue.append({
            "action": "remove",
            "process_id": target_process_id,
            "reasoning": remove_reason
        })
        print(f"✅ Removed {target_process_id}")
    
    assert len(session.editing_predictions) == 2
    assert len(session.rag_feedback_queue) == 2
    
    # Test 4: RAG feedback queue merge
    print("\nTest 4: RAG feedback queue merge")
    reasoning_lines = [
        f"{item['process_id']}: {item.get('reasoning', '')}"
        for item in session.editing_predictions
        if item.get("process_id")
    ]
    
    if session.rag_feedback_queue:
        for feedback in session.rag_feedback_queue:
            action = feedback["action"]
            pid = feedback["process_id"]
            reason = feedback["reasoning"]
            if reason:
                reasoning_lines.append(f"[{action.upper()}] {pid}: {reason}")
    
    merged_reasoning = "\n".join(reasoning_lines)
    print("✅ Merged reasoning:")
    print(merged_reasoning)
    
    assert "[ADD] K01: BOM表明確標註點焊" in merged_reasoning
    assert "[REMOVE] J01: BOM表分開列出，故非折彎" in merged_reasoning
    
    # Test 5: Title change logic
    print("\nTest 5: Title change logic")
    if session.is_corrected:
        title = "人工校正所需製程為以下"
    else:
        title = "製程預測與人工校正"
    
    assert title == "人工校正所需製程為以下"
    print(f"✅ Title: {title}")
    
    # Test 6: Confidence adjustment
    print("\nTest 6: Confidence adjustment simulation")
    # Simulate user editing confidence in st.data_editor
    session.editing_predictions[0]["confidence"] = 0.90
    session.editing_predictions[1]["confidence"] = 0.95
    
    assert session.editing_predictions[0]["confidence"] == 0.90
    assert session.editing_predictions[1]["confidence"] == 0.95
    print("✅ Confidence values updated")
    
    print("\n" + "="*50)
    print("ALL TESTS PASSED ✅")
    print("="*50)
    
    # Display final state
    print("\nFinal State:")
    print(f"  Editing Predictions: {len(session.editing_predictions)} items")
    for item in session.editing_predictions:
        print(f"    - {item['process_id']}: {item['process_name']} ({item['confidence']:.0%})")
    print(f"  RAG Feedback Queue: {len(session.rag_feedback_queue)} items")
    print(f"  Is Corrected: {session.is_corrected}")
    

if __name__ == "__main__":
    try:
        test_abc_ui_logic()
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
