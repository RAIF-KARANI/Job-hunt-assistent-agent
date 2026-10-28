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

#ifndef AppVersion
  #define AppVersion "0.0.0-dev"
#endif

[Setup]
; AppId identifies JobLens to Windows across versions: never change it, or an
; upgrade would install side by side instead of replacing the old version.
AppId={{6B0E5A3C-2F1D-4C8B-9E7A-4A1F2D3C5B6E}
AppName=JobLens
AppVersion={#AppVersion}
AppVerName=JobLens {#AppVersion}
AppPublisher=Raif Karani
AppPublisherURL=https://github.com/RAIF-KARANI/Job-hunt-assistent-agent
DefaultDirName={localappdata}\Programs\JobLens
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=JobLens-Setup-{#AppVersion}
SetupIconFile=..\assets\joblens.ico
UninstallDisplayIcon={app}\JobLens.exe
UninstallDisplayName=JobLens
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Close a running JobLens before installing / uninstalling.
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
; The whole PyInstaller folder: JobLens.exe + _internal\
Source: "..\dist\JobLens\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\JobLens"; Filename: "{app}\JobLens.exe"
Name: "{autodesktop}\JobLens"; Filename: "{app}\JobLens.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\JobLens.exe"; Description: "Launch JobLens"; Flags: nowait postinstall skipifsilent

[Code]
{ Windows paths are limited to 260 characters. JobLens' deepest file adds
  ~105 characters to the install folder, so a very deep folder would fail
  half-way ("MoveFile failed; code 3"). Found by the 10d install test. }
const
  MaxInstallDirLength = 140;

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
