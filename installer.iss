#define MyAppName "J.A.R.V.I.S Mark 7"
#define MyAppVersion "7.0.0"
#define MyAppPublisher "PHENOMVALENCE"
#define MyAppExeName "JARVIS-Mark-7.exe"

[Setup]
AppId={{8E4B839F-CA16-496B-B624-76A1C86FF0E8}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\JARVIS
DefaultGroupName={#MyAppName}
OutputDir=installer-output
OutputBaseFilename=JARVIS-Mark-7-Setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "startup"; Description: "Start J.A.R.V.I.S when I sign in"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "JARVIS Mark 7"; ValueData: """{app}\{#MyAppExeName}"""; Tasks: startup; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch J.A.R.V.I.S"; Flags: nowait postinstall skipifsilent
