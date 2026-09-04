[Setup]
AppName=PokéAbilityRando
AppVersion=1.0.5
AppPublisher=Zenshu
DefaultDirName={userappdata}\Programs\PokéAbilityRando
DefaultGroupName=PokéAbilityRando
; Prevents requesting Administrator privileges during setup
PrivilegesRequired=lowest
; Embeds the installer icon for the Setup.exe file itself
SetupIconFile=PokéAbilityRando.ico
UninstallDisplayIcon={app}\PokéAbilityRando.exe
OutputBaseFilename=PokéAbilityRando_Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; Automatically close running instances during updates
CloseApplications=yes
CloseApplicationsFilter=*.exe

[Files]
; Copy all compiled files from the PyInstaller output folder
Source: "dist\PokéAbilityRando\*.*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\PokéAbilityRando"; Filename: "{app}\PokéAbilityRando.exe"; IconFilename: "{app}\PokéAbilityRando.exe"
Name: "{userdesktop}\PokéAbilityRando"; Filename: "{app}\PokéAbilityRando.exe"; IconFilename: "{app}\PokéAbilityRando.exe"

[UninstallDelete]
; Clean up generated configuration files and empty installation directory on removal
Type: files; Name: "{app}\blacklist.txt"
Type: files; Name: "{app}\wildcards.txt"
Type: dirifempty; Name: "{app}"

[Run]
; Option to launch the application immediately after setup completes
Filename: "{app}\PokéAbilityRando.exe"; Description: "{cm:LaunchProgram,PokéAbilityRando}"; Flags: nowait postinstall skipifsilent