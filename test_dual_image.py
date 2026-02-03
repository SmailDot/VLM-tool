"""
測試雙圖辨識模式 - Parent Image + Child Image
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

from app.manufacturing import ManufacturingPipeline
import cv2
import numpy as np

def create_mock_parent_image():
    """建立模擬父圖 (包含標題欄、技術要求)"""
    img = np.ones((1000, 1500, 3), dtype=np.uint8) * 255
    
    # 添加一些模擬文字區域 (實際上需要OCR才能讀取)
    # 這裡只是視覺化,實際測試需要真實圖片
    cv2.putText(img, "Material: SUS304 (Stainless Steel)", (50, 100), 
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
    cv2.putText(img, "Customer: ASML", (50, 150), 
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
    cv2.putText(img, "Special Requirements:", (50, 250), 
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
    cv2.putText(img, "- Cleanroom Class 100", (50, 300), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    cv2.putText(img, "- Trivalent Chromium", (50, 350), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    
    return img

def create_mock_child_image():
    """建立模擬子圖 (包含零件幾何特徵)"""
    img = np.ones((800, 1200, 3), dtype=np.uint8) * 255
    
    # 模擬零件輪廓
    cv2.rectangle(img, (200, 200), (1000, 600), (0, 0, 0), 2)
    
    # 模擬折彎線
    cv2.line(img, (400, 200), (400, 600), (0, 0, 0), 1)
    cv2.line(img, (700, 200), (700, 600), (0, 0, 0), 1)
    
    # 模擬孔洞
    cv2.circle(img, (300, 400), 20, (0, 0, 0), 2)
    cv2.circle(img, (500, 400), 20, (0, 0, 0), 2)
    cv2.circle(img, (800, 400), 20, (0, 0, 0), 2)
    
    # 模擬焊接符號區域
    cv2.putText(img, "WELD", (600, 650), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    
    return img

def test_dual_image_mode():
    """測試雙圖辨識模式"""
    print("=" * 80)
    print("[TEST] Dual-Image Recognition Mode")
    print("=" * 80)
    
    # 初始化 pipeline (關閉OCR以加速測試)
    pipeline = ManufacturingPipeline(
        use_ocr=False,  # 若要完整測試,設為True
        use_geometry=True,
        use_symbols=True
    )
    
    print("\n✅ Pipeline initialized")
    
    # 建立測試圖片
    parent_image = create_mock_parent_image()
    child_image = create_mock_child_image()
    
    print("\n📷 Created mock images:")
    print(f"   Parent image: {parent_image.shape}")
    print(f"   Child image: {child_image.shape}")
    
    # === Test Case 1: 僅子圖模式 (傳統) ===
    print("\n" + "-" * 80)
    print("[Test 1] Child Image Only (Traditional Mode)")
    print("-" * 80)
    
    result_child_only = pipeline.recognize(
        image=child_image,
        parent_image=None,  # 不提供父圖
        top_n=10,
        min_confidence=0.2
    )
    
    print(f"\n結果數量: {len(result_child_only.predictions)}")
    print("\nTop 5 predictions:")
    for i, pred in enumerate(result_child_only.predictions[:5], 1):
        print(f"  {i}. {pred.name} ({pred.process_id}): {pred.confidence:.2%}")
        if pred.reasoning:
            print(f"     └─ {pred.reasoning[:100]}...")
    
    print(f"\n父圖資訊: {result_child_only.parent_context}")
    
    # === Test Case 2: 雙圖模式 ===
    print("\n" + "-" * 80)
    print("[Test 2] Parent + Child Images (Dual-Image Mode)")
    print("-" * 80)
    
    result_dual = pipeline.recognize(
        image=child_image,
        parent_image=parent_image,  # 提供父圖
        top_n=10,
        min_confidence=0.2
    )
    
    print(f"\n結果數量: {len(result_dual.predictions)}")
    
    # 顯示父圖解析結果
    if result_dual.parent_context:
        print("\n[Parent Context] 父圖全域資訊:")
        print(f"   材質: {result_dual.parent_context.material}")
        print(f"   客戶: {result_dual.parent_context.customer}")
        print(f"   無塵室等級: {result_dual.parent_context.cleanroom_level}")
        print(f"   表面處理: {result_dual.parent_context.surface_treatment}")
        print(f"   特殊要求: {result_dual.parent_context.special_requirements}")
        print(f"   觸發的預設製程: {result_dual.parent_context.triggered_processes}")
    
    print("\n[Child Predictions] Top 10 預測結果:")
    for i, pred in enumerate(result_dual.predictions[:10], 1):
        source_tag = "[父圖]" if pred.reasoning and "父圖觸發" in pred.reasoning else "[子圖]"
        print(f"  {i}. {source_tag} {pred.name} ({pred.process_id}): {pred.confidence:.2%}")
        if pred.reasoning:
            # 只顯示前100字元
            reasoning_lines = pred.reasoning.split('\n')
            print(f"     └─ {reasoning_lines[0][:80]}")
    
    # === 驗證邏輯 ===
    print("\n" + "-" * 80)
    print("[VERIFY] Logic Rules Validation")
    print("-" * 80)
    
    result_ids = {p.process_id for p in result_dual.predictions}
    
    # 驗證預設製程
    print("\n檢查預設製程 (應由父圖觸發):")
    default_processes = ["B01", "B02", "E01", "I01", "H02", "J01"]
    for proc_id in default_processes:
        status = "✅" if proc_id in result_ids else "❌"
        print(f"  {status} {proc_id}")
    
    # 驗證衝突解決 (如果有D04,不應有D01和D06)
    if "D04" in result_ids:
        print("\n檢查衝突解決 (D04 應取代 D01+D06):")
        d01_status = "❌ 衝突!" if "D01" in result_ids else "✅ 已移除"
        d06_status = "❌ 衝突!" if "D06" in result_ids else "✅ 已移除"
        print(f"  D01: {d01_status}")
        print(f"  D06: {d06_status}")
    
    # 驗證自動補全 (如果有F01,應自動添加F14)
    if "F01" in result_ids:
        print("\n檢查自動補全 (F01 應觸發 F14):")
        f14_status = "✅ 已補全" if "F14" in result_ids else "❌ 未觸發"
        print(f"  F14: {f14_status}")
    
    print("\n" + "=" * 80)
    print("[DONE] Dual-Image Mode Test Completed!")
    print("=" * 80)
    print("\n💡 Note: 此測試使用模擬圖片,實際效果需使用真實工程圖紙")
    print("💡 若啟用 OCR (use_ocr=True),可辨識真實圖片中的文字資訊")

if __name__ == "__main__":
    try:
        test_dual_image_mode()
    except Exception as e:
        print(f"\n❌ Test failed with error:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
