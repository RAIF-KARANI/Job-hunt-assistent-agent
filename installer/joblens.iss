; Inno Setup script for JobLens-Setup-<version>.exe (Phase 10d).
;
; Build everything with one command (from the repo root, venv activated):
;     python scripts/build_installer.py
; which runs PyInstaller (dist\JobLens\) and then:
;     ISCC.exe /DAppVersion=<version> installer\joblens.iss
;
; What the installer does:
;   - installs per user (no admin prompt) into %LOCALAPPDATA%\Programs\JobLens
;   - Start-menu entry, optional desktop shortcut, "Launch JobLens" at the end
;   - registers in Windows Settings > Apps, so it uninstalls the normal way
; What the uninstaller does:
;   - removes the program files and shortcuts
;   - ASKS whether to keep your data (%LOCALAPPDATA%\JobLens: tracker,
;     cover notes, resume copies, settings). Default: keep.
;   - never touches Ollama or downloaded models (installed separately)
; Since 12h:
;   - installs Microsoft Edge WebView2 Runtime (the engine the window uses)
;     if the PC doesn't have it, with the bootstrapper build_installer.py
;     downloaded and checked
;   - /DTestBuild makes a separate "JobLens Test Build" (own AppId, folder,
;     shortcut; its uninstaller never deletes data), so a build can be
;     installed and uninstalled for testing next to a real JobLens

#ifndef AppVersion
  #define AppVersion "0.0.0-dev"
#endif
#ifdef TestBuild
  #define TheAppName "JobLens Test Build"
  #define TheAppId "{{C4A7D2E1-8B3F-4E6A-9D5C-1F2E3A4B5C6D}"
#else
  #define TheAppName "JobLens"
  #define TheAppId "{{6B0E5A3C-2F1D-4C8B-9E7A-4A1F2D3C5B6E}"
#endif

[Setup]
; AppId identifies JobLens to Windows across versions: never change it, or an
; upgrade would install side by side instead of replacing the old version.
AppId={#TheAppId}
AppName={#TheAppName}
AppVersion={#AppVersion}
AppVerName={#TheAppName} {#AppVersion}
AppPublisher=Raif Karani
AppPublisherURL=https://github.com/RAIF-KARANI/Job-hunt-assistent-agent
DefaultDirName={localappdata}\Programs\{#TheAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
#ifdef TestBuild
OutputBaseFilename=JobLens-TestBuild-Setup-{#AppVersion}
#else
OutputBaseFilename=JobLens-Setup-{#AppVersion}
#endif
SetupIconFile=..\assets\joblens.ico
UninstallDisplayIcon={app}\JobLens.exe
UninstallDisplayName={#TheAppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Close a running JobLens before installing / uninstalling.
CloseApplications=yes
; 13d: after an in-app update, /RELAUNCH=1 starts the new JobLens ([Run]). Don't
; also let Windows' Restart Manager restart what it closed: one way, not two.
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
; The whole PyInstaller folder: JobLens.exe + _internal\
Source: "..\dist\JobLens\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Licenses: JobLens (MIT) + bundled components
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion
; Microsoft's WebView2 bootstrapper (~2 MB): copied to a temp folder only if needed
Source: "..\build\webview2\MicrosoftEdgeWebview2Setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: NeedsWebView2

[Icons]
Name: "{autoprograms}\{#TheAppName}"; Filename: "{app}\JobLens.exe"
Name: "{autodesktop}\{#TheAppName}"; Filename: "{app}\JobLens.exe"; Tasks: desktopicon

[Registry]
; 14e: "Start JobLens with Windows" is turned on in Settings (desktop_web/autostart.py),
; never by the installer. The uninstaller removes it (ValueType none: nothing is written).
#ifndef TestBuild
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "JobLens"; Flags: uninsdeletevalue
#endif

[Run]
; Before the app can start: the WebView2 Runtime, silently (per user, no admin prompt).
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; StatusMsg: "Installing Microsoft Edge WebView2 Runtime..."; Flags: waituntilterminated; Check: NeedsWebView2
Filename: "{app}\JobLens.exe"; Description: "Launch JobLens"; Flags: nowait postinstall skipifsilent
; 13d: an update started from inside JobLens runs silently and asks with /RELAUNCH=1
; to open the new version when it's done (a plain silent install doesn't).
Filename: "{app}\JobLens.exe"; Flags: nowait; Check: RelaunchAfterUpdate

[Code]
{ Windows paths are limited to 260 characters. JobLens' deepest file adds
  ~105 characters to the install folder, so a very deep folder would fail
  half-way ("MoveFile failed; code 3"). Found by the 10d install test. }
const
  MaxInstallDirLength = 140;
  WebView2Key = 'Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';

{ Same check as desktop_web/app.py: the runtime's version under one of three keys. }
function HasVersion(Root: Integer; Key: String): Boolean;
var
  Version: String;
begin
  Result := RegQueryStringValue(Root, Key, 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0');
end;

function RelaunchAfterUpdate: Boolean;
begin
  Result := ExpandConstant('{param:RELAUNCH|0}') = '1';
end;

function NeedsWebView2: Boolean;
begin
  Result := not (HasVersion(HKLM, 'SOFTWARE\WOW6432Node\' + WebView2Key) or
                 HasVersion(HKLM, 'SOFTWARE\' + WebView2Key) or
                 HasVersion(HKCU, 'Software\' + WebView2Key));
  if Result then
    Log('WebView2 Runtime not found: it will be installed.')
  else
    Log('WebView2 Runtime found: nothing to install.');
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = wpSelectDir) and (Length(WizardDirValue) > MaxInstallDirLength) then
  begin
    MsgBox('This folder path is too long for Windows (' + IntToStr(Length(WizardDirValue)) +
           ' characters; the limit for JobLens is ' + IntToStr(MaxInstallDirLength) + ').' + #13#10#13#10 +
           'Please choose a shorter folder, for example the default one.',
           mbError, MB_OK);
    Result := False;
  end;
end;

{ Runs after the program files are removed. Asks before deleting user data. }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
#ifdef TestBuild
  { A test build never deletes data: it shares %LOCALAPPDATA%\JobLens with a real install. }
  Exit;
#endif
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{localappdata}\JobLens');
    if DirExists(DataDir) and not UninstallSilent then
    begin
      if MsgBox('Do you want to KEEP your JobLens data?' + #13#10#13#10 +
                'This is your job tracker, approved cover notes, copies of your resumes ' +
                'and your settings, in:' + #13#10 + DataDir + #13#10#13#10 +
                'Yes  = keep it (handy if you reinstall later)' + #13#10 +
                'No   = delete it permanently',
                mbConfirmation, MB_YESNO) = IDNO then
        DelTree(DataDir, True, True, True);
    end;
  end;
end;
