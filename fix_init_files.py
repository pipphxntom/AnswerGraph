"""
Script to fix invalid UTF-8 bytes in Python files.

This script scans for Python files with encoding issues and corrects them.
"""
import os
import sys
import glob
from pathlib import Path

def fix_file_encoding(file_path):
    """Fix encoding issues in a Python file."""
    try:
        # Try to read the file as binary
        with open(file_path, 'rb') as f:
            content = f.read()
        
        # Replace invalid UTF-8 characters with a placeholder
        try:
            # Try to decode as utf-8, replacing invalid characters
            decoded = content.decode('utf-8', errors='replace')
            
            # Write back the cleaned content
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(decoded)
            
            print(f"✅ Fixed: {file_path}")
            return True
        except Exception as e:
            print(f"❌ Error fixing {file_path}: {str(e)}")
            return False
    except Exception as e:
        print(f"❌ Error reading {file_path}: {str(e)}")
        return False

def fix_init_files():
    """Fix all __init__.py files in the project."""
    # Find all __init__.py files
    init_files = glob.glob("src/**/__init__.py", recursive=True)
    
    fixed = 0
    failed = 0
    
    print(f"Found {len(init_files)} __init__.py files")
    
    for file_path in init_files:
        try:
            # Get file size
            size = os.path.getsize(file_path)
            
            if size == 0:
                # File is empty, which is fine
                print(f"ℹ️ Empty file (OK): {file_path}")
                continue
            
            # Try to read the file
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                # File can be read as utf-8, continue
                print(f"✓ Valid file: {file_path}")
            except UnicodeDecodeError:
                # File has encoding issues, fix it
                if fix_file_encoding(file_path):
                    fixed += 1
                else:
                    failed += 1
                    
                    # If fixing failed, create a new empty file
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write("# Fixed empty __init__.py file\n")
                    print(f"⚠️ Created new empty file: {file_path}")
        except Exception as e:
            print(f"❌ Error processing {file_path}: {str(e)}")
            failed += 1
    
    print(f"\nSummary: Fixed {fixed} files, Failed to fix {failed} files")

if __name__ == "__main__":
    print("Starting to fix __init__.py files with encoding issues...")
    fix_init_files()
    print("Done!")
