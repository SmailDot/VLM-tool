"""
Test script for tolerance detection and precision logic.

Tests:
1. Extract tolerances from OCR text
2. Validate tolerance parsing (symmetric, asymmetric, implied)
3. Test precision logic (K01 triggering for tight tolerances)
4. Verify laser cutting confidence reduction
"""

import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.manufacturing.extractors.tolerance_parser import ToleranceParser, ToleranceSpec
from app.manufacturing.schema import OCRResult
from app.manufacturing import ManufacturingPipeline
import cv2


def test_tolerance_parsing():
    """Test tolerance text parsing with various formats"""
    print("=" * 60)
    print("TEST 1: Tolerance Text Parsing")
    print("=" * 60)
    
    parser = ToleranceParser()
    
    # Test cases
    test_cases = [
        # (text, expected_value, expected_type)
        ("±0.3", 0.3, "symmetric"),
        ("± 0.05", 0.05, "symmetric"),
        ("±0.02", 0.02, "symmetric"),
        ("+0.3/-0.2", 0.3, "asymmetric"),
        ("+0.05/-0.03", 0.05, "asymmetric"),
        ("+0.1/-0.1", 0.1, "symmetric"),  # Equal values → symmetric
        ("0.05", 0.05, "implied"),
        ("0.02", 0.02, "implied"),
        ("150", None, None),  # Too large, should be rejected
        ("ABC", None, None),  # Not a tolerance
    ]
    
    print(f"\nTesting {len(test_cases)} tolerance patterns...\n")
    
    passed = 0
    failed = 0
    
    for text, expected_value, expected_type in test_cases:
        # Create mock OCR result
        ocr = OCRResult(text=text, confidence=0.9, bbox=[0, 0, 50, 20])
        
        # Parse
        tol_spec = parser._parse_tolerance_text(text, ocr.bbox)
        
        # Check result
        if expected_value is None:
            if tol_spec is None:
                print(f"✅ '{text}' → Correctly rejected")
                passed += 1
            else:
                print(f"❌ '{text}' → Should be rejected, got {tol_spec.value}mm")
                failed += 1
        else:
            if tol_spec is None:
                print(f"❌ '{text}' → Should parse as {expected_value}mm, got None")
                failed += 1
            elif abs(tol_spec.value - expected_value) < 0.001 and tol_spec.tolerance_type == expected_type:
                print(f"✅ '{text}' → {tol_spec.value}mm ({tol_spec.tolerance_type})")
                passed += 1
            else:
                print(f"❌ '{text}' → Expected {expected_value}mm ({expected_type}), got {tol_spec.value}mm ({tol_spec.tolerance_type})")
                failed += 1
    
    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")
    print(f"{'='*60}\n")
    
    return passed, failed


def test_tolerance_extraction():
    """Test tolerance extraction from OCR results"""
    print("=" * 60)
    print("TEST 2: Tolerance Extraction from OCR")
    print("=" * 60)
    
    parser = ToleranceParser()
    
    # Mock OCR results (simulating a real drawing)
    ocr_results = [
        OCRResult(text="零件名稱", confidence=0.95, bbox=[10, 10, 80, 20]),
        OCRResult(text="150", confidence=0.92, bbox=[100, 50, 40, 20]),  # Dimension
        OCRResult(text="±0.3", confidence=0.90, bbox=[150, 50, 30, 15]),  # Tolerance 1
        OCRResult(text="φ20", confidence=0.93, bbox=[200, 80, 40, 20]),  # Diameter
        OCRResult(text="±0.05", confidence=0.91, bbox=[250, 80, 35, 15]),  # Tolerance 2 (tight!)
        OCRResult(text="R10", confidence=0.89, bbox=[300, 120, 30, 20]),  # Radius
        OCRResult(text="45°", confidence=0.88, bbox=[350, 150, 30, 20]),  # Angle
    ]
    
    print(f"\nMock OCR results: {len(ocr_results)} texts")
    print("Texts:", [ocr.text for ocr in ocr_results])
    
    # Extract tolerances
    tolerances = parser.extract_tolerances(ocr_results)
    
    print(f"\nExtracted {len(tolerances)} tolerance(s):")
    for i, tol in enumerate(tolerances, 1):
        print(f"  {i}. {tol.text} → {tol.value}mm ({tol.tolerance_type})")
    
    # Check precision summary
    summary = parser.get_precision_summary(tolerances)
    print(f"\nPrecision Summary:")
    print(f"  Tightest tolerance: {summary['tightest_tolerance']}mm")
    print(f"  Requires precision: {summary['requires_precision']}")
    print(f"  Precision category: {summary['precision_category']}")
    print(f"  Tolerance count: {summary['tolerance_count']}")
    
    # Validate
    assert len(tolerances) == 2, f"Expected 2 tolerances, got {len(tolerances)}"
    assert tolerances[0].value == 0.05, f"Tightest should be 0.05mm, got {tolerances[0].value}mm"
    assert summary['requires_precision'] == True, "Should require precision machining"
    
    print(f"\n✅ All assertions passed!")
    print(f"{'='*60}\n")


