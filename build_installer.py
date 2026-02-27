"""Build script for creating Windows installer with Inno Setup."""
import subprocess
import sys
import os
from pathlib import Path


def get_version():
    """
    Get version number from various sources.
    
    Priority:
    1. Environment variable VERSION
    2. Git tag (if in git repository)
    3. version.txt file
    4. Default: 1.0.0
    
    Returns:
        Version string (e.g., "1.0.0")
    """
    # Check environment variable
    version = os.getenv('VERSION')
    if version:
        # Remove 'v' prefix if present
        return version.lstrip('v')
    
    # Try to get from git tag
    try:
        result = subprocess.run(
            ['git', 'describe', '--tags', '--abbrev=0'],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            # Remove 'v' prefix if present
            return version.lstrip('v')
    except (FileNotFoundError, subprocess.SubprocessError):
        pass
    
    # Try to read from version.txt
    version_file = Path(__file__).parent / 'version.txt'
    if version_file.exists():
        try:
            with open(version_file, 'r', encoding='utf-8') as f:
                version = f.read().strip()
                if version:
                    return version
        except Exception:
            pass
    
    # Default version
    return '1.0.0'


def write_version_file(version: str) -> None:
    """Write version.txt so the built app's About dialog shows the correct version and release date."""
    version_path = Path(__file__).parent / 'version.txt'
    version_path.write_text(version.strip(), encoding='utf-8')
    print(f"  Wrote {version_path} (release date = file mtime)")


def build_executable(version: str):
    """Build the executable using PyInstaller."""
    print("Building executable with PyInstaller...")
    
    # Ensure version.txt exists with build version (for About dialog and bundling)
    write_version_file(version)
    
    # PyInstaller command
    # Using --onedir instead of --onefile to avoid extraction overhead
    # --onedir creates a folder with the executable and dependencies
    # This eliminates the 500-1000MB memory spike during startup
    cmd = [
        "pyinstaller",
        "--name=BossTracker",
        "--windowed",
        "--onedir",  # Changed from --onefile to reduce memory usage
        "--icon=icons/tray_icon.ico",
        "--add-data=assets;assets",
        "--add-data=icons;icons",
        "--add-data=version.txt;.",  # About dialog version and release date (mtime)
        "--add-data=data/bosses.json;data",  # Default boss list for new installs
        "--hidden-import=PyQt6.QtCore",
        "--hidden-import=PyQt6.QtGui",
        "--hidden-import=PyQt6.QtWidgets",
        # Include all src modules
        "--hidden-import=logger",
        "--hidden-import=message_parser",
        "--hidden-import=boss_database",
        "--hidden-import=discord_notifier",
        "--hidden-import=sound_player",
        "--hidden-import=log_monitor",
        "--hidden-import=system_tray",
        "--hidden-import=options_window",
        "--hidden-import=message_editor",
        "--hidden-import=theme_manager",
        "--hidden-import=timestamp_formatter",
        "--hidden-import=activity_database",
        "--hidden-import=activity_log",
        "--hidden-import=main_window",
        "--hidden-import=new_boss_dialog",
        "--hidden-import=security",
        "--hidden-import=os_theme_detector",
        "--hidden-import=zone_group_widget",
        "--hidden-import=discord_checker",
        # Add src to path and collect all modules
        "--paths=src",
        "--collect-all=src",
        "--clean",  # Clean PyInstaller cache
        "src/main.py"
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print("[OK] Executable built successfully!")
        print(f"  Output: dist/BossTracker.exe")
    except subprocess.CalledProcessError as e:
        print(f"[FAIL] Error building executable: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("[FAIL] PyInstaller not found. Install it with: pip install pyinstaller")
        sys.exit(1)


def find_innosetup_compiler():
    """
    Find Inno Setup compiler (ISCC.exe).
    
    Checks common installation locations.
    
    Returns:
        Path to ISCC.exe or None if not found
    """
    # Common installation paths
    paths = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
        r"C:\Program Files\Inno Setup 5\ISCC.exe",
    ]
    
    for path in paths:
        if Path(path).exists():
            return path
    
    # Try to find via PATH
    try:
        result = subprocess.run(
            ['where', 'ISCC.exe'],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0:
            return result.stdout.strip().split('\n')[0]
    except (FileNotFoundError, subprocess.SubprocessError):
        pass
    
    return None


def build_installer(version):
    """
    Build installer using Inno Setup.
    
    Args:
        version: Version string (e.g., "1.0.0")
    """
    print(f"\nBuilding installer (version {version})...")
    
    # Find Inno Setup compiler
    iscc_path = find_innosetup_compiler()
    if not iscc_path:
        print("[FAIL] Inno Setup compiler (ISCC.exe) not found.")
        print("  Please install Inno Setup from https://jrsoftware.org/isinfo.php")
        print("  Or install via Chocolatey: choco install innosetup")
        sys.exit(1)
    
    # Check if executable exists (--onedir mode creates a folder)
    exe_path = Path('dist/BossTracker/BossTracker.exe')
    if not exe_path.exists():
        print("[FAIL] Executable not found. Run build_executable() first.")
        print(f"  Expected: {exe_path}")
        sys.exit(1)
    
    # Check if installer script exists
    iss_path = Path('installer/boss_tracker.iss')
    if not iss_path.exists():
        print(f"[FAIL] Installer script not found: {iss_path}")
        sys.exit(1)
    
    # Compile installer script
    cmd = [
        iscc_path,
        f'/DVersion={version}',
        str(iss_path)
    ]
    
    print(f"  Using Inno Setup: {iscc_path}")
    print(f"  Compiling: {iss_path}")
    
    try:
        result = subprocess.run(cmd, check=True)
        print("[OK] Installer built successfully!")
        
        # Find output installer
        installer_name = f"BossTracker-Setup-v{version}.exe"
        installer_path = Path('dist') / installer_name
        
        if installer_path.exists():
            size_mb = installer_path.stat().st_size / (1024 * 1024)
            print(f"  Output: {installer_path}")
            print(f"  Size: {size_mb:.2f} MB")
        else:
            print(f"  Warning: Expected installer not found at {installer_path}")
            print("  Check dist/ directory for installer files")
            
    except subprocess.CalledProcessError as e:
        print(f"[FAIL] Error building installer: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("[FAIL] Inno Setup compiler not found at expected location")
        sys.exit(1)


def validate_files():
    """Validate that required files exist before building."""
    print("Validating required files...")
    
    required_files = [
        Path('src/main.py'),
        Path('icons/tray_icon.ico'),
        Path('assets/fanfare.mp3'),
        Path('installer/boss_tracker.iss'),
    ]
    
    missing = []
    for file_path in required_files:
        if not file_path.exists():
            missing.append(str(file_path))
        else:
            print(f"  [OK] {file_path}")
    
    if missing:
        print("\n[FAIL] Missing required files:")
        for file_path in missing:
            print(f"  - {file_path}")
        sys.exit(1)
    
    print("[OK] All required files found")


def main():
    """Main build function."""
    print("=" * 60)
    print("Project Quarm Boss Tracker - Installer Build Script")
    print("=" * 60)
    
    # Get version (from command line argument or auto-detect)
    if len(sys.argv) > 1 and sys.argv[1] not in ('', '--skip-exe'):
        version = sys.argv[1].strip().lstrip('v')
    else:
        version = get_version()
    
    if not version:
        version = '1.0.0'
    
    print(f"\nVersion: {version}")
    
    # Validate files
    validate_files()
    
    # Build executable (only if not already built or --force flag)
    if '--skip-exe' not in sys.argv:
        build_executable(version)
    else:
        print("Skipping executable build (--skip-exe flag set)")
    
    # Build installer
    build_installer(version)
    
    print("\n" + "=" * 60)
    print("Build complete!")
    print("=" * 60)
    print(f"\nInstaller: dist/BossTracker-Setup-v{version}.exe")
    print("\nNext steps:")
    print("1. Test the installer on a clean system")
    print("2. Verify uninstaller preserves/removes settings correctly")
    print("3. Create GitHub release and upload installer")


if __name__ == "__main__":
    main()
