"""
測試完整功能（全選三個選項）
驗證 OneDNN 錯誤修復是否成功
"""

import sys
import codecs
import os

# ==================== 重要：PaddleOCR 環境變數設定 ====================
# 必須在任何 import 之前設定
# 問題 1: 禁用 PaddleX model source check（避免 modelscope/PyTorch DLL 錯誤）
os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'
# 問題 2: 禁用 OneDNN 後端（避免 PIR 相容性錯誤）
os.environ['FLAGS_use_mkldnn'] = 'False'
os.environ['FLAGS_use_onednn'] = 'False'

# 修復 Windows 控制台編碼
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

import cv2
import numpy as np
from app.manufacturing import ManufacturingPipeline

print("=" * 60)
print("測試完整功能（OCR + 幾何 + 符號全選）")
print("=" * 60)

# 創建測試圖片
img = np.ones((400, 800, 3), dtype=np.uint8) * 255

# 添加中英文文字
cv2.putText(img, "Manufacturing Process Test", (50, 80), 
            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
cv2.putText(img, "Bending Line", (50, 150), 
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)

# 添加幾何形狀（折彎線）
cv2.line(img, (100, 250), (700, 250), (0, 0, 0), 2)  # 水平線
cv2.line(img, (400, 200), (400, 300), (0, 0, 0), 1)  # 折彎虛線

# 添加圓形（孔洞）
cv2.circle(img, (200, 320), 20, (0, 0, 0), 2)
cv2.circle(img, (400, 320), 20, (0, 0, 0), 2)
cv2.circle(img, (600, 320), 20, (0, 0, 0), 2)

# 保存測試圖片
test_path = "test_full_features.png"
cv2.imwrite(test_path, img)
print(f"\n✓ 測試圖片已創建: {test_path}")

# 初始化管線（全選三個選項）
print("\n正在初始化製程辨識管線...")
print("  - OCR 文字辨識: ✓ 啟用")
print("  - 幾何特徵分析: ✓ 啟用")
print("  - 符號辨識: ✓ 啟用")
print("  - OneDNN: ✗ 已禁用（修復 PIR 錯誤）")

try:
    pipeline = ManufacturingPipeline(
        use_ocr=True,      # 啟用 OCR
        use_geometry=True,  # 啟用幾何
        use_symbols=True,   # 啟用符號
        use_visual=False    # 不使用 DINOv2（太慢）
    )
    print("\n✓ 管線初始化成功！")
    print(f"  - 載入製程數量: {pipeline.total_processes} 種")
except Exception as e:
    print(f"\n✗ 管線初始化失敗: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 執行辨識
print("\n正在執行完整辨識（OCR + 幾何 + 符號）...")
try:
    result = pipeline.recognize(
        test_path,
        top_n=5,
        min_confidence=0.2
    )
    
    print(f"\n✓ 辨識完成！")
    print(f"  - 處理時間: {result.total_time:.2f} 秒")
    print(f"  - 檢測到製程: {len(result.predictions)} 個")
    
    # 顯示特徵統計
    print("\n特徵提取統計:")
    print(f"  - OCR 文字: {len(result.features.ocr_results)} 個")
    print(f"  - 幾何線條: {len(result.features.geometry.lines) if result.features.geometry else 0} 條")
    print(f"  - 圓形/孔洞: {len(result.features.geometry.circles) if result.features.geometry else 0} 個")
    print(f"  - 符號: {len(result.features.symbols)} 個")
    
    # 顯示預測結果
    if result.predictions:
        print("\n預測結果 (Top 5):")
        for i, pred in enumerate(result.predictions[:5], 1):
            print(f"  [{i}] {pred.name} ({pred.process_id})")
            print(f"      信心度: {pred.confidence:.2%}")
            if pred.reasoning:
                reasoning_lines = pred.reasoning.split('\n')[:2]  # 只顯示前兩行
                for line in reasoning_lines:
                    if line.strip():
                        print(f"      → {line.strip()}")
    else:
        print("\n⚠ 未檢測到任何製程（可能需要調整門檻或圖片內容）")
    
    print("\n" + "=" * 60)
    print("✓✓✓ 全選測試成功！OneDNN 錯誤已修復 ✓✓✓")
    print("=" * 60)
    
except Exception as e:
    print(f"\n✗ 辨識失敗: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 清理
try:
    os.remove(test_path)
    print(f"\n✓ 清理測試檔案: {test_path}")
except:
    pass
