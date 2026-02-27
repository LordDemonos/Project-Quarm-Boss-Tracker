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
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}

; Uninstall registry key
Uninstallable=yes
CreateUninstallRegKey=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Main executable (--onedir mode creates a folder)
Source: "..\dist\BossTracker\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; Include all files from BossTracker folder (dependencies)
Source: "..\dist\BossTracker\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Assets directory
Source: "..\assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs

; Icons directory
Source: "..\icons\*"; DestDir: "{app}\icons"; Flags: ignoreversion recursesubdirs createallsubdirs

; Default boss list (so new installs have full mob list; app expects {app}\data\bosses.json)
Source: "..\data\bosses.json"; DestDir: "{app}\data"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
var
  UserDataDir: String;
  UninstallKeepSettingsChoice: Boolean;  // Set by the initial "pause" dialog
  UninstallChoiceMade: Boolean;         // True after user has seen the dialog

function InitializeUninstall(): Boolean;
var
  UninstallForm: TSetupForm;
  InfoLabel: TLabel;
  KeepCheckbox: TNewCheckBox;
  UninstallBtn: TNewButton;
  CancelBtn: TNewButton;
begin
  Result := True;
  UninstallKeepSettingsChoice := True;
  UninstallChoiceMade := False;

  if UninstallSilent then
    Exit;

  UninstallForm := CreateCustomForm(ScaleX(400), ScaleY(200), False, False);
  UninstallForm.Caption := 'Uninstall {#AppName}';
  UninstallForm.BorderStyle := bsDialog;

  InfoLabel := TLabel.Create(UninstallForm);
  InfoLabel.Parent := UninstallForm;
  InfoLabel.Caption := 'Do you want to keep your settings and data (webhook, bot token, boss list, activity log)?';
  InfoLabel.Left := ScaleX(16);
  InfoLabel.Top := ScaleY(16);
  InfoLabel.Width := UninstallForm.ClientWidth - ScaleX(32);
  InfoLabel.AutoSize := False;
  InfoLabel.WordWrap := True;

  KeepCheckbox := TNewCheckBox.Create(UninstallForm);
  KeepCheckbox.Parent := UninstallForm;
  KeepCheckbox.Caption := 'Keep my settings and data';
  KeepCheckbox.Checked := True;
  KeepCheckbox.Left := ScaleX(16);
  KeepCheckbox.Top := ScaleY(72);
  KeepCheckbox.Width := UninstallForm.ClientWidth - ScaleX(32);

  CancelBtn := TNewButton.Create(UninstallForm);
  CancelBtn.Parent := UninstallForm;
  CancelBtn.Caption := 'Cancel';
  CancelBtn.ModalResult := mrCancel;
  CancelBtn.Left := UninstallForm.ClientWidth - ScaleX(180);
  CancelBtn.Top := ScaleY(140);
  CancelBtn.Width := ScaleX(75);
  CancelBtn.Height := ScaleY(23);

  UninstallBtn := TNewButton.Create(UninstallForm);
  UninstallBtn.Parent := UninstallForm;
  UninstallBtn.Caption := 'Uninstall';
  UninstallBtn.ModalResult := mrOK;
  UninstallBtn.Left := UninstallForm.ClientWidth - ScaleX(92);
  UninstallBtn.Top := ScaleY(140);
  UninstallBtn.Width := ScaleX(75);
  UninstallBtn.Height := ScaleY(23);

  UninstallForm.ActiveControl := KeepCheckbox;

  if UninstallForm.ShowModal() = mrOK then
  begin
    UninstallKeepSettingsChoice := KeepCheckbox.Checked;
    UninstallChoiceMade := True;
    Result := True;
  end
  else
  begin
    Result := False;  // Abort uninstall
  end;
end;

procedure InitializeUninstallProgressForm();
var
  InfoLabel: TLabel;
begin
  UserDataDir := ExpandConstant('{localappdata}\boss tracker');

  if not UninstallSilent and UninstallChoiceMade then
  begin
    InfoLabel := TLabel.Create(UninstallProgressForm);
    InfoLabel.Parent := UninstallProgressForm;
    if UninstallKeepSettingsChoice then
      InfoLabel.Caption := 'Your settings and data will be kept.'
    else
      InfoLabel.Caption := 'Your settings and data will be removed.';
    InfoLabel.Left := ScaleX(16);
    InfoLabel.Top := ScaleY(180);
    InfoLabel.Width := UninstallProgressForm.ClientWidth - ScaleX(32);
    InfoLabel.AutoSize := False;
    InfoLabel.WordWrap := True;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  KeepSettings: Boolean;
begin
  if CurUninstallStep = usUninstall then
  begin
    if UninstallChoiceMade then
      KeepSettings := UninstallKeepSettingsChoice
    else
      KeepSettings := True;

    if KeepSettings then
      RegWriteStringValue(HKEY_CURRENT_USER,
        'Software\Microsoft\Windows\CurrentVersion\Uninstall\BossTracker',
        'KeepSettings', '1')
    else
      RegWriteStringValue(HKEY_CURRENT_USER,
        'Software\Microsoft\Windows\CurrentVersion\Uninstall\BossTracker',
        'KeepSettings', '0');
  end;

  if CurUninstallStep = usPostUninstall then
  begin
    if UninstallChoiceMade then
      KeepSettings := UninstallKeepSettingsChoice
    else
      KeepSettings := True;

    if not KeepSettings then
    begin
      if DirExists(UserDataDir) then
        DelTree(UserDataDir, True, True, True);
    end;

    // Remove runtime-created logs in install dir (app writes .cursor/debug.log there)
    if DirExists(ExpandConstant('{app}\.cursor')) then
      DelTree(ExpandConstant('{app}\.cursor'), True, True, True);
  end;
end;
