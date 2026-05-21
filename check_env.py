import os

# Check if the ANAGRAM_FILE_PATH environment variable is set
anagram_path = os.environ.get('ANAGRAM_FILE_PATH')

print("=== Environment Variable Check ===")
print(f"ANAGRAM_FILE_PATH = {anagram_path}")

if anagram_path:
    print(f"File exists: {os.path.exists(anagram_path)}")
    if os.path.exists(anagram_path):
        try:
            with open(anagram_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            print(f"File contains {len(lines)} lines")
            print("First 3 lines:")
            for i, line in enumerate(lines[:3]):
                print(f"  {i+1}: {repr(line.strip())}")
        except Exception as e:
            print(f"Error reading file: {e}")
else:
    print("❌ Environment variable not set!")
    print("\nTo set it, run in PowerShell:")
    print('$env:ANAGRAM_FILE_PATH = "C:\\path\\to\\your\\anagram\\file.txt"')
