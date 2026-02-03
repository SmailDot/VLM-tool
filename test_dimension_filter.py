"""
Test script for dimension line filtering functionality.

Tests:
1. Load engineering drawing with dimension lines
2. Extract geometry with and without OCR filtering
3. Visualize before/after comparison
4. Validate filtering effectiveness
"""

import cv2
import numpy as np
from pathlib import Path
import sys

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.manufacturing.extractors.geometry import GeometryExtractor
from app.manufacturing.extractors.ocr import OCRExtractor


def test_dimension_filtering(image_path: str):
    """
    Test dimension line filtering on a sample drawing.
    
    Args:
        image_path: Path to engineering drawing image
    """
    print(f"Testing dimension line filtering on: {image_path}")
    print("=" * 60)
    
    # Load image
    if not Path(image_path).exists():
        print(f"❌ Error: Image not found: {image_path}")
        return
    
    image = cv2.imread(image_path)
    if image is None:
        print(f"❌ Error: Failed to load image: {image_path}")
        return
    
    print(f"✅ Image loaded: {image.shape}")
    
    # Initialize extractors
    geometry_extractor = GeometryExtractor(
        line_threshold=100,
        min_line_length=50,
        max_line_gap=10
    )
    ocr_extractor = OCRExtractor()
    
    # Test 1: Extract without OCR filtering (baseline)
    print("\n[Test 1] Extracting geometry WITHOUT OCR filtering...")
    features_without_filter = geometry_extractor.extract(image, ocr_results=None)
    
    print(f"  Lines detected: {len(features_without_filter.lines)}")
    print(f"  Bend lines detected: {len(features_without_filter.bend_lines)}")
    print(f"  Circles detected: {len(features_without_filter.circles)}")
    print(f"  Holes detected: {len(features_without_filter.holes)}")
    
    # Test 2: Extract OCR results
    print("\n[Test 2] Extracting OCR text...")
    try:
        ocr_results = ocr_extractor.extract(image, threshold=0.5)
        print(f"  OCR texts detected: {len(ocr_results)}")
        
        # Show sample OCR results
        dimension_keywords = ['±', 'φ', 'Φ', 'R', 'r', 'M', '°']
        dimension_texts = [
            ocr.text for ocr in ocr_results 
            if any(kw in ocr.text for kw in dimension_keywords) or ocr.text.replace('.', '').isdigit()
        ]
        print(f"  Dimension-related texts: {len(dimension_texts)}")
        if dimension_texts[:5]:
            print(f"  Sample: {dimension_texts[:5]}")
    except Exception as e:
        print(f"  ⚠️  OCR failed: {e}")
        print("  Note: OCR requires PaddlePaddle. Continuing without OCR...")
        ocr_results = []
    
    # Test 3: Extract with OCR filtering
    print("\n[Test 3] Extracting geometry WITH OCR filtering...")
    features_with_filter = geometry_extractor.extract(image, ocr_results=ocr_results)
    
    print(f"  Lines detected: {len(features_with_filter.lines)}")
    print(f"  Bend lines detected: {len(features_with_filter.bend_lines)}")
    print(f"  Circles detected: {len(features_with_filter.circles)}")
    print(f"  Holes detected: {len(features_with_filter.holes)}")
    
    # Compare results
    print("\n[Comparison]")
    lines_filtered = len(features_without_filter.lines) - len(features_with_filter.lines)
    print(f"  Lines filtered out: {lines_filtered}")
    
    if lines_filtered > 0:
        reduction_pct = (lines_filtered / len(features_without_filter.lines)) * 100
        print(f"  Reduction: {reduction_pct:.1f}%")
        print(f"  ✅ Filtering is working!")
    else:
        print(f"  ⚠️  No lines filtered (may not have dimension lines, or OCR failed)")
    
    # Visualize results
    print("\n[Visualization]")
    
    # Create side-by-side comparison
    vis_without = geometry_extractor.visualize(image, features_without_filter)
    vis_with = geometry_extractor.visualize(image, features_with_filter)
    
    # Resize for display if too large
    max_height = 800
    if vis_without.shape[0] > max_height:
        scale = max_height / vis_without.shape[0]
        new_width = int(vis_without.shape[1] * scale)
        vis_without = cv2.resize(vis_without, (new_width, max_height))
        vis_with = cv2.resize(vis_with, (new_width, max_height))
    
    # Stack horizontally
    comparison = np.hstack([vis_without, vis_with])
    
    # Add labels
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(comparison, "WITHOUT OCR FILTER", (10, 30), font, 1, (0, 0, 255), 2)
    cv2.putText(comparison, "WITH OCR FILTER", (vis_without.shape[1] + 10, 30), font, 1, (0, 255, 0), 2)
    
    # Save comparison image
    output_path = Path(image_path).parent / f"dimension_filter_comparison_{Path(image_path).stem}.jpg"
    cv2.imwrite(str(output_path), comparison)
    print(f"  Saved comparison image: {output_path}")
    
    # Display (optional)
    print("\n  Press any key to close visualization window...")
    cv2.imshow("Dimension Line Filtering Comparison", comparison)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    
    print("\n" + "=" * 60)
    print("✅ Test complete!")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test dimension line filtering")
    parser.add_argument(
        "image",
        nargs="?",
        default="test1.jpg",
        help="Path to engineering drawing image (default: test1.jpg)"
    )
    
    args = parser.parse_args()
    
    # Check if default test images exist
    if args.image == "test1.jpg" and not Path("test1.jpg").exists():
        print("⚠️  Default test image 'test1.jpg' not found.")
        print("Please provide an image path:")
        print("  python test_dimension_filter.py <path_to_image>")
        print("\nExample:")
        print("  python test_dimension_filter.py sample_drawing.jpg")
        return
    
    test_dimension_filtering(args.image)


if __name__ == "__main__":
    main()
