#!/usr/bin/env python3
"""
Create EC2 deployment package with all necessary files.
Creates: analyez_scraper_pkg.zip
"""
import os
import zipfile
import shutil
from pathlib import Path

# Directories to include (Relative to Project Root)
INCLUDE_DIRS = [
    'data_platform/scrapers',
    'api',  # Include entire API package
    'data_platform/__init__.py',
    'data_platform/analytics', # Include analytics if needed
]

# Files to include (Relative to Project Root)
INCLUDE_FILES_ROOT = [
    'requirements.txt',
    '.env',
]

# Files to include (Relative to Script Directory - deployment/)
INCLUDE_FILES_SCRIPT_DIR = [
    'setup_remote.sh',
    'EC2_DEPLOYMENT_GUIDE.md',
]

# Files/patterns to exclude
EXCLUDE_PATTERNS = [
    '__pycache__',
    '.pyc',
    '.log',
    '.lock',
    'venv',
    '.git',
    '.DS_Store',
    'api/static', # Exclude static files to save space? Keep if needed.
    'api/tests',  # Exclude tests
]

def should_exclude(path: str) -> bool:
    for pattern in EXCLUDE_PATTERNS:
        if pattern in path:
            return True
    return False

def create_package():
    # Helper to resolve paths
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent.parent # Analyez/infrastructure/deployment -> Analyez/
    
    output_file = script_dir / 'analyez_scraper_pkg.zip'
    
    print(f"📂 Project Root: {project_root}")
    print(f"📂 Script Dir: {script_dir}")
    
    # Remove old package
    if output_file.exists():
        output_file.unlink()
    
    with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        print("\n📦 Adding Project Directories...")
        # Add directories from Project Root
        for dir_name in INCLUDE_DIRS:
            full_path = project_root / dir_name
            if not full_path.exists():
                print(f"  ⚠️  Warning: {dir_name} not found!")
                continue
                
            if full_path.is_file():
                 arcname = dir_name
                 zf.write(full_path, arcname)
                 print(f"  + {arcname}")
            else:
                for root, dirs, files in os.walk(full_path):
                    # Filter out excluded directories
                    dirs[:] = [d for d in dirs if not should_exclude(d)]
                    
                    for file in files:
                        file_path = Path(root) / file
                        # Compute relative path from project root to keep structure
                        relative_path = file_path.relative_to(project_root)
                        
                        if not should_exclude(str(relative_path)):
                            zf.write(file_path, relative_path)
                            # print(f"  + {relative_path}") # Commented out to reduce noise
        
        print("\n📄 Adding Root Files...")
        # Add individual files from Project Root
        for file_name in INCLUDE_FILES_ROOT:
            full_path = project_root / file_name
            if full_path.exists():
                zf.write(full_path, file_name)
                print(f"  + {file_name}")
            else:
                print(f"  ⚠️  Warning: {file_name} not found at root!")

        print("\n📄 Adding Deployment Scripts...")
        # Add individual files from Script Dir (placed at root of zip)
        for file_name in INCLUDE_FILES_SCRIPT_DIR:
            full_path = script_dir / file_name
            if full_path.exists():
                zf.write(full_path, file_name)
                print(f"  + {file_name}")
            else:
                 print(f"  ⚠️  Warning: {file_name} not found in script dir!")
    
    size_mb = output_file.stat().st_size / (1024 * 1024)
    print(f"\n✅ Created: {output_file.name}")
    print(f"   Size: {size_mb:.2f} MB")
    print(f"\n📤 Upload with deploy.sh")

if __name__ == "__main__":
    print("Creating Analyez EC2 deployment package...\n")
    create_package()
