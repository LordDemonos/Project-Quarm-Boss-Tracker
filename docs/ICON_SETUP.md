# Custom Icon Setup Guide

This guide explains how to customize the application icon for both the window title bar and system tray.

## Icon File Requirements

- **Format**: `.ico` (Windows Icon) format is recommended for best compatibility
- **Sizes**: Include multiple sizes (16x16, 32x32, 48x48, 256x256) for best results
- **Location**: Place your icon file in one of these locations (checked in order):

### Preferred Locations (checked in order):
1. `icons/tray_icon.ico` - **Primary location** (use this one!)
2. `icons/app_icon.ico` - Alternative icon name
3. `assets/icon.ico` - Assets folder
4. `icon.ico` - Root directory

**Important**: The application uses the **first icon file it finds** in the list above. If you have multiple icon files, make sure `tray_icon.ico` is the one you want to use, or remove/rename the others.

## How It Works

The application automatically searches for icon files in the locations above when it starts:

1. **Window Icons**: All windows (Main Window, Settings, Message Editor, etc.) automatically use the application icon set via `QApplication.setWindowIcon()`. This means you only need to set it once, and all windows inherit it.

2. **System Tray Icon**: The system tray icon uses the same icon file. If found, it's passed to the `SystemTray` class.

3. **Fallback**: If no custom icon is found, the application uses:
   - **Windows**: Default system computer icon
   - **System Tray**: Default system computer icon

## Steps to Add Your Custom Icon

### Option 1: Replace Existing Icon (Easiest)

1. Create or obtain your `.ico` file (**with multiple sizes included** - see "Creating an ICO File" below)
2. Replace the existing file: `icons/tray_icon.ico`
3. Restart the application
4. The icon should appear in:
   - Window title bars (upper left corner) - uses 16x16 or 32x32
   - System tray - uses 16x16 or 32x32
   - Taskbar (when window is open) - uses 32x32 or larger

### Option 2: Use a Different Filename

1. Create or obtain your `.ico` file
2. Place it in one of these locations:
   - `icons/app_icon.ico`
   - `assets/icon.ico`
   - `icon.ico` (root directory)
3. Restart the application

## Creating an ICO File

**Important**: Create **ONE** `.ico` file that contains **multiple sizes** inside it. The ICO format is a container that can hold multiple resolutions, and Windows/Qt will automatically select the best size for each context.

### Using Online Tools:
- [ConvertICO](https://convertico.com/) - Convert PNG to ICO (supports multi-size)
- [ICO Convert](https://icoconvert.com/) - Multi-size ICO generator (recommended - upload multiple sizes)
- [RealWorld ICO](http://www.rw-designer.com/online-icon-maker) - Create ICO with multiple sizes

### Using Image Editing Software:
- **GIMP** (free): 
  1. Create your icon at 256x256 pixels
  2. File → Export As → Select `.ico` format
  3. When exporting, choose to include multiple sizes
- **Photoshop**: File → Export → Save for Web → Select ICO format (includes multiple sizes)
- **Paint.NET** (Windows): Use ICO plugin, export with multiple sizes

### Recommended Icon Sizes to Include:
When creating your `.ico` file, include these sizes **all in one file**:
- **16x16 pixels** - Window title bar, small tray icon
- **32x32 pixels** - Standard tray icon size
- **48x48 pixels** - High DPI displays
- **256x256 pixels** - Large icons, modern Windows, taskbar

**How to create multi-size ICO:**
1. Create your icon design at 256x256 pixels (highest quality)
2. Use an ICO converter tool that supports multiple sizes
3. Upload your 256x256 image and let the tool generate all sizes automatically
4. Or manually create each size and combine them into one ICO file

**Example workflow:**
1. Design icon at 256x256 in your favorite image editor
2. Export as PNG at 256x256
3. Use [ICO Convert](https://icoconvert.com/) to create multi-size ICO
4. Save as `icons/tray_icon.ico`
5. Done! One file with all sizes.

## Testing Your Icon

1. Place your icon file in one of the locations above
2. Run the application: `python run.py`
3. Check:
   - **Window title bar**: Look at the upper left corner of any window
   - **System tray**: Minimize the window and check the system tray
   - **Taskbar**: Check the taskbar icon when the window is open

## Troubleshooting

### Icon Not Appearing

1. **Check file location**: Make sure the icon file is in one of the expected locations
2. **Check file format**: Ensure it's a valid `.ico` file (not just renamed `.png`)
3. **Check file name**: Use one of the expected filenames (`tray_icon.ico`, `app_icon.ico`, `icon.ico`)
4. **Check logs**: Look for messages like:
   - `"Application icon set from: ..."` (success)
   - `"No custom icon found, using default"` (not found)

### Icon Looks Blurry

- Include multiple sizes in your ICO file (16x16, 32x32, 48x48, 256x256)
- Windows will automatically select the best size for each context

### Icon Not Showing in System Tray

- Make sure the file is readable
- Try restarting the application
- Check Windows notification area settings (some systems hide tray icons)

## Code Reference

The icon loading logic is in `src/main.py`:

```python
def _set_application_icon(self) -> Optional[Path]:
    """Set the application icon for all windows and system tray."""
    # Searches for icon files in order:
    # 1. icons/tray_icon.ico
    # 2. icons/app_icon.ico
    # 3. assets/icon.ico
    # 4. icon.ico
    # Sets QApplication.setWindowIcon() which applies to all windows
```

The system tray icon is set in `src/system_tray.py`:

```python
def __init__(self, icon_path: Optional[str] = None):
    if icon_path:
        self.tray_icon.setIcon(QIcon(icon_path))
    else:
        # Uses default system icon
```

## Packaging Considerations

When packaging the application:

1. **Include icon file**: Make sure your `.ico` file is included in the package
2. **PyInstaller**: Add `--icon=icons/tray_icon.ico` to your PyInstaller command
3. **MSI Installer**: The icon will be used for:
   - The installer itself
   - The installed application shortcut
   - The application executable

## Example: Quick Setup

1. Create a 256x256 PNG image of your icon (design at highest quality)
2. Use an online ICO converter (like [ICO Convert](https://icoconvert.com/)) to create a multi-size ICO file
   - Upload your 256x256 PNG
   - The converter will automatically generate 16x16, 32x32, 48x48, and 256x256 sizes
   - Download the resulting `.ico` file
3. Save as `icons/tray_icon.ico` (replace the existing file)
4. Restart the application

That's it! Your custom icon should now appear everywhere. Windows and Qt will automatically use the best size for each context.

## FAQ

**Q: Do I need separate files for each size?**  
A: No! Create **one** `.ico` file that contains all sizes. The ICO format is a container.

**Q: Which size is used for the tray icon?**  
A: Windows automatically selects the best size (usually 16x16 or 32x32) based on your display settings. That's why you include multiple sizes - so the system can choose.

**Q: I only have a 256x256 image, is that enough?**  
A: It will work, but may look blurry when scaled down. It's better to include smaller sizes (16x16, 32x32) for crisp rendering at small sizes.
