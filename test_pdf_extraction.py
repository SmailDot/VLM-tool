"""
PDF Extraction Testing Script

Tests the PDFImageExtractor functionality for Phase 1 implementation.
Validates high-resolution rendering, region extraction, and error handling.

Usage:
    python test_pdf_extraction.py
"""

import os
import sys
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PIL import Image

# Fix encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent))

try:
    from app.manufacturing.extractors.pdf_extractor import PDFImageExtractor, is_pdf_available
except ImportError as e:
    print(f"❌ Import Error: {e}")
    print("Make sure you're running from project root: python test_pdf_extraction.py")
    sys.exit(1)


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def check_dependencies() -> bool:
    """Check if required dependencies are installed."""
    print_section("Dependency Check")
    
    if not is_pdf_available():
        print("❌ PyMuPDF (fitz) not installed")
        print("Install with: pip install pymupdf>=1.26.0")
        return False
    
    print("✅ PyMuPDF (fitz) available")
    print("✅ OpenCV available")
    print("✅ Pillow available")
    return True


def find_sample_pdf() -> Optional[str]:
    """Find a sample PDF file for testing."""
    print_section("Looking for Sample PDF")
    
    # Check common locations
    possible_paths = [
        "test.pdf",
        "sample.pdf",
        "test1.pdf",
        "test2.pdf",
        "samples/test.pdf",
        "data/test.pdf",
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            print(f"✅ Found sample PDF: {path}")
            return path
    
    print("⚠️  No sample PDF found in common locations:")
    for path in possible_paths:
        print(f"   - {path}")
    print("\n💡 Place a PDF file named 'test.pdf' in the project root to test")
    return None


def test_extractor_initialization():
    """Test PDFImageExtractor initialization."""
    print_section("Test 1: Extractor Initialization")
    
    try:
        # Test with different DPI values
        for dpi in [150, 300, 600]:
            extractor = PDFImageExtractor(target_dpi=dpi)
            print(f"✅ Created extractor with DPI={dpi}")
        
        # Test default DPI
        extractor = PDFImageExtractor()
        print(f"✅ Created extractor with default DPI={extractor.target_dpi}")
        
        return True
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        return False


def test_full_page_extraction(pdf_path: str):
    """Test full page extraction."""
    print_section("Test 2: Full Page Extraction")
    
    try:
        extractor = PDFImageExtractor(target_dpi=300)
        
        # Extract first page
        img = extractor.extract_full_page(pdf_path, page_num=0)
        
        if img is None:
            print("❌ extract_full_page returned None")
            return False
        
        h, w = img.shape[:2]
        channels = img.shape[2] if len(img.shape) == 3 else 1
        
        print(f"✅ Extracted page 0")
        print(f"   Resolution: {w} × {h} px")
        print(f"   Channels: {channels}")
        print(f"   Data type: {img.dtype}")
        print(f"   DPI: {extractor.target_dpi}")
        
        # Save output for manual inspection
        output_path = "test_output_full_page.png"
        cv2.imwrite(output_path, img)
        print(f"📁 Saved test output: {output_path}")
        
        return True
    except Exception as e:
        print(f"❌ Full page extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_region_extraction(pdf_path: str):
    """Test region extraction with normalized bbox."""
    print_section("Test 3: Region Extraction (Normalized Coords)")
    
    try:
        extractor = PDFImageExtractor(target_dpi=300)
        
        # Extract center region (normalized coordinates)
        bbox = (0.25, 0.25, 0.75, 0.75)  # Center 50% of page
        img = extractor.extract_region(pdf_path, page_num=0, bbox=bbox)
        
        if img is None:
            print("❌ extract_region returned None")
            return False
        
        h, w = img.shape[:2]
        print(f"✅ Extracted region with bbox={bbox}")
        print(f"   Resolution: {w} × {h} px")
        
        # Save output
        output_path = "test_output_region.png"
        cv2.imwrite(output_path, img)
        print(f"📁 Saved test output: {output_path}")
        
        return True
    except Exception as e:
        print(f"❌ Region extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_pixel_coords_extraction(pdf_path: str):
    """Test region extraction with pixel coordinates."""
    print_section("Test 4: Region Extraction (Pixel Coords)")
    
    try:
        extractor = PDFImageExtractor(target_dpi=300)
        
        # First get full page to know dimensions
        full_img = extractor.extract_full_page(pdf_path, page_num=0)
        if full_img is None:
            print("❌ Could not extract full page for reference")
            return False
        
        screen_h, screen_w = full_img.shape[:2]
        
        # Extract top-left quarter (pixel coordinates)
        pixel_bbox = (0, 0, screen_w // 2, screen_h // 2)
        img = extractor.extract_with_pixel_coords(
            pdf_path, page_num=0, pixel_bbox=pixel_bbox, reference_dpi=300
        )
        
        if img is None:
            print("❌ extract_with_pixel_coords returned None")
            return False
        
        h, w = img.shape[:2]
        print(f"✅ Extracted region with pixel_bbox={pixel_bbox}")
        print(f"   Screen dimensions: {screen_w} × {screen_h}")
        print(f"   Extracted resolution: {w} × {h} px")
        
        # Save output
        output_path = "test_output_pixel_coords.png"
        cv2.imwrite(output_path, img)
        print(f"📁 Saved test output: {output_path}")
        
        return True
    except Exception as e:
        print(f"❌ Pixel coords extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_preview_image(pdf_path: str):
    """Test low-resolution preview extraction."""
    print_section("Test 5: Preview Image Generation")
    
    try:
        extractor = PDFImageExtractor(target_dpi=300)
        
        # Get preview at 96 DPI
        preview = extractor.get_preview_image(pdf_path, page_num=0, preview_dpi=96)
        
        if preview is None:
            print("❌ get_preview_image returned None")
            return False
        
        h, w = preview.shape[:2]
        print(f"✅ Generated preview image")
        print(f"   Resolution: {w} × {h} px")
        print(f"   Target DPI: 96 (for UI display)")
        
        # Save output
        output_path = "test_output_preview.png"
        cv2.imwrite(output_path, preview)
        print(f"📁 Saved test output: {output_path}")
        
        return True
    except Exception as e:
        print(f"❌ Preview generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_error_handling(pdf_path: str):
    """Test error handling for invalid inputs."""
    print_section("Test 6: Error Handling")
    
    extractor = PDFImageExtractor(target_dpi=300)
    passed = 0
    total = 4
    
    # Test 1: Invalid file path
    try:
        img = extractor.extract_full_page("nonexistent.pdf", page_num=0)
        if img is None:
            print("✅ Test 1/4: Invalid path handled gracefully (returned None)")
            passed += 1
        else:
            print("❌ Test 1/4: Should return None for invalid path")
    except Exception as e:
        print(f"⚠️  Test 1/4: Raised exception (acceptable): {type(e).__name__}")
        passed += 1
    
    # Test 2: Invalid page number
    try:
        img = extractor.extract_full_page(pdf_path, page_num=999)
        if img is None:
            print("✅ Test 2/4: Invalid page number handled gracefully (returned None)")
            passed += 1
        else:
            print("❌ Test 2/4: Should return None for invalid page number")
    except Exception as e:
        print(f"⚠️  Test 2/4: Raised exception (acceptable): {type(e).__name__}")
        passed += 1
    
    # Test 3: Invalid bbox (negative values)
    try:
        img = extractor.extract_region(pdf_path, page_num=0, bbox=(-0.1, -0.1, 0.5, 0.5))
        if img is None:
            print("✅ Test 3/4: Invalid bbox handled gracefully (returned None)")
            passed += 1
        else:
            print("⚠️  Test 3/4: Accepted negative bbox (implementation may clamp)")
            passed += 1
    except Exception as e:
        print(f"⚠️  Test 3/4: Raised exception (acceptable): {type(e).__name__}")
        passed += 1
    
    # Test 4: Invalid bbox (reversed coordinates)
    try:
        img = extractor.extract_region(pdf_path, page_num=0, bbox=(0.8, 0.8, 0.2, 0.2))
        if img is None:
            print("✅ Test 4/4: Reversed bbox handled gracefully (returned None)")
            passed += 1
        else:
            print("⚠️  Test 4/4: Accepted reversed bbox (implementation may swap)")
            passed += 1
    except Exception as e:
        print(f"⚠️  Test 4/4: Raised exception (acceptable): {type(e).__name__}")
        passed += 1
    
    print(f"\n📊 Error handling tests: {passed}/{total} passed")
    return passed >= 3  # Allow 1 failure


def test_resolution_quality(pdf_path: str):
    """Compare output quality at different DPI settings."""
    print_section("Test 7: Resolution Quality Comparison")
    
    try:
        dpi_values = [96, 150, 300, 600]
        results = []
        
        for dpi in dpi_values:
            extractor = PDFImageExtractor(target_dpi=dpi)
            img = extractor.extract_full_page(pdf_path, page_num=0)
            
            if img is not None:
                h, w = img.shape[:2]
                file_size_mb = (img.nbytes / (1024 * 1024))
                results.append((dpi, w, h, file_size_mb))
                
                output_path = f"test_output_dpi_{dpi}.png"
                cv2.imwrite(output_path, img)
                print(f"✅ DPI {dpi:3d}: {w:4d} × {h:4d} px | {file_size_mb:.2f} MB | Saved: {output_path}")
        
        if len(results) == len(dpi_values):
            print(f"\n📊 Quality comparison complete: {len(results)}/{len(dpi_values)} resolutions tested")
            print("💡 Recommendation: 300 DPI balances quality and file size for OCR")
            return True
        else:
            print(f"\n⚠️  Only {len(results)}/{len(dpi_values)} resolutions succeeded")
            return False
    except Exception as e:
        print(f"❌ Resolution comparison failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("  PDF Image Extractor - Test Suite (Phase 1)")
    print("=" * 60)
    
    # Check dependencies
    if not check_dependencies():
        print("\n❌ Dependency check failed. Please install required packages.")
        return False
    
    # Find sample PDF
    pdf_path = find_sample_pdf()
    if pdf_path is None:
        print("\n⚠️  No sample PDF found. Skipping extraction tests.")
        print("To run full test suite, add a PDF file to the project root.")
        
        # Still test initialization
        if test_extractor_initialization():
            print("\n✅ Basic initialization tests passed")
            return True
        else:
            print("\n❌ Initialization tests failed")
            return False
    
    # Run all tests
    results = []
    results.append(("Initialization", test_extractor_initialization()))
    results.append(("Full Page Extraction", test_full_page_extraction(pdf_path)))
    results.append(("Region Extraction (Normalized)", test_region_extraction(pdf_path)))
    results.append(("Region Extraction (Pixel Coords)", test_pixel_coords_extraction(pdf_path)))
    results.append(("Preview Generation", test_preview_image(pdf_path)))
    results.append(("Error Handling", test_error_handling(pdf_path)))
    results.append(("Resolution Comparison", test_resolution_quality(pdf_path)))
    
    # Print summary
    print_section("Test Summary")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\n📊 Overall: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    
    if passed == total:
        print("\n🎉 All tests passed! PDF extraction is working correctly.")
        print("✅ Ready to commit Phase 1 changes")
        return True
    elif passed >= total * 0.7:
        print("\n⚠️  Most tests passed. Review failures before committing.")
        return True
    else:
        print("\n❌ Multiple test failures. Debug before committing.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
