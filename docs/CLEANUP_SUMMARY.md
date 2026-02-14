# Project Cleanup Summary

This document summarizes the cleanup and organization work done to prepare the project for GitHub and build/release scripts.

## Files Moved to `docs/` Directory

All documentation files have been moved to the `docs/` folder for better organization:

- ✅ `CROSS_PLATFORM.md` → `docs/CROSS_PLATFORM.md`
- ✅ `ICON_SETUP.md` → `docs/ICON_SETUP.md`
- ✅ `PACKAGING_GUIDE.md` → `docs/PACKAGING_GUIDE.md`
- ✅ `PRE_FLIGHT_CHECKLIST.md` → `docs/PRE_FLIGHT_CHECKLIST.md`
- ✅ `TARGET_TRACKER.MD` → `docs/TARGET_TRACKER.MD`
- ✅ `TESTING_PLAN.md` → `docs/TESTING_PLAN.md`
- ✅ `DESIGN_REVISION.md` → `docs/DESIGN_REVISION.md`
- ✅ `IMPLEMENTATION_NOTES.md` → `docs/IMPLEMENTATION_NOTES.md`
- ✅ `test_utilities/README.md` → `docs/TEST_UTILITIES.md`

**Note**: `README.md` remains in the root directory as it's the main user-facing documentation that GitHub displays.

## Files Deleted

Unused or unnecessary files have been removed:

- ✅ `python` - Empty file (accidental creation)
- ✅ `assets/theme.css` - Not used (themes are generated inline in code)
- ✅ `setup.py` - Not used (using PyInstaller instead of setuptools)

## Files Updated

### `build_msi.py`
- Removed reference to `themes` directory (not needed - themes generated inline)
- Removed reference to `data` directory (user data, not packaged)
- Added reference to `icons` directory (needed for packaging)
- Updated instructions to reflect changes

### `.gitignore`
- Added comments for clarity
- Kept `themes/*.qss` ignore rule (for safety, even though themes directory may not exist)

## New Documentation Created

- ✅ `docs/PROJECT_STRUCTURE.md` - Comprehensive project structure documentation
- ✅ `docs/CLEANUP_SUMMARY.md` - This file

## Current Project Structure

```
target tracker/
├── src/              # All Python source code
├── assets/          # Application assets (fanfare.mp3)
├── icons/           # Application icons
├── test_utilities/  # Testing utilities
├── docs/            # All documentation
├── README.md        # Main user documentation (root)
├── requirements.txt # Python dependencies
├── run.py           # Development entry point
├── build_msi.py     # Build script
└── .gitignore       # Git ignore rules
```

## What's NOT in the Repository

The following are stored in OS-specific user data directories and are gitignored:

- `settings.json` - User settings (encrypted sensitive fields)
- `bosses.json` - User's boss database
- `activity.json` - Activity log history
- `logs/` - Application log files

**Locations:**
- Windows: `%APPDATA%\boss tracker\`
- macOS: `~/Library/Application Support/boss tracker/`
- Linux: `~/.config/boss tracker/`

## Build Artifacts (Gitignored)

- `dist/` - PyInstaller output
- `build/` - Build temporary files
- `*.spec` - PyInstaller spec files
- `*.exe` - Compiled executables
- `*.msi` - Installer packages

## Next Steps for GitHub

1. ✅ Project structure is organized
2. ✅ Documentation is in `docs/` folder
3. ✅ Unused files removed
4. ✅ Build script updated
5. ⏭️ Create GitHub repository
6. ⏭️ Add GitHub Actions workflow for builds (optional)
7. ⏭️ Create release script

## Notes

- **Themes**: Themes are generated inline in `src/main.py` using `_get_dark_theme()` and `_get_light_theme()` functions. The `ThemeManager` class exists but is not actively used. The `themes/` directory exists with generated `.qss` files but these are gitignored and not needed for the application to run (themes are generated dynamically).

- **Default Bosses**: If you want to pre-populate bosses in the packaged app, create a `data/bosses.json` file in the app directory. The application will copy it to the user data directory on first run.

- **Cross-Platform**: The application supports Windows, macOS, and Linux. See `docs/CROSS_PLATFORM.md` for details.
