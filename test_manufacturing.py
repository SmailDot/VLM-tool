"""
Test script for Manufacturing Recognition Pipeline.

Quick verification that all modules work correctly.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.manufacturing import ManufacturingPipeline, recognize


def test_pipeline_import():
    """Test 1: Verify all imports work."""
    print("=" * 60)
    print("TEST 1: Import Verification")
    print("=" * 60)
    
    try:
        from app.manufacturing.extractors import (
            OCRExtractor, GeometryExtractor,
            SymbolDetector, VisualEmbedder
        )
        from app.manufacturing.decision import DecisionEngine
        from app.manufacturing import ManufacturingPipeline
        
        print("✅ All imports successful")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False


def test_process_library():
    """Test 2: Verify process_lib.json loads correctly."""
    print("\n" + "=" * 60)
    print("TEST 2: Process Library Loading")
    print("=" * 60)
    
    try:
        from app.manufacturing.decision import DecisionEngine
        
        engine = DecisionEngine()
        processes = engine.get_all_processes()
        
        print(f"✅ Loaded {len(processes)} processes")
        
        # Show first 5 processes
        print("\nSample processes:")
        for i, (pid, pdef) in enumerate(list(processes.items())[:5]):
            print(f"  {pid}: {pdef.name} ({pdef.category})")
        
        return True
    except Exception as e:
        print(f"❌ Process library loading failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_extractors_basic():
    """Test 3: Verify extractors initialize correctly."""
    print("\n" + "=" * 60)
    print("TEST 3: Extractor Initialization")
    print("=" * 60)
    
    try:
        from app.manufacturing.extractors import (
            OCRExtractor, GeometryExtractor, SymbolDetector
        )
        
        # OCR
        print("Initializing OCRExtractor...")
        ocr = OCRExtractor(show_log=False)
        print("  ✅ OCR initialized")
        
        # Geometry
        print("Initializing GeometryExtractor...")
        geo = GeometryExtractor()
        print("  ✅ Geometry initialized")
        
        # Symbol
        print("Initializing SymbolDetector...")
        sym = SymbolDetector()
        print("  ✅ Symbol detector initialized")
        
        print("\n✅ All extractors initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Extractor initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_pipeline_creation():
    """Test 4: Verify pipeline creates successfully."""
    print("\n" + "=" * 60)
    print("TEST 4: Pipeline Creation")
    print("=" * 60)
    
    try:
        # Create pipeline without visual embeddings (faster)
        pipeline = ManufacturingPipeline(
            use_ocr=True,
            use_geometry=True,
            use_symbols=True,
            use_visual=False  # Skip DINOv2 for quick test
        )
        
        print("✅ Pipeline created successfully")
        print(f"  - OCR: {'Enabled' if pipeline.use_ocr else 'Disabled'}")
        print(f"  - Geometry: {'Enabled' if pipeline.use_geometry else 'Disabled'}")
        print(f"  - Symbols: {'Enabled' if pipeline.use_symbols else 'Disabled'}")
        print(f"  - Visual: {'Enabled' if pipeline.use_visual else 'Disabled'}")
        
        return True
    except Exception as e:
        print(f"❌ Pipeline creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_dummy_recognition():
    """Test 5: Test recognition with dummy image."""
    print("\n" + "=" * 60)
    print("TEST 5: Dummy Recognition Test")
    print("=" * 60)
    
    try:
        import numpy as np
        import cv2
        
        # Create a simple dummy image (white background, black text/shapes)
        dummy_img = np.ones((800, 600, 3), dtype=np.uint8) * 255
        
        # Draw some text
        cv2.putText(
            dummy_img,
            "WELDING",
            (50, 100),
            cv2.FONT_HERSHEY_SIMPLEX,
            2,
            (0, 0, 0),
            3
        )
        
        # Draw some lines (potential bend lines)
        cv2.line(dummy_img, (100, 300), (500, 300), (0, 0, 0), 2)
        cv2.line(dummy_img, (100, 400), (500, 400), (0, 0, 0), 2)
        
        # Draw some circles (potential holes)
        cv2.circle(dummy_img, (200, 500), 20, (0, 0, 0), 2)
        cv2.circle(dummy_img, (400, 500), 20, (0, 0, 0), 2)
        
        print("Created dummy image (800x600 with text, lines, circles)")
        
        # Create pipeline
        pipeline = ManufacturingPipeline(use_visual=False)
        
        print("Running recognition...")
        result = pipeline.recognize(dummy_img, top_n=3)
        
        print(f"\n✅ Recognition completed in {result.processing_time:.2f}s")
        print(f"\nDiagnostics:")
        for key, value in result.diagnostics.items():
            print(f"  - {key}: {value}")
        
        print(f"\nTop predictions:")
        if result.predictions:
            for i, pred in enumerate(result.predictions[:3], 1):
                print(f"  {i}. {pred.process_name} (信心度: {pred.confidence:.2%})")
                if pred.evidence:
                    print(f"     證據: {', '.join(pred.evidence)}")
        else:
            print("  (No predictions above threshold)")
        
        return True
    except Exception as e:
        print(f"❌ Recognition test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("MANUFACTURING PIPELINE TEST SUITE")
    print("=" * 60 + "\n")
    
    tests = [
        test_pipeline_import,
        test_process_library,
        test_extractors_basic,
        test_pipeline_creation,
        test_dummy_recognition
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"\n❌ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    
    print(f"\nPassed: {passed}/{total}")
    
    if passed == total:
        print("\n==> All tests passed! System is ready.")
    else:
        print(f"\n==> {total - passed} test(s) failed. Check errors above.")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
