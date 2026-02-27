# Installer Quick Start Guide

## For Users

### Installing the Application

1. Download `BossTracker-Setup-vX.X.X.exe` from the [Releases](https://github.com/yourusername/boss-tracker/releases) page
2. Run the installer
3. Follow the installation wizard
4. Launch from Start Menu or Desktop shortcut

### Uninstalling the Application

1. Go to **Settings** → **Apps** → **Apps & features** (Windows 10/11)
2. Find "Project Quarm Boss Tracker"
3. Click **Uninstall**
4. When prompted, choose whether to **keep your settings and data**:
   - **Checked**: Your settings, boss database, and activity log will be preserved
   - **Unchecked**: Everything will be removed, including your data

## For Developers

### How the build process works

Building the installer is **two steps in one command**:

1. **PyInstaller** (build the executable)
   - Run from the **project root** (where `build_installer.py` lives).
   - Bundles your Python app and dependencies into a folder: `dist/BossTracker/`.
   - That folder contains:
     - `BossTracker.exe`
     - Python runtime and libraries
     - `assets/`, `icons/`, `version.txt`
     - **`data/bosses.json`** (default boss list; added via `--add-data=data/bosses.json;data` in `build_installer.py`).
   - The app at runtime looks for this default list under the install directory (e.g. `{app}\data\bosses.json`) so new installs get the full mob list.

2. **Inno Setup** (build the installer)
   - Takes `dist/BossTracker/` and the repo’s `assets/`, `icons/`, and **`data/bosses.json`**.
   - Produces a single installer: `dist/BossTracker-Setup-vX.X.X.exe`.
   - When a user runs that installer, it copies everything into the install dir (e.g. `%LOCALAPPDATA%\Programs\Boss Tracker\`), including `data\bosses.json`.
   - The installer script is `installer/boss_tracker.iss`; it explicitly includes `Source: "..\data\bosses.json"; DestDir: "{app}\data"` so the default list is always installed even if PyInstaller’s bundle were missing it.

**One command does both steps:**

```bash
python build_installer.py
```

This runs PyInstaller (with the correct `--add-data` so `data/bosses.json` is in the bundle), then runs the Inno Setup compiler. You need **PyInstaller** (`pip install pyinstaller`) and **Inno Setup** (installed on Windows) for the full build.

**Optional:** `python build_installer.py --skip-exe` skips the PyInstaller step and only rebuilds the installer from the existing `dist/BossTracker/` folder (useful if you only changed the `.iss` script).

### Building Locally

1. **Install Inno Setup**:
   - Download from https://jrsoftware.org/isinfo.php
   - Or use Chocolatey: `choco install innosetup`

2. **Build installer**:
   ```bash
   python build_installer.py
   ```

3. **Output**: `dist/BossTracker-Setup-vX.X.X.exe`

### Building with Custom Version

```bash
python build_installer.py 1.2.3
```

### Building for GitHub Release

1. **Create a git tag**:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

2. **Create GitHub release** with the tag

3. **GitHub Actions** will automatically:
   - Extract version from tag
   - Build executable
   - Build installer
   - Attach installer to release

### Manual GitHub Actions Trigger

1. Go to **Actions** tab in GitHub
2. Select **Build Windows Installer** workflow
3. Click **Run workflow**
4. Optionally specify version number
5. Click **Run workflow**

## Troubleshooting

### Inno Setup Not Found

**Error**: `Inno Setup compiler (ISCC.exe) not found`

**Solution**: 
- Install Inno Setup from https://jrsoftware.org/isinfo.php
- Or use Chocolatey: `choco install innosetup`
- Ensure it's installed to the default location

### Executable Not Found

**Error**: `Executable not found. Run build_executable() first.`

**Solution**: 
- The build script will build the executable automatically
- If you see this error, ensure PyInstaller is installed: `pip install pyinstaller`
- Check that `src/main.py` exists

### Version Not Found

**Error**: Version extraction fails

**Solution**:
- Create `version.txt` with version number (e.g., `1.0.0`)
- Or set environment variable: `set VERSION=1.0.0`
- Or pass as argument: `python build_installer.py 1.0.0`

## File Locations

### Installation Directory
- **Windows**: `%LOCALAPPDATA%\Programs\Boss Tracker\`

### User Data Directory (Preserved on Uninstall if Requested)
- **Windows**: `%APPDATA%\boss tracker\`
- Contains: `settings.json`, `bosses.json`, `activity.json`, `logs/`

## Testing as a New User (Fresh Install)

To test the installer as if you’re a new user (no existing data):

1. **Back up your current data** (optional but recommended):
   - Open `%APPDATA%\boss tracker\` (Win+R → type that → Enter).
   - Copy the entire `boss tracker` folder to a safe place (e.g. `Desktop\boss-tracker-backup`).

2. **Remove the app data** so the app starts with no settings:
   - Delete the contents of `%APPDATA%\boss tracker\` (or rename the folder to `boss tracker-old`).

3. **Run the installer** (`dist\BossTracker-Setup-vX.X.X.exe`) and install.

4. **Launch the app** and verify:
   - First-run experience (default bosses load if bundled, or empty list).
   - Settings, Discord setup, backups, activity log all work.

5. **Restore your data** when done testing:
   - Restore from your backup, or rename `boss tracker-old` back to `boss tracker`.

## Testing Checklist

Before releasing:

- [ ] Installer installs correctly
- [ ] Application launches after installation
- [ ] All assets (sound, icons) work correctly
- [ ] Uninstaller appears in Programs and Features
- [ ] Uninstaller preserves settings when checked
- [ ] Uninstaller removes settings when unchecked
- [ ] Version number is correct in installer
- [ ] Installer file size is reasonable (< 100 MB typically)
