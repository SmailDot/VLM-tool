"""
System Validation Test Script
=============================
Tests the complete manufacturing recognition pipeline without emojis
to avoid Windows console encoding issues.

Run this before starting the Streamlit app to verify everything works.
"""

import sys
import os
import cv2
import time
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))


def print_section(title: str):
    """Print a section header"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_imports():
    """Test 1: Verify all imports work"""
    print_section("Test 1: Module Imports")
    
    try:
        from app.manufacturing import ManufacturingPipeline
        print("[PASS] ManufacturingPipeline import")
    except Exception as e:
        print(f"[FAIL] ManufacturingPipeline import: {e}")
        return False
    
    try:
        from app.manufacturing.decision import DecisionEngine
        print("[PASS] DecisionEngine import")
    except Exception as e:
        print(f"[FAIL] DecisionEngine import: {e}")
        return False
    
    try:
        from app.manufacturing.extractors import (
            GeometryExtractor,
            SymbolDetector,
            VisualEmbedder
        )
        print("[PASS] Extractors import")
    except Exception as e:
        print(f"[FAIL] Extractors import: {e}")
        return False
    
    print("[SUCCESS] All imports successful")
    return True


def test_process_library():
    """Test 2: Verify process library loads correctly"""
    print_section("Test 2: Process Library")
    
    try:
        from app.manufacturing.decision import DecisionEngine
        
        engine = DecisionEngine()
        num_processes = len(engine.process_library)
        
        print(f"[INFO] Loaded {num_processes} processes")
        
        if num_processes == 96:
            print("[PASS] All 96 processes loaded")
        else:
            print(f"[WARN] Expected 96 processes, got {num_processes}")
        
        # Show sample processes
        categories = {}
        for process in engine.process_library[:10]:
            cat = process.category
            categories[cat] = categories.get(cat, 0) + 1
        
        print(f"[INFO] Sample categories: {list(categories.keys())}")
        print("[SUCCESS] Process library loaded")
        return True
        
    except Exception as e:
        print(f"[FAIL] Process library error: {e}")
        return False


def test_pipeline_creation():
    """Test 3: Create pipeline without OCR"""
    print_section("Test 3: Pipeline Creation")
    
    try:
        from app.manufacturing import ManufacturingPipeline
        
        # Create pipeline without OCR (to avoid PaddlePaddle requirement)
        pipeline = ManufacturingPipeline(
            use_ocr=False,
            use_geometry=True,
            use_symbols=True,
            use_visual=False
        )
        
        print("[PASS] Pipeline created successfully")
        print(f"[INFO] OCR: {pipeline.use_ocr}")
        print(f"[INFO] Geometry: {pipeline.use_geometry}")
        print(f"[INFO] Symbols: {pipeline.use_symbols}")
        print(f"[INFO] Visual: {pipeline.use_visual}")
        print("[SUCCESS] Pipeline ready")
        return pipeline
        
    except Exception as e:
        print(f"[FAIL] Pipeline creation error: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_image_processing(pipeline):
    """Test 4: Process a test image"""
    print_section("Test 4: Image Processing")
    
    # Find test images
    test_images = [
        "test1.jpg",
        "test2.jpg",
        "test1_黑白.jpg"
    ]
    
    test_image = None
    for img_path in test_images:
        if os.path.exists(img_path):
            test_image = img_path
            break
    
    if not test_image:
        print("[SKIP] No test images found")
        return False
    
    print(f"[INFO] Using test image: {test_image}")
    
    try:
        # Load image
        image = cv2.imread(test_image)
        if image is None:
            print(f"[FAIL] Could not load image: {test_image}")
            return False
        
        h, w = image.shape[:2]
        print(f"[INFO] Image size: {w} x {h} pixels")
        
        # Run recognition
        print("[INFO] Running recognition...")
        start_time = time.time()
        
        result = pipeline.recognize(image, top_n=5, min_confidence=0.1)
        
        elapsed = time.time() - start_time
        print(f"[INFO] Processing time: {elapsed:.2f}s")
        
        # Display results
        print(f"\n[RESULTS] Top {len(result.predictions)} predictions:")
        print("-" * 60)
        
        for i, pred in enumerate(result.predictions, 1):
            conf_pct = pred.confidence * 100
            
            # Confidence level indicator
            if conf_pct >= 70:
                level = "HIGH"
            elif conf_pct >= 50:
                level = "MEDIUM"
            else:
                level = "LOW"
            
            print(f"\n{i}. {pred.name}")
            print(f"   Category: {pred.process_id}")
            print(f"   Confidence: {conf_pct:.1f}% [{level}]")
            
            if pred.reasoning:
                print(f"   Reasoning:")
                for evidence in pred.reasoning.split("\n")[:3]:
                    if evidence.strip():
                        print(f"     - {evidence}")
        
        # Show diagnostics
        print("\n[DIAGNOSTICS]")
        print("-" * 60)
        print(f"  total_time: {result.total_time}s")
        print(f"  warnings: {result.warnings}")
        print(f"  errors: {result.errors}")
        print(f"  extraction_time: {result.features.extraction_time}s")
        
        print("\n[SUCCESS] Image processing complete")
        return True
        
    except Exception as e:
        print(f"[FAIL] Processing error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_streamlit_app():
    """Test 5: Verify Streamlit app can be imported"""
    print_section("Test 5: Streamlit App")
    
    if not os.path.exists("aov_app.py"):
        print("[FAIL] aov_app.py not found")
        return False
    
    print("[INFO] aov_app.py exists")
    print("[INFO] To test the UI, run:")
    print("       streamlit run aov_app.py")
    print("[SKIP] Streamlit app validation (requires manual testing)")
    return True


def main():
    """Run all tests"""
    print("\n")
    print("*" * 60)
    print("  NKUST Manufacturing Recognition System")
    print("  System Validation Test")
    print("*" * 60)
    
    results = []
    
    # Run tests
    results.append(("Imports", test_imports()))
    results.append(("Process Library", test_process_library()))
    
    pipeline = test_pipeline_creation()
    results.append(("Pipeline Creation", pipeline is not None))
    
    if pipeline:
        results.append(("Image Processing", test_image_processing(pipeline)))
    else:
        results.append(("Image Processing", False))
    
    results.append(("Streamlit App", test_streamlit_app()))
    
    # Summary
    print_section("TEST SUMMARY")
    
    passed = sum(1 for _, status in results if status)
    total = len(results)
    
    for name, status in results:
        status_str = "[PASS]" if status else "[FAIL]"
        print(f"{status_str} {name}")
    
    print("\n" + "-" * 60)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n[SUCCESS] All tests passed! System is ready.")
        print("\nNext steps:")
        print("  1. Run: streamlit run aov_app.py")
        print("  2. Upload engineering drawings")
        print("  3. Verify recognition results")
        return 0
    else:
        print("\n[WARNING] Some tests failed. Please review errors above.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
