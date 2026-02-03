"""
快速測試腳本 - 驗證製程辨識系統的核心功能
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

from app.manufacturing import ManufacturingPipeline
import cv2
import numpy as np

def test_frequency_filter():
    """測試頻率過濾功能"""
    print("=" * 60)
    print("[TEST] Testing Frequency Filter")
    print("=" * 60)
    
    # 初始化 pipeline
    pipeline = ManufacturingPipeline(
        use_ocr=False,
        use_geometry=True,
        use_symbols=True
    )
    
    print(f"\n✅ Pipeline initialized")
    print(f"   Total processes in library: {len(pipeline.decision_engine.processes)}")
    
    # 建立測試圖片 (白底黑線模擬工程圖)
    test_image = np.ones((800, 1200, 3), dtype=np.uint8) * 255
    
    # 畫一些幾何特徵
    cv2.line(test_image, (100, 400), (1100, 400), (0, 0, 0), 2)  # 水平線
    cv2.circle(test_image, (600, 400), 50, (0, 0, 0), 2)  # 圓形
    
    print("\n[TEST] Running recognition with different frequency filters...")
    
    # 測試案例 1: 只顯示「高」頻率製程
    print("\n--- Test 1: 只顯示「高」頻率 ---")
    result1 = pipeline.recognize(
        test_image,
        top_n=10,
        min_confidence=0.1,
        frequency_filter=["高"]
    )
    print(f"結果數量: {len(result1.predictions)}")
    for pred in result1.predictions[:3]:
        print(f"  - {pred.name} ({pred.process_id}): {pred.confidence:.2%}")
    
    # 測試案例 2: 顯示「高」+「中」頻率製程 (預設)
    print("\n--- Test 2: 顯示「高」+「中」頻率 ---")
    result2 = pipeline.recognize(
        test_image,
        top_n=10,
        min_confidence=0.1,
        frequency_filter=["高", "中"]
    )
    print(f"結果數量: {len(result2.predictions)}")
    for pred in result2.predictions[:3]:
        print(f"  - {pred.name} ({pred.process_id}): {pred.confidence:.2%}")
    
    # 測試案例 3: 顯示所有頻率
    print("\n--- Test 3: 顯示所有頻率 ---")
    result3 = pipeline.recognize(
        test_image,
        top_n=10,
        min_confidence=0.1,
        frequency_filter=None  # None = 不過濾
    )
    print(f"結果數量: {len(result3.predictions)}")
    for pred in result3.predictions[:3]:
        print(f"  - {pred.name} ({pred.process_id}): {pred.confidence:.2%}")
    
    # 驗證過濾邏輯
    print("\n[VERIFY] 驗證過濾邏輯...")
    assert len(result1.predictions) <= len(result2.predictions), "高 應該 <= 高+中"
    assert len(result2.predictions) <= len(result3.predictions), "高+中 應該 <= 全部"
    print("✅ 過濾邏輯正確")
    
    # 統計頻率分布
    print("\n[STATS] 製程庫頻率統計:")
    freq_count = {}
    for proc in pipeline.decision_engine.processes.values():
        freq = proc.get("frequency", "無")
        freq_count[freq] = freq_count.get(freq, 0) + 1
    
    for freq, count in sorted(freq_count.items()):
        print(f"  {freq}: {count} 個製程")
    
    print("\n" + "=" * 60)
    print("[DONE] All tests passed!")
    print("=" * 60)


def test_process_library():
    """測試製程知識庫載入"""
    print("\n[TEST] Testing Process Library Loading...")
    
    from app.manufacturing.decision import DecisionEngineV2
    
    engine = DecisionEngineV2()
    
    print(f"✅ Loaded {len(engine.processes)} processes")
    
    # 檢查幾個關鍵製程
    key_processes = ["C05", "D01", "D04", "D06", "E01"]
    
    for proc_id in key_processes:
        if proc_id in engine.processes:
            proc = engine.processes[proc_id]
            print(f"  ✓ {proc_id}: {proc['name']} (頻率: {proc.get('frequency', 'N/A')})")
        else:
            print(f"  ✗ {proc_id}: NOT FOUND")


if __name__ == "__main__":
    print("\n🧪 NKUST 製程辨識系統 - 功能測試")
    print("=" * 60)
    
    try:
        test_process_library()
        test_frequency_filter()
        
        print("\n✨ 所有測試通過！系統運作正常。")
        
    except Exception as e:
        print(f"\n❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
