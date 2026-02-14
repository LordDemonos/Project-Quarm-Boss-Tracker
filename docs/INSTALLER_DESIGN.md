# Installer Design Document

## Overview

This document describes the Windows installer implementation for Project Quarm Boss Tracker using Inno Setup. The installer provides a complete installation and uninstallation experience with the option to preserve user settings and data.

## Requirements

### Installation Requirements

1. **Application Installation**
   - Install executable to user-accessible location
   - Include all required assets (sound files, icons)
   - Create Start Menu shortcuts
   - Create optional Desktop shortcut
   - Register uninstaller in Windows Programs and Features

2. **File Structure**
   - Executable: `BossTracker.exe` (or current name)
   - Assets: `assets/` directory (contains `fanfare.mp3`)
   - Icons: `icons/` directory (contains `tray_icon.ico`)
   - Optional: Default `bosses.json` for pre-population

3. **Installation Location**
   - Default: `{localappdata}\Programs\Boss Tracker` (user-level installation)
   - Alternative: `{pf}\Boss Tracker` (system-wide, requires admin)
   - User-level preferred for easier updates and no admin requirements

### Uninstallation Requirements

1. **Standard Uninstall**
   - Remove all application files
   - Remove Start Menu shortcuts
   - Remove Desktop shortcut (if created)
   - Remove registry entries
   - Remove uninstaller entry from Programs and Features

2. **Settings Preservation Option**
   - Show custom uninstall page with checkbox: "Keep my settings and data"
   - If checked: Preserve `%APPDATA%\boss tracker\` directory
   - If unchecked: Delete entire `%APPDATA%\boss tracker\` directory
   - User data includes:
     - `settings.json` (encrypted webhook URLs, bot tokens, preferences)
     - `bosses.json` (user's boss database)
     - `activity.json` (activity log history)
     - `logs/` directory (application logs)

## Technical Details

### Application Information

- **Name**: Project Quarm Boss Tracker
- **Internal Name**: BossTracker
- **Publisher**: (To be configured)
- **Version**: Managed via `version.txt` or git tags
- **App ID**: `{BossTrackerApp}` (GUID can be generated)

### Registry Entries

**Uninstall Registry Key**:
```
HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Uninstall\BossTracker
```

**Registry Values**:
- `DisplayName`: "Project Quarm Boss Tracker"
- `DisplayVersion`: Version number (e.g., "1.0.0")
- `Publisher`: Publisher name
- `InstallLocation`: Installation directory path
- `UninstallString`: Path to uninstaller executable
- `DisplayIcon`: Path to application icon
- `NoModify`: 1 (no modify option)
- `NoRepair`: 1 (no repair option)
- `KeepSettings`: 0 or 1 (custom value, set during uninstall)

### User Data Directory

**Location**: `%APPDATA%\boss tracker\`

**Contents**:
- `settings.json` - Application settings (encrypted sensitive fields)
- `bosses.json` - Boss database
- `activity.json` - Activity log
- `logs/` - Application log files

**Preservation Logic**:
- During uninstall, check user's choice
- If "Keep settings" is checked: Do not delete this directory
- If "Keep settings" is unchecked: Delete entire directory recursively

### Version Management

**Options**:
1. **version.txt**: Simple text file with version number (e.g., `1.0.0`)
2. **Git Tags**: Extract from git tag when building (e.g., `v1.0.0` → `1.0.0`)
3. **Environment Variable**: Set version via environment variable in CI/CD

**Precedence**:
1. Git tag (if building from git)
2. Environment variable `VERSION`
3. `version.txt` file
4. Default: `1.0.0`

### Build Process

1. **Build Executable**
   - Use PyInstaller to create single-file executable
   - Include assets and icons as embedded data
   - Output: `dist/BossTracker.exe`

2. **Compile Installer**
   - Use Inno Setup Compiler (`ISCC.exe`)
   - Pass version via compiler parameter: `/DVersion=1.0.0`
   - Output: `dist/BossTracker-Setup-v1.0.0.exe`

3. **Automated Builds**
   - GitHub Actions workflow triggers on release creation
   - Extracts version from git tag
   - Builds executable and installer
   - Attaches installer to GitHub release

## Installer Features

### Installation Wizard Pages

1. **Welcome Page**: Standard Inno Setup welcome
2. **License Page**: (Optional, if license file exists)
3. **Select Destination Location**: Default to `{localappdata}\Programs\Boss Tracker`
4. **Select Start Menu Folder**: Default to "Boss Tracker"
5. **Select Additional Tasks**:
   - Create Desktop shortcut (optional checkbox)
6. **Ready to Install**: Summary of installation
7. **Installing**: Progress bar
8. **Finished**: Completion message

### Uninstallation Wizard Pages

1. **Welcome Page**: Standard uninstall welcome
2. **Custom Page**: "Keep my settings and data" checkbox
3. **Uninstalling**: Progress bar
4. **Finished**: Completion message

### Custom Uninstall Page Implementation

**Using Inno Setup Pascal Script**:

```pascal
var
  KeepSettingsPage: TOutputOptionWizardPage;
  KeepSettingsCheckbox: TNewCheckBox;

