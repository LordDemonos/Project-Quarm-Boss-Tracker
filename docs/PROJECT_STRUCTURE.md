# Project Structure

This document explains the organization of the Project Quarm Boss Tracker codebase.

## Directory Structure

```
target tracker/
├── src/                    # Source code (all Python modules)
│   ├── __init__.py
│   ├── main.py            # Main application entry point
│   ├── main_window.py     # Main UI window
│   ├── system_tray.py     # System tray icon and menu
│   ├── options_window.py  # Settings/options dialog
│   ├── message_editor.py  # Message format editor
│   ├── zone_group_widget.py # Zone grouping widget
│   ├── new_boss_dialog.py # New boss discovery dialog
│   ├── message_parser.py  # Log line parser
│   ├── boss_database.py   # Boss database manager
│   ├── activity_database.py # Activity log database
│   ├── activity_log.py    # Activity log UI component
│   ├── discord_notifier.py # Discord webhook poster
│   ├── discord_checker.py # Discord duplicate checker
│   ├── log_monitor.py     # Log file monitor
│   ├── sound_player.py    # Sound notification player
│   ├── timestamp_formatter.py # Timestamp formatting
│   ├── security.py        # Encryption/decryption
│   ├── os_theme_detector.py # OS theme detection
│   ├── theme_manager.py   # Theme manager (legacy, not actively used)
│   └── logger.py          # Logging setup
│
├── assets/                # Application assets
│   └── fanfare.mp3        # Default sound notification
│
├── icons/                 # Application icons
│   └── tray_icon.ico      # System tray icon (should contain multiple sizes)
│
├── test_utilities/        # Testing utilities
│   ├── __init__.py
│   ├── run_all_tests.py   # Test runner
│   ├── mock_discord.py    # Mock Discord for testing
│   ├── test_parser.py     # Parser tests
│   ├── test_database.py   # Database tests
│   ├── test_activity.py    # Activity log tests
│   ├── test_timestamp.py  # Timestamp tests
│   ├── test_theme.py      # Theme tests
│   └── test_log_generator.py # Log generator for testing
│
├── docs/                  # Documentation
│   ├── PROJECT_STRUCTURE.md # This file
│   ├── README.md          # Main user documentation (moved from root)
│   ├── CROSS_PLATFORM.md  # Cross-platform support info
│   ├── ICON_SETUP.md      # Icon customization guide
│   ├── PACKAGING_GUIDE.md # Packaging instructions
│   ├── PRE_FLIGHT_CHECKLIST.md # Pre-release checklist
│   ├── TEST_UTILITIES.md  # Testing documentation
│   ├── TESTING_PLAN.md    # Testing strategy
│   ├── DESIGN_REVISION.md # Design decisions
│   ├── IMPLEMENTATION_NOTES.md # Implementation notes
│   └── TARGET_TRACKER.MD  # Original design document
│
├── .gitignore            # Git ignore rules
├── requirements.txt      # Python dependencies
├── run.py                # Application entry point (development)
└── build_msi.py         # Build script for PyInstaller/MSI

```

## Key Files

### Core Application Files

- **`run.py`**: Entry point for running the application during development
- **`src/main.py`**: Main application class that orchestrates all components
- **`requirements.txt`**: Python package dependencies

### Build Files

- **`build_msi.py`**: Script to build executable using PyInstaller
- **`.gitignore`**: Files and directories to exclude from version control

### Documentation

- **`README.md`**: Main user-facing documentation (should be in root for GitHub)
- **`docs/`**: All other documentation files

## What's NOT Included

### User Data (Gitignored)

The following are stored in OS-specific user data directories and are **not** part of the repository:

- **Settings**: `settings.json` (encrypted sensitive fields)
- **Boss Database**: `bosses.json` (user's boss list)
- **Activity Log**: `activity.json` (full activity history)
- **Logs**: `logs/` directory (application log files)

**Locations:**
- Windows: `%APPDATA%\boss tracker\`
- macOS: `~/Library/Application Support/boss tracker/`
- Linux: `~/.config/boss tracker/`

### Build Artifacts (Gitignored)

- `dist/` - PyInstaller output
- `build/` - Build temporary files
- `*.spec` - PyInstaller spec files
- `*.exe` - Compiled executables
- `*.msi` - Installer packages

### Generated Files (Gitignored)

- `__pycache__/` - Python bytecode cache
- `*.pyc` - Compiled Python files
- `themes/*.qss` - Generated theme files (themes are now generated inline)

## Removed Files

The following files were removed during cleanup:

- **`python`**: Empty file (accidental)
- **`assets/theme.css`**: Not used (themes are generated inline in code)
- **`setup.py`**: Not used (using PyInstaller instead of setuptools)

## Legacy/Unused Code

- **`src/theme_manager.py`**: Imported but not actively used. Themes are generated inline in `main.py` using `_get_dark_theme()` and `_get_light_theme()` functions.

## Packaging Considerations

When building the application:

1. **Assets**: `assets/` directory must be included (contains `fanfare.mp3`)
2. **Icons**: `icons/` directory must be included (contains `tray_icon.ico`)
3. **Default Data**: If you want to pre-populate bosses, create a `data/bosses.json` file that will be copied to user data on first run
4. **Themes**: Not needed - themes are generated inline in code

## Development vs. Production

### Development
- Run `python run.py` to start the application
- Uses source files directly
- Logs go to user data directory

### Production
- Build executable with `python build_msi.py`
- Creates `dist/EverQuestBossTracker.exe`
- Package into MSI installer using WiX Toolset or Inno Setup
- User data is stored in OS-specific directories (not in app directory)

## Testing

- **`test_utilities/`**: Contains test scripts and mock objects
- Run tests with `python test_utilities/run_all_tests.py`
- Tests use mock Discord to avoid posting real messages

## Notes for GitHub

When preparing for GitHub:

1. ✅ All documentation is in `docs/` (except `README.md` which should be in root)
2. ✅ User data directories are gitignored
3. ✅ Build artifacts are gitignored
4. ✅ Unused files have been removed
5. ✅ Project structure is clean and organized