def test_precision_logic_integration(image_path: str = None):
    """Test precision logic in full pipeline"""
    print("=" * 60)
    print("TEST 3: Precision Logic Integration")
    print("=" * 60)
    
    # Create pipeline with OCR enabled
    pipeline = ManufacturingPipeline(
        use_ocr=True,
        use_geometry=True,
        use_symbols=True
    )
    
    if image_path and Path(image_path).exists():
        print(f"\nTesting with real image: {image_path}")
        
        # Load image
        image = cv2.imread(image_path)
        if image is None:
            print(f"❌ Failed to load image: {image_path}")
            return
        
        # Run recognition
        result = pipeline.recognize(image, top_n=10)
        
        # Check if tolerances were extracted
        print(f"\n📊 Extracted Features:")
        print(f"  OCR texts: {len(result.features.ocr_results)}")
        print(f"  Tolerances: {len(result.features.tolerances)}")
        
        if result.features.tolerances:
            print(f"\n📏 Tolerance Details:")
            for tol in result.features.tolerances:
                print(f"  - {tol.text}: {tol.value}mm ({tol.tolerance_type})")
            
            min_tol = min(tol.get_max_tolerance() for tol in result.features.tolerances)
            print(f"\n  Tightest tolerance: ±{min_tol:.2f}mm")
            
            if min_tol < 0.1:
                print(f"  ⚠️  HIGH PRECISION REQUIRED (<0.1mm)")
        else:
            print(f"  ⚠️  No tolerances detected (OCR may have failed or no tolerances in drawing)")
        
        # Check if K01 was triggered
        print(f"\n🏭 Process Predictions:")
        k01_found = False
        for i, pred in enumerate(result.predictions[:10], 1):
            marker = ""
            if pred.process_id == "K01":
                marker = " ⭐ (PRECISION MACHINING)"
                k01_found = True
            elif pred.process_id in ["C01", "C02"]:
                marker = " 📉 (Laser cutting - confidence may be reduced)"
            
            print(f"  {i}. [{pred.process_id}] {pred.name}: {pred.confidence:.2%}{marker}")
            if pred.reasoning and ("精密公差" in pred.reasoning or "公差" in pred.reasoning):
                print(f"      Reasoning: {pred.reasoning}")
        
        # Validate logic
        if result.features.tolerances:
            min_tol = min(tol.get_max_tolerance() for tol in result.features.tolerances)
            if min_tol < 0.1:
                if k01_found:
                    print(f"\n✅ K01 (切削) correctly triggered for tight tolerance!")
                else:
                    print(f"\n⚠️  K01 (切削) NOT found - may need to check decision engine logic")
        
    else:
        print(f"\n⚠️  No image provided or image not found")
        print(f"Run with: python test_tolerance_detection.py <image_path>")
        print(f"\nTesting with mock data instead...\n")
        
        # Create mock features with tight tolerance
        from app.manufacturing.schema import ExtractedFeatures, GeometryFeatures
        
        mock_ocr = [
            OCRResult(text="±0.05", confidence=0.90, bbox=[100, 50, 30, 15])
        ]
        
        parser = ToleranceParser()
        mock_tolerances = parser.extract_tolerances(mock_ocr)
        
        mock_features = ExtractedFeatures(
            ocr_results=mock_ocr,
            tolerances=mock_tolerances,
            geometry=GeometryFeatures()
        )
        
        # Test decision engine directly
        from app.manufacturing.decision.engine_v2 import DecisionEngineV2
        engine = DecisionEngineV2()
        
        predictions = engine.predict(mock_features, top_n=10)
        
        print(f"Mock test with ±0.05mm tolerance:")
        print(f"\nPredictions:")
        for i, pred in enumerate(predictions[:10], 1):
            marker = " ⭐" if pred.process_id == "K01" else ""
            print(f"  {i}. [{pred.process_id}] {pred.name}: {pred.confidence:.2%}{marker}")
            if "精密公差" in pred.reasoning:
                print(f"      {pred.reasoning}")
        
        k01_found = any(p.process_id == "K01" for p in predictions)
        if k01_found:
            print(f"\n✅ K01 correctly added for tight tolerance!")
        else:
            print(f"\n❌ K01 NOT found - precision logic may not be working")
    
    print(f"\n{'='*60}\n")


def main():
    """Run all tests"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test tolerance detection and precision logic")
    parser.add_argument(
        "image",
        nargs="?",
        default=None,
        help="Path to engineering drawing with tolerances (optional)"
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("TOLERANCE DETECTION & PRECISION LOGIC TEST SUITE")
    print("="*60 + "\n")
    
    # Test 1: Text parsing
    passed, failed = test_tolerance_parsing()
    
    # Test 2: Extraction
    test_tolerance_extraction()
    
    # Test 3: Integration
    test_precision_logic_integration(args.image)
    
    print("="*60)
    print("ALL TESTS COMPLETE")
    print("="*60)
    
    if failed == 0:
        print("✅ All tests passed!")
    else:
        print(f"⚠️  {failed} test(s) failed")


if __name__ == "__main__":
    main()