procedure InitializeWizard;
begin
  KeepSettingsPage := CreateOutputOptionPage(wpWelcome,
    'Settings Preservation', 'Choose what to keep',
    'Select whether you want to keep your settings and data:');
  
  KeepSettingsCheckbox := TNewCheckBox.Create(KeepSettingsPage);
  KeepSettingsCheckbox.Caption := 'Keep my settings and data';
  KeepSettingsCheckbox.Checked := True; // Default to keeping
  KeepSettingsCheckbox.Parent := KeepSettingsPage.Surface;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    if KeepSettingsCheckbox.Checked then
    begin
      // Don't delete user data directory
      // Registry value already set
    end
    else
    begin
      // Delete user data directory
      DelTree(ExpandConstant('{localappdata}\boss tracker'), True, True, True);
    end;
  end;
end;
```

## File Locations

### Installation Directory Structure

```
{localappdata}\Programs\Boss Tracker\
├── BossTracker.exe
├── assets\
│   └── fanfare.mp3
└── icons\
    └── tray_icon.ico
```

### User Data Directory Structure

```
%APPDATA%\boss tracker\
├── settings.json
├── bosses.json
├── activity.json
└── logs\
    └── boss_tracker_YYYYMMDD.log
```

## Testing Requirements

### Installation Testing

- [ ] Installer runs without errors
- [ ] All files are copied correctly
- [ ] Shortcuts are created in correct locations
- [ ] Application launches successfully after installation
- [ ] Application can access assets (sound file plays)
- [ ] Application can access icons (tray icon displays)
- [ ] Uninstaller appears in Programs and Features

### Uninstallation Testing

- [ ] Uninstaller launches from Programs and Features
- [ ] Custom page displays correctly
- [ ] With "Keep settings" checked:
  - [ ] Application files are removed
  - [ ] Shortcuts are removed
  - [ ] User data directory remains intact
- [ ] With "Keep settings" unchecked:
  - [ ] Application files are removed
  - [ ] Shortcuts are removed
  - [ ] User data directory is completely deleted
- [ ] Registry entries are removed correctly

### Upgrade Testing

- [ ] Installing over existing installation works
- [ ] User data is preserved during upgrade
- [ ] Settings remain intact after upgrade

## Security Considerations

1. **User Data Encryption**: Settings file contains encrypted sensitive data (webhook URLs, bot tokens). This is handled by the application, not the installer.

2. **Installation Permissions**: User-level installation (`{localappdata}`) doesn't require admin rights, improving security posture.

3. **Uninstaller Verification**: Uninstaller should verify it's removing the correct application to prevent accidental deletion.

## Future Enhancements

1. **Auto-Update**: Check for updates on launch
2. **Silent Installation**: Support `/S` parameter for silent install
3. **Silent Uninstallation**: Support `/S` parameter for silent uninstall
4. **Code Signing**: Sign installer with code signing certificate
5. **Multi-Architecture**: Support both x86 and x64 builds
6. **Delta Updates**: Only download changed files for updates

## References

- [Inno Setup Documentation](https://jrsoftware.org/ishelp/)
- [Inno Setup Pascal Scripting](https://jrsoftware.org/ishelp/index.php?topic=scriptpages)
- [PyInstaller Documentation](https://pyinstaller.org/)
