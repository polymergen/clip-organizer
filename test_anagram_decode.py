#!/usr/bin/env python3
"""
Test script for anagram filename decoding functionality.
"""

import sys
import os

def decode_anagram_filename(filename):
    """
    Simple anagram decoder for filenames.
    This should contain the core anagram mapping logic.
    """
    # Remove file extension for processing
    name_without_ext = os.path.splitext(filename)[0]
    extension = os.path.splitext(filename)[1]
    
    # Common anagram mappings (you may need to adjust these based on your specific anagram system)
    anagram_mappings = {
        'BocbkoSu': 'BoobSuck',
        'Colgwir': 'Cowgirl', 
        'Miaysrson': 'Missionary',
        'sFoitaradAntMneoyurplab': 'ForeplayAndMasturbation',
        'dooniiotgsgyP': 'DoggyPosition',
        'iSinyhBOeresddwa': 'SidewaysAndBentOver',
        'sortefco': 'Softcore',
        'Trsah': 'Trash',
        'dStnlHOerngadi': 'StandingOrHeld',
        'iSiogtenrstIntin': 'SittingInsertion',
        'OPoVfPwi-enVitO': 'PointOfView-POV',
        'StiernoyL': 'StoryLine',
    }
    
    # Try to find exact matches first
    for anagram, decoded in anagram_mappings.items():
        if anagram in name_without_ext:
            decoded_name = name_without_ext.replace(anagram, decoded)
            return decoded_name + extension
    
    # If no exact match, try partial matches or return original
    return filename

def test_decode_function():
    """Test the decode function with sample filenames."""
    test_files = [
        "BocbkoSu_video.mp4",
        "test_Miaysrson_image.jpg", 
        "sortefco_video.avi",
        "regular_filename.png",
        "Trsah_file.mp4",
        "dooniiotgsgyP_scene.avi"
    ]
    
    print("Testing anagram decode function:")
    print("-" * 50)
    
    for filename in test_files:
        decoded = decode_anagram_filename(filename)
        print(f"Original: {filename}")
        print(f"Decoded:  {decoded}")
        print(f"Changed:  {'Yes' if decoded != filename else 'No'}")
        print()

if __name__ == "__main__":
    test_decode_function()
