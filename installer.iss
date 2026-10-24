; MultiPost installer - Inno Setup script.
; The wizard ALWAYS shows the destination-folder page: the user picks where
; MultiPost is installed (default C:\BOT\MultiPost).

#define MyAppName "MultiPost"
#define MyAppVersion "1.7.0"
#define MyAppExeName "MultiPost.exe"

[Setup]
AppId={{8F3A2C41-6B7D-4E9A-9C2B-1D5E7A0B3F66}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=ZGG.ID
DefaultDirName={sd}\BOT\MultiPost
DefaultGroupName={#MyAppName}
DisableDirPage=no
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=installer-output
OutputBaseFilename=MultiPost-Setup
CloseApplications=yes
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#MyAppName} {#MyAppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Dirs]
; App data (accounts + browser sessions) lives next to the exe and must stay
; writable even if the user installs under Program Files.
Name: "{app}\data"; Permissions: users-full

[Files]
Source: "dist\MultiPost\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Buat shortcut di Desktop"; GroupDescription: "Shortcut:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Jalankan MultiPost sekarang"; Flags: nowait postinstall skipifsilent
