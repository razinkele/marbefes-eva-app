#!/usr/bin/env python3
"""
Quick check script to verify deployment package is complete
"""

from pathlib import Path

def check_deployment():
    required_files = [
        "app.py",
        "requirements.txt",
        "www/marbefes.png",
        "www/iecs.png",
        "MARBEFES_EVA-Phase2_template.xlsx"
    ]
    
    print("Checking deployment package...")
    print("-" * 50)
    
    all_ok = True
    for file in required_files:
        path = Path(file)
        if path.exists():
            size = path.stat().st_size
            print(f"✓ {file} ({size:,} bytes)")
        else:
            print(f"✗ {file} - MISSING!")
            all_ok = False
    
    print("-" * 50)
    if all_ok:
        print("✓ All required files present!")
        print("\nReady for deployment!")
    else:
        print("✗ Some files are missing!")
        print("\nPlease check your package.")
    
    return all_ok

if __name__ == "__main__":
    check_deployment()
