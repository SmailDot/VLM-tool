"""
Test script for multilingual OCR feature.
測試多語言 OCR 功能腳本

Tests:
1. Multilingual OCR (Chinese, English, Japanese, Korean)
2. Title block notes detection
3. Regional OCR scanning
"""

import cv2
import numpy as np
from app.manufacturing.extractors.ocr import OCRExtractor

def test_multilang_ocr():
    """測試多語言 OCR"""
    print("=" * 60)
    print("測試 1: 多語言 OCR (中英日韓)")
    print("=" * 60)
    
    # 初始化 OCR (啟用多語言)
    ocr = OCRExtractor(enable_multilang=True)
    
    # 測試圖片路徑 - 使用你的測試圖片
    test_images = [
        "test1.jpg",  # 如果有的話
        "test2.jpg"
    ]
    
    for img_path in test_images:
        try:
            print(f"\n處理圖片: {img_path}")
            image = cv2.imread(img_path)
            
            if image is None:
                print(f"  ⚠️  無法讀取圖片: {img_path}")
                continue
            
            # 執行多語言 OCR
            results = ocr.extract_multilang(
                image,
                languages=['chinese_cht', 'en', 'japan', 'korean'],
                confidence_threshold=0.5
            )
            
            print(f"  檢測到 {len(results)} 個文字區域")
            
            # 按語言分類
            by_lang = {}
            for result in results:
                lang = result.metadata.get('language', 'unknown') if hasattr(result, 'metadata') else 'unknown'
                if lang not in by_lang:
                    by_lang[lang] = []
                by_lang[lang].append(result)
            
            # 顯示結果
            for lang, texts in by_lang.items():
                lang_name = {
                    'chinese_cht': '繁體中文',
                    'ch': '簡體中文',
                    'en': '英文',
                    'japan': '日文',
                    'korean': '韓文'
                }.get(lang, lang)
                
                print(f"\n  【{lang_name}】 ({len(texts)} 個)")
                for text in texts[:5]:  # 只顯示前5個
                    print(f"    - {text.text} (信心度: {text.confidence:.2f})")
                
                if len(texts) > 5:
                    print(f"    ... 還有 {len(texts) - 5} 個")
            
        except Exception as e:
            print(f"  ❌ 錯誤: {e}")
    
    print("\n✅ 多語言 OCR 測試完成")


def test_title_block_detection():
    """測試標題欄注意事項檢測"""
    print("\n" + "=" * 60)
    print("測試 2: 標題欄注意事項檢測")
    print("=" * 60)
    
    # 初始化 OCR
    ocr = OCRExtractor(enable_multilang=True)
    
    # 測試圖片
    test_images = ["test1.jpg", "test2.jpg"]
    
    for img_path in test_images:
        try:
            print(f"\n處理圖片: {img_path}")
            image = cv2.imread(img_path)
            
            if image is None:
                print(f"  ⚠️  無法讀取圖片: {img_path}")
                continue
            
            # 檢測標題欄
            title_block_data = ocr.detect_title_block_notes(
                image,
                scan_bottom_right=True,
                region_ratio=0.25,
                confidence_threshold=0.5
            )
            
            print(f"  掃描區域: {title_block_data['region']}")
            print(f"  檢測到 {len(title_block_data['raw_texts'])} 行文字")
            print(f"  重要注意事項: {len(title_block_data['important_notes'])} 條")
            
            # 顯示重要注意事項
            if title_block_data['important_notes']:
                print("\n  【重要注意事項】")
                for i, note in enumerate(title_block_data['important_notes'], 1):
                    print(f"    {i}. {note}")
            else:
                print("\n  ℹ️  未檢測到重要注意事項關鍵字")
            
            # 顯示所有文字 (前10行)
            if title_block_data['raw_texts']:
                print("\n  【標題欄所有文字 (前10行)】")
                for text in title_block_data['raw_texts'][:10]:
                    print(f"    - {text}")
                
                if len(title_block_data['raw_texts']) > 10:
                    print(f"    ... 還有 {len(title_block_data['raw_texts']) - 10} 行")
            
        except Exception as e:
            print(f"  ❌ 錯誤: {e}")
    
    print("\n✅ 標題欄檢測測試完成")


def test_region_ocr():
    """測試區域 OCR"""
    print("\n" + "=" * 60)
    print("測試 3: 區域 OCR 掃描")
    print("=" * 60)
    
    # 初始化 OCR
    ocr = OCRExtractor()
    
    # 測試圖片
    img_path = "test1.jpg"
    
    try:
        print(f"\n處理圖片: {img_path}")
        image = cv2.imread(img_path)
        
        if image is None:
            print(f"  ⚠️  無法讀取圖片: {img_path}")
            return
        
        h, w = image.shape[:2]
        
        # 測試不同區域
        regions = [
            ("右下角 (25%)", (int(w * 0.75), int(h * 0.75), int(w * 0.25), int(h * 0.25))),
            ("左上角 (25%)", (0, 0, int(w * 0.25), int(h * 0.25))),
            ("中央 (50%)", (int(w * 0.25), int(h * 0.25), int(w * 0.5), int(h * 0.5)))
        ]
        
        for region_name, region_coords in regions:
            print(f"\n  掃描區域: {region_name}")
            print(f"    座標: {region_coords}")
            
            results = ocr.extract_region(
                image,
                region_coords,
                confidence_threshold=0.5
            )
            
            print(f"    檢測到 {len(results)} 個文字")
            for text in results[:3]:  # 顯示前3個
                print(f"      - {text.text} (bbox: {text.bbox})")
            
            if len(results) > 3:
                print(f"      ... 還有 {len(results) - 3} 個")
        
    except Exception as e:
        print(f"  ❌ 錯誤: {e}")
    
    print("\n✅ 區域 OCR 測試完成")


if __name__ == "__main__":
    print("\n" + "🔬" * 30)
    print("   多語言 OCR 功能測試")
    print("🔬" * 30 + "\n")
    
    # 執行所有測試
    try:
        test_multilang_ocr()
        test_title_block_detection()
        test_region_ocr()
    except Exception as e:
        print(f"\n❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("所有測試完成!")
    print("=" * 60)
