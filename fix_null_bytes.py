import os
import sys

def check_file_for_null_bytes(file_path):
    try:
        with open(file_path, 'rb') as f:
            content = f.read()
            if b'\x00' in content:
                null_positions = [i for i, byte in enumerate(content) if byte == 0]
                return True, null_positions
            return False, []
    except Exception as e:
        return False, f"Error reading file: {str(e)}"

def scan_directory(directory):
    print(f"Scanning directory: {directory}")
    null_byte_files = []
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                has_null, positions = check_file_for_null_bytes(file_path)
                if has_null:
                    relative_path = os.path.relpath(file_path, directory)
                    null_byte_files.append((relative_path, positions))
                    print(f"Found null bytes in: {relative_path} at positions: {positions[:10]}{'...' if len(positions) > 10 else ''}")
    
    return null_byte_files

def clean_null_bytes(file_path):
    try:
        with open(file_path, 'rb') as f:
            content = f.read()
        
        # Remove null bytes
        cleaned = content.replace(b'\x00', b'')
        
        # Write back to file
        with open(file_path, 'wb') as f:
            f.write(cleaned)
            
        return True
    except Exception as e:
        print(f"Error cleaning file {file_path}: {str(e)}")
        return False

if __name__ == "__main__":
    directory = os.path.dirname(os.path.abspath(__file__))
    null_byte_files = scan_directory(directory)
    
    if null_byte_files:
        print(f"\nFound {len(null_byte_files)} files with null bytes.")
        clean = input("Do you want to clean these files? (y/n): ").lower().strip()
        
        if clean == 'y':
            cleaned_count = 0
            for rel_path, _ in null_byte_files:
                abs_path = os.path.join(directory, rel_path)
                if clean_null_bytes(abs_path):
                    cleaned_count += 1
                    print(f"Cleaned: {rel_path}")
            
            print(f"\nCleaned {cleaned_count} out of {len(null_byte_files)} files.")
        else:
            print("No files were cleaned.")
    else:
        print("No files with null bytes found.")
