; CapyRunner Windows installer (Inno Setup 6). Built by .github/workflows/build.yml:
;   iscc /DAppVersion=0.4.0 packaging\capyrunner.iss
; Installs for the current user only: no administrator password, no UAC prompt.
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6F3B1C2E-8A4D-4E5F-9B7A-CA9E7A11C0DE}
AppName=CapyRunner
AppVersion={#AppVersion}
AppVerName=CapyRunner {#AppVersion}
AppPublisher=Devjr
AppCopyright=Developed by Devjr
VersionInfoCompany=Devjr
VersionInfoDescription=CapyRunner setup
DefaultDirName={localappdata}\Programs\CapyRunner
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=CapyRunner-Setup-x64
SetupIconFile=capyrunner.ico
UninstallDisplayIcon={app}\CapyRunner.exe
UninstallDisplayName=CapyRunner
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Windows 10 version 1809 or newer (Qt 6 needs it), and every Windows 11
MinVersion=10.0.17763
WizardStyle=modern
CloseApplications=force
RestartApplications=no

[Messages]
WelcomeLabel2=This puts Primo, the Capytech mascot, on your desktop.%n%nHe runs along the bottom of the screen, keeps your tasks and notes, sits at his desk while you work, dances to your music and rides dragons across the screen.%n%nDeveloped by Devjr. No administrator rights needed.

[Tasks]
Name: "autostart"; Description: "Start CapyRunner when I sign in to Windows"
Name: "desktopicon"; Description: "Add a shortcut to my desktop"; Flags: unchecked

[InstallDelete]
; files of an older version that are no longer shipped
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\CapyRunner\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{userprograms}\CapyRunner"; Filename: "{app}\CapyRunner.exe"; Comment: "Primo, the Capytech mascot"
Name: "{userdesktop}\CapyRunner"; Filename: "{app}\CapyRunner.exe"; Tasks: desktopicon

[Registry]
; same value the app writes for Settings > "Start when I log in"
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "CapyRunner"; \
  ValueData: """{app}\CapyRunner.exe"""; Tasks: autostart; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "CapyRunner"; \
  Flags: deletevalue uninsdeletevalue; Tasks: not autostart

[Run]
Filename: "{app}\CapyRunner.exe"; Description: "Start CapyRunner now"; Flags: nowait postinstall skipifsilent
; an automatic update (the app runs the new setup with /SILENT): start the new version straight away
Filename: "{app}\CapyRunner.exe"; Flags: nowait; Check: WizardSilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/IM CapyRunner.exe /F"; Flags: runhidden; RunOnceId: "StopCapyRunner"
