"""Build script for creating MSI installer. DEPRECATED: Use build_installer.py instead."""
import subprocess
import sys
from pathlib import Path


def build_executable():
    """Build the executable using PyInstaller."""
    print("Building executable with PyInstaller...")
    
    # PyInstaller command
    cmd = [
        "pyinstaller",
        "--name=EverQuestBossTracker",
        "--windowed",
        "--onefile",
        "--icon=icons/tray_icon.ico",
        "--add-data=assets;assets",
        "--add-data=icons;icons",
        "--hidden-import=PyQt6.QtCore",
        "--hidden-import=PyQt6.QtGui",
        "--hidden-import=PyQt6.QtWidgets",
        "src/main.py"
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print("Executable built successfully!")
        print("Output: dist/EverQuestBossTracker.exe")
    except subprocess.CalledProcessError as e:
        print(f"Error building executable: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("PyInstaller not found. Install it with: pip install pyinstaller")
        sys.exit(1)


if __name__ == "__main__":
    build_executable()
    print("\nNext steps:")
    print("1. Test the executable: dist/EverQuestBossTracker.exe")
    print("2. Use WiX Toolset or Inno Setup to create MSI installer")
    print("3. Include assets and icons directories in the installer")
