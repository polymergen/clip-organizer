#!/usr/bin/env python3
"""
Debug script to check anagram decoding setup
"""

import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from viewer import decode_anagram_filename

def debug_anagram_setup():
    """Debug the anagram decoding setup"""
    print("=== Anagram Decoding Debug ===")
    
    # Check environment variable
    anagram_file_path = os.environ.get('ANAGRAM_FILE_PATH')
    print(f"ANAGRAM_FILE_PATH environment variable: {anagram_file_path}")
    
    if not anagram_file_path:
        print("❌ ANAGRAM_FILE_PATH environment variable is not set!")
        print("\nTo fix this, you need to set the environment variable. You can:")
        print("1. Set it in PowerShell: $env:ANAGRAM_FILE_PATH = 'C:\\path\\to\\your\\anagram\\file.txt'")
        print("2. Set it in System Environment Variables")
        print("3. Create the anagram file and set the path")
        return False
    
    # Check if file exists
    if not os.path.exists(anagram_file_path):
        print(f"❌ Anagram file does not exist at: {anagram_file_path}")
        print("\nPlease create the anagram file or update the path.")
        return False
    
    print(f"✅ Anagram file found at: {anagram_file_path}")
    
    # Check file contents
    try:
        with open(anagram_file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        print(f"✅ File readable, contains {len(lines)} lines")
        
        # Show first few lines as example
        print("\nFirst few lines of anagram file:")
        for i, line in enumerate(lines[:5]):
            print(f"  {i+1}: {line.strip()}")
        
        if len(lines) > 5:
            print(f"  ... and {len(lines) - 5} more lines")
        
        # Test with some sample filenames
        print("\n=== Testing Anagram Decoding ===")
        
        # Extract some anagrams from the file to test
        test_anagrams = []
        for line in lines[:3]:  # Test first 3 lines
            line = line.strip()
            if ',' in line:
                parts = line.split(',', 1)
                if len(parts) == 2:
                    original, anagram = parts[0].strip(), parts[1].strip()
                    test_anagrams.append((original, anagram))
        
        if test_anagrams:
            for original, anagram in test_anagrams:
                test_filename = f"{anagram}.mp4"
                decoded = decode_anagram_filename(test_filename)
                expected = f"{original}.mp4"
                
                print(f"Original: {original}")
                print(f"Anagram:  {anagram}")
                print(f"Test filename: {test_filename}")
                print(f"Decoded: {decoded}")
                print(f"Expected: {expected}")
                print(f"Match: {'✅' if decoded == expected else '❌'}")
                print()
        else:
            print("❌ No valid anagram pairs found in file")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error reading anagram file: {e}")
        return False

def suggest_setup():
    """Suggest how to set up the anagram system"""
    print("\n=== Setup Instructions ===")
    print("To set up anagram decoding:")
    print()
    print("1. Create an anagram mapping file (e.g., anagram_mappings.txt)")
    print("   Format: original_name,anagram_name (one per line)")
    print("   Example content:")
    print("   BoobSuck,BocbkoSu")
    print("   Cowgirl,Colgwir")
    print("   Missionary,Miaysrson")
    print()
    print("2. Set the environment variable:")
    print("   In PowerShell: $env:ANAGRAM_FILE_PATH = 'C:\\path\\to\\anagram_mappings.txt'")
    print("   Or add to your PowerShell profile for permanent setup")
    print()
    print("3. Test with this debug script")

if __name__ == "__main__":
    success = debug_anagram_setup()
    
    if not success:
        suggest_setup()
    else:
        print("🎉 Anagram decoding setup looks good!")
        print("\nIf you're still not seeing decoded filenames in the viewer,")
        print("make sure your actual filenames match the anagrams in your file.")
