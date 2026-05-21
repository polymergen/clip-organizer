#!/usr/bin/env python3
"""
Test script to verify the complete functionality:
1. Database caching with compression
2. Anagram filename decoding with file-based lookup
"""

import os
import sys
import tempfile
import sqlite3

# Add the current directory to Python path so we can import from viewer modules
sys.path.insert(0, os.path.dirname(__file__))

from viewer import decode_anagram_filename, ScreencapDatabase, pixmap_to_base64_compressed, base64_to_pixmap
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPixmap

def test_anagram_decoding():
    """Test the anagram decoding functionality."""
    print("=== Testing Anagram Decoding ===")
    
    # Create a temporary anagram file for testing
    test_anagram_content = """BoobSuck,BocbkoSu
Cowgirl,Colgwir
Missionary,Miaysrson
ForeplayAndMasturbation,sFoitaradAntMneoyurplab
DoggyPosition,dooniiotgsgyP
SidewaysAndBentOver,iSinyhBOeresddwa
Softcore,sortefco
Trash,Trsah
StandingOrHeld,dStnlHOerngadi
SittingInsertion,iSiogtenrstIntin
PointOfView-POV,OPoVfPwi-enVitO
StoryLine,StiernoyL"""
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as temp_file:
        temp_file.write(test_anagram_content)
        temp_anagram_file = temp_file.name
    
    # Set the environment variable
    original_anagram_path = os.environ.get('ANAGRAM_FILE_PATH')
    os.environ['ANAGRAM_FILE_PATH'] = temp_anagram_file
    
    try:
        # Test cases
        test_cases = [
            ("BocbkoSu_video.mp4", "BoobSuck_video.mp4"),
            ("test_Miaysrson_scene.avi", "test_Missionary_scene.avi"),
            ("sortefco_content.jpg", "Softcore_content.jpg"),
            ("regular_filename.png", "regular_filename.png"),  # Should remain unchanged
            ("Trsah_old_file.mov", "Trash_old_file.mov"),
            ("dooniiotgsgyP_position.mkv", "DoggyPosition_position.mkv")
        ]
        
        print("Testing anagram decoding:")
        print("-" * 50)
        
        all_passed = True
        for original, expected in test_cases:
            decoded = decode_anagram_filename(original)
            passed = decoded == expected
            all_passed = all_passed and passed
            
            print(f"Original:  {original}")
            print(f"Expected:  {expected}")
            print(f"Decoded:   {decoded}")
            print(f"Status:    {'✓ PASS' if passed else '✗ FAIL'}")
            print()
        
        print(f"Overall result: {'✓ ALL TESTS PASSED' if all_passed else '✗ SOME TESTS FAILED'}")
        return all_passed
        
    finally:
        # Clean up
        os.unlink(temp_anagram_file)
        if original_anagram_path is not None:
            os.environ['ANAGRAM_FILE_PATH'] = original_anagram_path
        elif 'ANAGRAM_FILE_PATH' in os.environ:
            del os.environ['ANAGRAM_FILE_PATH']

def test_database_functionality():
    """Test the database caching and compression functionality."""
    print("\n=== Testing Database Functionality ===")
    
    # Create a QApplication instance for QPixmap operations
    app = QApplication([])
    
    # Create a temporary database
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as temp_db:
        temp_db_path = temp_db.name
    
    try:
        # Initialize database
        db = ScreencapDatabase(temp_db_path)
        
        # Create a test pixmap (simple colored rectangle)
        test_pixmap = QPixmap(800, 600)
        test_pixmap.fill(0xFF0000)  # Red color
        
        # Test compression
        print("Testing image compression...")
        compressed_data = pixmap_to_base64_compressed(test_pixmap)
        print(f"Compressed data length: {len(compressed_data)} characters")
        
        # Test decompression
        decompressed_pixmap = base64_to_pixmap(compressed_data)
        print(f"Original size: {test_pixmap.width()}x{test_pixmap.height()}")
        print(f"Decompressed size: {decompressed_pixmap.width()}x{decompressed_pixmap.height()}")
        
        # Test database storage and retrieval
        test_file_path = "/test/path/video.mp4"
        print(f"\nTesting database storage...")
        
        # Save to database
        db.save_screencap(test_file_path, compressed_data)
        print("✓ Saved screencap to database")
        
        # Retrieve from database
        retrieved_data = db.get_screencap(test_file_path)
        if retrieved_data == compressed_data:
            print("✓ Successfully retrieved screencap from database")
            print("✓ Data integrity verified")
        else:
            print("✗ Data integrity check failed")
            return False
        
        # Test database size calculation
        db_size = db.get_database_size()
        print(f"Database size: {db_size:.4f} MB")
        
        # Test cleanup function (though no old entries exist yet)
        deleted = db.cleanup_old_entries(30)
        print(f"Cleanup removed {deleted} old entries")
        
        print("✓ ALL DATABASE TESTS PASSED")
        return True
        
    finally:
        # Clean up
        try:
            os.unlink(temp_db_path)
        except:
            pass

def main():
    """Run all tests."""
    print("ClipOrganizer Complete Functionality Test")
    print("=" * 50)
    
    anagram_success = test_anagram_decoding()
    db_success = test_database_functionality()
    
    print("\n" + "=" * 50)
    print("FINAL RESULTS:")
    print(f"Anagram Decoding: {'✓ PASS' if anagram_success else '✗ FAIL'}")
    print(f"Database Caching: {'✓ PASS' if db_success else '✗ FAIL'}")
    
    if anagram_success and db_success:
        print("\n🎉 ALL FUNCTIONALITY TESTS PASSED!")
        print("\nYour ClipOrganizer is ready with:")
        print("- Database caching with compression")
        print("- Anagram filename decoding from file lookup")
        print("- Decoded filename display under images")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main())
