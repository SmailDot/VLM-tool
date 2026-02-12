"""
Test script for image deduplication functionality.

Tests:
1. Image hash computation
2. Hamming distance calculation
3. Similar image detection
4. Duplicate detection workflow
5. Database cleanup
"""

import cv2
import numpy as np
from pathlib import Path
import shutil
import tempfile

from app.knowledge.manager import KnowledgeBaseManager


def create_test_image(color=(255, 255, 255), size=(100, 100), pattern="solid"):
    """
    Create a test image with different patterns.
    
    Args:
        color: RGB color tuple
        size: (width, height)
        pattern: "solid", "gradient", "checkerboard"
    """
    img = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    
    if pattern == "solid":
        img[:] = color
    elif pattern == "gradient":
        for i in range(size[1]):
            intensity = int((i / size[1]) * color[0])
            img[i, :] = (intensity, intensity, intensity)
    elif pattern == "checkerboard":
        cell_size = 10
        for i in range(0, size[1], cell_size):
            for j in range(0, size[0], cell_size):
                if (i // cell_size + j // cell_size) % 2 == 0:
                    img[i:i+cell_size, j:j+cell_size] = color
    
    return img


def test_image_hash():
    """Test image hash computation."""
    print("\n=== Test 1: Image Hash Computation ===")
    
    # Create temporary test images with different patterns
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp1:
        img1 = create_test_image((255, 255, 255), pattern="gradient")  # White gradient
        cv2.imwrite(tmp1.name, img1)
        tmp1_path = tmp1.name
    
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp2:
        img2 = create_test_image((255, 255, 255), pattern="gradient")  # Same gradient
        cv2.imwrite(tmp2.name, img2)
        tmp2_path = tmp2.name
    
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp3:
        img3 = create_test_image((255, 255, 255), pattern="checkerboard")  # Different pattern
        cv2.imwrite(tmp3.name, img3)
        tmp3_path = tmp3.name
    
    kb_manager = KnowledgeBaseManager()
    
    hash1 = kb_manager._compute_image_hash(tmp1_path)
    hash2 = kb_manager._compute_image_hash(tmp2_path)
    hash3 = kb_manager._compute_image_hash(tmp3_path)
    
    print(f"Hash 1 (gradient):      {hash1}")
    print(f"Hash 2 (gradient):      {hash2}")
    print(f"Hash 3 (checkerboard):  {hash3}")
    
    assert hash1 == hash2, "Identical images should have same hash"
    assert hash1 != hash3, "Different images should have different hashes"
    
    # Cleanup
    Path(tmp1_path).unlink()
    Path(tmp2_path).unlink()
    Path(tmp3_path).unlink()
    
    print("[PASS] Image hash computation test passed")


def test_hamming_distance():
    """Test Hamming distance calculation."""
    print("\n=== Test 2: Hamming Distance ===")
    
    kb_manager = KnowledgeBaseManager()
    
    # Test cases
    hash1 = "0000000000000000"  # 64 zeros in binary
    hash2 = "0000000000000001"  # 1 bit difference
    hash3 = "000000000000000f"  # 4 bits difference (0xF = 1111)
    hash4 = "ffffffffffffffff"  # All ones (64 bits difference)
    
    dist_0 = kb_manager._hamming_distance(hash1, hash1)
    dist_1 = kb_manager._hamming_distance(hash1, hash2)
    dist_4 = kb_manager._hamming_distance(hash1, hash3)
    dist_64 = kb_manager._hamming_distance(hash1, hash4)
    
    print(f"Distance (same):      {dist_0} (expected: 0)")
    print(f"Distance (1 bit):     {dist_1} (expected: 1)")
    print(f"Distance (4 bits):    {dist_4} (expected: 4)")
    print(f"Distance (64 bits):   {dist_64} (expected: 64)")
    
    assert dist_0 == 0, "Same hashes should have distance 0"
    assert dist_1 == 1, "1 bit difference should have distance 1"
    assert dist_4 == 4, "4 bits difference should have distance 4"
    assert dist_64 == 64, "All bits different should have distance 64"
    
    print("[PASS] Hamming distance test passed")


def test_duplicate_detection():
    """Test duplicate detection workflow."""
    print("\n=== Test 3: Duplicate Detection Workflow ===")
    
    # Create temporary database directory
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        db_path = tmpdir_path / "test_kb.json"
        img_dir = tmpdir_path / "test_images"
        
        kb_manager = KnowledgeBaseManager(
            db_path=str(db_path),
            image_storage_dir=str(img_dir)
        )
        
        # Create test images
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp1:
            img1 = create_test_image((255, 0, 0))
            cv2.imwrite(tmp1.name, img1)
            tmp1_path = tmp1.name
        
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp2:
            img2 = create_test_image((255, 0, 0))  # Identical
            cv2.imwrite(tmp2.name, img2)
            tmp2_path = tmp2.name
        
        # Add first entry (should succeed)
        print("\nAdding first entry...")
        result1 = kb_manager.add_entry(
            image_path=tmp1_path,
            features={"shape_description": "Test shape 1"},
            correct_processes=["I01"],
            reasoning="Test reasoning 1"
        )
        
        print(f"Result 1 status: {result1.get('status')}")
        assert result1.get("status") == "ok", "First entry should succeed"
        
        # Add duplicate entry (should detect)
        print("\nAdding duplicate entry...")
        result2 = kb_manager.add_entry(
            image_path=tmp2_path,
            features={"shape_description": "Test shape 2"},
            correct_processes=["J01"],
            reasoning="Test reasoning 2"
        )
        
        print(f"Result 2 status: {result2.get('status')}")
        assert result2.get("status") == "duplicate_found", "Should detect duplicate"
        
        similar = result2.get("similar", [])
        print(f"Found {len(similar)} similar entries")
        
        assert len(similar) > 0, "Should find at least one similar entry"
        
        # Check similarity percentage
        similarity = similar[0]["similarity_percent"]
        print(f"Similarity: {similarity}%")
        assert similarity > 90, "Identical images should have >90% similarity"
        
        # Cleanup
        Path(tmp1_path).unlink()
        Path(tmp2_path).unlink()
    
    print("[PASS] Duplicate detection test passed")


def test_cleanup_invalid_entries():
    """Test database cleanup for missing image files."""
    print("\n=== Test 4: Database Cleanup ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        db_path = tmpdir_path / "test_kb.json"
        img_dir = tmpdir_path / "test_images"
        
        kb_manager = KnowledgeBaseManager(
            db_path=str(db_path),
            image_storage_dir=str(img_dir)
        )
        
        # Create test image
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            img = create_test_image((255, 0, 0))
            cv2.imwrite(tmp.name, img)
            tmp_path = tmp.name
        
        # Add entry
        result = kb_manager.add_entry(
            image_path=tmp_path,
            features={"shape_description": "Test shape"},
            correct_processes=["I01"],
            reasoning="Test reasoning",
            similarity_threshold=-1  # Disable duplicate check
        )
        
        print(f"Added entry: {result.get('entry', {}).get('id')}")
        print(f"DB size before cleanup: {len(kb_manager.db)}")
        
        # Delete the stored image file to simulate missing file
        stored_image_path = result.get("entry", {}).get("image_rel_path")
        if stored_image_path and Path(stored_image_path).exists():
            Path(stored_image_path).unlink()
            print(f"Deleted stored image: {stored_image_path}")
        
        # Run cleanup
        removed = kb_manager._cleanup_invalid_entries()
        print(f"Removed {removed} invalid entries")
        print(f"DB size after cleanup: {len(kb_manager.db)}")
        
        assert removed == 1, "Should remove 1 invalid entry"
        assert len(kb_manager.db) == 0, "DB should be empty after cleanup"
        
        # Cleanup
        Path(tmp_path).unlink()
    
    print("[PASS] Database cleanup test passed")


if __name__ == "__main__":
    print("Starting image deduplication tests...")
    
    try:
        test_image_hash()
        test_hamming_distance()
        test_duplicate_detection()
        test_cleanup_invalid_entries()
        
        print("\n" + "="*50)
        print("[PASS] All tests passed!")
        print("="*50)
    
    except AssertionError as e:
        print(f"\n[FAIL] Test failed: {e}")
    except Exception as e:
        print(f"\n[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()
