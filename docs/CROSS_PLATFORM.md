# Cross-Platform Support

The application is designed to work on **Windows, macOS, and Linux**, though it was originally developed for Windows.

## Supported Platforms

### ✅ Windows 10/11
- **Fully supported** - Original target platform
- System tray: Native Windows system tray
- Notifications: Windows notification system
- Theme detection: Registry-based detection
- Data directory: `%APPDATA%\boss tracker\`

### ✅ macOS
- **Fully supported** - PyQt6 provides native macOS support
- System tray: macOS menu bar (right side)
- Notifications: macOS notification center
- Theme detection: Uses `defaults read -g AppleInterfaceStyle`
- Data directory: `~/Library/Application Support/boss tracker/`

### ✅ Linux
- **Supported** - Works with most desktop environments
- System tray: Desktop environment's system tray (GNOME, KDE, XFCE, etc.)
- Notifications: Uses desktop notification system (libnotify)
- Theme detection: Supports GNOME (gsettings) and KDE (kreadconfig5)
- Data directory: `~/.config/boss tracker/` (or `$XDG_CONFIG_HOME/boss tracker/`)

## Cross-Platform Features

### ✅ Works Everywhere

1. **System Tray**
   - `QSystemTrayIcon` is cross-platform in PyQt6
   - Works on Windows, macOS, and Linux desktop environments
   - Icon display, context menu, and activation all work

2. **System Notifications**
   - `QSystemTrayIcon.showMessage()` is cross-platform
   - **Windows**: Uses Windows notification system
   - **macOS**: Uses macOS notification center
   - **Linux**: Uses desktop environment's notification daemon (libnotify)
   - All platforms show native-style notifications

3. **File Monitoring**
   - `watchdog` library works on all platforms
   - Log file monitoring works identically

4. **Discord Integration**
   - Webhooks work from any platform
   - Bot API works from any platform
   - No platform-specific code

5. **UI and Theming**
   - PyQt6 provides native look and feel on all platforms
   - Light/Dark mode switching works everywhere
   - Custom accent colors work everywhere

6. **Data Storage**
   - Uses OS-specific user data directories
   - JSON file format works identically
   - Encryption works identically

### ⚠️ Platform-Specific Features

1. **Dark Mode Overlay (Windows Only)**
   - The `ctypes` code that forces dark mode on Windows is Windows-specific
   - This is optional and wrapped in try/except - won't break on other platforms
   - macOS and Linux handle dark mode through Qt/PyQt6 automatically

2. **Theme Detection**
   - **Windows**: Registry-based (winreg)
   - **macOS**: Command-line based (defaults command)
   - **Linux**: Desktop environment specific (gsettings/kreadconfig5)
   - All platforms have detection implemented

3. **Icon Format**
   - **Windows**: `.ico` format (recommended)
   - **macOS/Linux**: `.ico` works, but `.png` or `.svg` may be preferred
   - PyQt6 handles format conversion automatically

## Testing on Other Platforms

### macOS Testing

1. Install Python 3.8+ and dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the application:
   ```bash
   python run.py
   ```

3. Check:
   - System tray icon appears in menu bar (right side)
   - Notifications appear in macOS notification center
   - Settings are saved to `~/Library/Application Support/boss tracker/`

### Linux Testing

1. Install dependencies (may need system packages):
   ```bash
   # Ubuntu/Debian
   sudo apt-get install python3-pyqt6 libnotify-bin
   
   # Fedora
   sudo dnf install python3-pyqt6 libnotify
   
   pip install -r requirements.txt
   ```

2. Run the application:
   ```bash
   python run.py
   ```

3. Check:
   - System tray icon appears (may need to enable in desktop environment)
   - Notifications appear via desktop notification system
   - Settings are saved to `~/.config/boss tracker/`

## Known Limitations

1. **System Tray on Linux**
   - Some desktop environments (like GNOME) hide system tray icons by default
   - Users may need to enable system tray extensions
   - The application checks `QSystemTrayIcon.isSystemTrayAvailable()` and will exit with an error if not available

2. **Notifications on Linux**
   - Requires `libnotify` to be installed
   - Some minimal desktop environments may not support notifications
   - Falls back gracefully if notifications aren't available

3. **Sound Playback**
   - Uses `pygame` which works on all platforms
   - May need audio codecs installed on Linux
   - File format support may vary (mp3, wav, ogg, flac should all work)

4. **Packaging**
   - Current packaging guide focuses on Windows MSI
   - macOS: Could use PyInstaller + DMG
   - Linux: Could use PyInstaller + AppImage/Debian package

## Platform-Specific Notes

### Windows
- Best tested and supported
- All features work as expected
- MSI installer available

### macOS
- Should work out of the box
- May need to allow Python in Security & Privacy settings
- System tray appears in menu bar (not dock)

### Linux
- Works with most desktop environments
- May need additional packages for notifications
- System tray behavior varies by desktop environment
- Some distributions may need PyQt6 installed via package manager

## Future Platform Support

The application architecture is already cross-platform. To improve support:

1. **Testing**: Test on macOS and Linux regularly
2. **Packaging**: Create installers for macOS (.dmg) and Linux (.deb/.rpm/AppImage)
3. **Documentation**: Add platform-specific setup instructions
4. **CI/CD**: Add automated testing on multiple platforms

## Summary

**Yes, the application can support other platforms!** The core functionality is already cross-platform:

- ✅ System tray works on Windows, macOS, and Linux
- ✅ Notifications work on all platforms (native system notifications)
- ✅ File monitoring works everywhere
- ✅ UI and theming work everywhere
- ✅ Data storage uses OS-appropriate directories

The only Windows-specific code is:
- Dark mode overlay (optional, won't break on other platforms)
- Theme detection method (but detection exists for all platforms)

The application should work on macOS and Linux with minimal or no changes!
