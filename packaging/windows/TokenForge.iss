; TokenForge native Windows installer - keeps existing default file applications.
#define AppName "TokenForge"
#define AppVersion "0.3.1"

[Setup]
AppId={{6CE03228-2A4A-45E3-B5E4-30C3C380B948}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=TerranexTech
DefaultDirName={localappdata}\Programs\TokenForge
DefaultGroupName=TokenForge
OutputDir=..\..\desktop\dist\installers
OutputBaseFilename=TokenForge-Setup-Windows-x64
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ChangesAssociations=yes
UninstallDisplayIcon={app}\TokenForge.exe
WizardStyle=modern

[Files]
Source: "..\..\desktop\dist\TokenForge\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Icons]
Name: "{autoprograms}\TokenForge"; Filename: "{app}\TokenForge.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\TokenForge"; Filename: "{app}\TokenForge.exe"; Tasks: desktopicon

[Registry]
; The Explorer right-click option is explicit; .txt/.pdf defaults remain unchanged.
Root: HKCU; Subkey: "Software\Classes\Applications\TokenForge.exe\shell\open\command"; ValueType: string; ValueData: """{app}\TokenForge.exe"" ""%1"""; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\*\shell\TokenForgeOptimize"; ValueType: string; ValueName: ""; ValueData: "Optimize with TokenForge"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\*\shell\TokenForgeOptimize\command"; ValueType: string; ValueData: """{app}\TokenForge.exe"" ""%1"""; Flags: uninsdeletekey

[Run]
Filename: "{app}\TokenForge.exe"; Description: "Launch TokenForge"; Flags: nowait postinstall skipifsilent
