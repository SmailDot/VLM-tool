"""Simple test for manufacturing pipeline (no emojis)."""

import sys
from pathlib import Path

project_root = Path.cwd()
sys.path.insert(0, str(project_root))

print("=" * 60)
print("MANUFACTURING PIPELINE TEST")
print("=" * 60)

# Test 1: Imports
print("\n[Test 1] Importing modules...")
try:
    from app.manufacturing import ManufacturingPipeline
    from app.manufacturing.extractors import OCRExtractor, GeometryExtractor
    from app.manufacturing.decision import DecisionEngine
    print("[OK] All imports successful")
except Exception as e:
    print(f"[ERR] Import failed: {e}")
    sys.exit(1)

# Test 2: Process library
print("\n[Test 2] Loading process library...")
try:
    engine = DecisionEngine()
    processes = engine.get_all_processes()
    print(f"[OK] Loaded {len(processes)} processes")
except Exception as e:
    print(f"[ERR] Process library failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Pipeline creation
print("\n[Test 3] Creating pipeline...")
try:
    pipeline = ManufacturingPipeline(use_visual=False)
    print("[OK] Pipeline created")
except Exception as e:
    print(f"[ERR] Pipeline creation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Dummy recognition
print("\n[Test 4] Testing recognition with dummy image...")
try:
    import numpy as np
    import cv2
    
    # Create dummy image
    dummy_img = np.ones((800, 600, 3), dtype=np.uint8) * 255
    cv2.putText(dummy_img, "BEND", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 3)
    cv2.line(dummy_img, (100, 300), (500, 300), (0, 0, 0), 2)
    
    # Run recognition
    result = pipeline.recognize(dummy_img, top_n=3)
    
    print(f"[OK] Recognition completed in {result.processing_time:.2f}s")
    print(f"     OCR results: {len(result.extracted_features.ocr_results)}")
    print(f"     Geometry shapes: {result.diagnostics.get('geometry_shapes', 0)}")
    
    if result.predictions:
        print(f"\n     Top prediction: {result.predictions[0].process_name}")
        print(f"     Confidence: {result.predictions[0].confidence:.2%}")
    else:
        print("     (No predictions above threshold)")
        
except Exception as e:
    print(f"[ERR] Recognition failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("ALL TESTS PASSED")
print("=" * 60)
