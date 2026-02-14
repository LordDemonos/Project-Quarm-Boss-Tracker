; Inno Setup Script for Project Quarm Boss Tracker
; This script creates a Windows installer with uninstall option to preserve settings

#define AppName "Project Quarm Boss Tracker"
#define AppInternalName "BossTracker"
#define AppPublisher "Project Quarm"
#define AppURL "https://github.com/LordDemonos/Project-Quarm-Boss-Tracker"
#define AppExeName "BossTracker.exe"

; Version is passed via compiler parameter: /DVersion=1.0.0
#ifndef Version
  #define Version "1.0.0"
#endif

[Setup]
; App information
AppId={{BossTrackerApp}}
AppName={#AppName}
AppVersion={#Version}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={localappdata}\Programs\Boss Tracker
DefaultGroupName=Boss Tracker
AllowNoIcons=yes
LicenseFile=
OutputDir=..\dist
OutputBaseFilename=BossTracker-Setup-v{#Version}
SetupIconFile=..\icons\tray_icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}

; Uninstall registry key
Uninstallable=yes
CreateUninstallRegKey=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode

[Files]
; Main executable (--onedir mode creates a folder)
Source: "..\dist\BossTracker\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; Include all files from BossTracker folder (dependencies)
Source: "..\dist\BossTracker\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Assets directory
Source: "..\assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs

; Icons directory
Source: "..\icons\*"; DestDir: "{app}\icons"; Flags: ignoreversion recursesubdirs createallsubdirs

; Optional: Default bosses.json if pre-populating
; Source: "..\data\bosses.json"; DestDir: "{app}"; Flags: ignoreversion; Check: FileExists(ExpandConstant("{#SourcePath}\..\data\bosses.json"))

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
var
  KeepSettingsCheckbox: TNewCheckBox;
  UserDataDir: String;

procedure InitializeUninstallProgressForm();
var
  InfoLabel: TLabel;
begin
  // Set user data directory path
  UserDataDir := ExpandConstant('{localappdata}\boss tracker');
  
  // Only show checkbox if not silent uninstall
  if not UninstallSilent then
  begin
    // Create info label
    InfoLabel := TLabel.Create(UninstallProgressForm);
    InfoLabel.Parent := UninstallProgressForm;
    InfoLabel.Caption := 'Choose whether to keep your settings and data:';
    InfoLabel.Left := ScaleX(16);
    InfoLabel.Top := ScaleY(180);
    InfoLabel.Width := UninstallProgressForm.ClientWidth - ScaleX(32);
    InfoLabel.AutoSize := False;
    InfoLabel.WordWrap := True;
    
    // Create checkbox on the uninstall progress form
    KeepSettingsCheckbox := TNewCheckBox.Create(UninstallProgressForm);
    KeepSettingsCheckbox.Parent := UninstallProgressForm;
    KeepSettingsCheckbox.Caption := 'Keep my settings and data';
    KeepSettingsCheckbox.Checked := True; // Default to keeping settings
    KeepSettingsCheckbox.Left := ScaleX(16);
    KeepSettingsCheckbox.Top := ScaleY(210);
    KeepSettingsCheckbox.Width := UninstallProgressForm.ClientWidth - ScaleX(32);
    KeepSettingsCheckbox.Font.Size := 9;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  KeepSettings: Boolean;
begin
  if CurUninstallStep = usUninstall then
  begin
    // Get user's choice (default to True if checkbox doesn't exist or silent uninstall)
    if Assigned(KeepSettingsCheckbox) then
      KeepSettings := KeepSettingsCheckbox.Checked
    else
      KeepSettings := True; // Default to keeping settings if checkbox not available
    
    // Store choice in registry for reference
    if KeepSettings then
    begin
      RegWriteStringValue(HKEY_CURRENT_USER,
        'Software\Microsoft\Windows\CurrentVersion\Uninstall\BossTracker',
        'KeepSettings', '1');
    end
    else
    begin
      RegWriteStringValue(HKEY_CURRENT_USER,
        'Software\Microsoft\Windows\CurrentVersion\Uninstall\BossTracker',
        'KeepSettings', '0');
    end;
  end;
  
  if CurUninstallStep = usPostUninstall then
  begin
    // After uninstall completes, check if we should delete user data
    if Assigned(KeepSettingsCheckbox) then
      KeepSettings := KeepSettingsCheckbox.Checked
    else
      KeepSettings := True; // Default to keeping settings if checkbox not available
    
    if not KeepSettings then
    begin
      // Delete user data directory
      if DirExists(UserDataDir) then
      begin
        DelTree(UserDataDir, True, True, True);
      end;
    end;
  end;
end;
