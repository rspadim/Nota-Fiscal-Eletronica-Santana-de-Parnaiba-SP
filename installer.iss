; Instalador do Sistema de NFS-e - Santana de Parnaiba
; Requer Inno Setup 6: https://jrsoftware.org/isdl.php
;
; Compilar (depois do PyInstaller):
;   iscc installer.iss
;
; Espera a pasta dist\nfse-santana\ gerada por: pyinstaller nfse.spec --noconfirm

#define AppName "Sistema NFS-e Santana de Parnaiba"
#define AppShortName "NFS-e Santana"
#define AppVersion "1.0.0"
#define AppPublisher "Spadim"
#define AppExe "nfse-santana.exe"
#define PastaBuild "dist\nfse-santana"

[Setup]
AppId={{8F2A1C64-3E7B-4B9A-9E52-6D1A4C0B7E31}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\NFS-e Santana
DefaultGroupName={#AppShortName}
DisableProgramGroupPage=yes
OutputDir=dist\instalador
OutputBaseFilename=nfse-santana-{#AppVersion}-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; instala sem pedir administrador (pasta do usuario)
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na area de trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked

[Files]
Source: "{#PastaBuild}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; na primeira instalacao o config nasce do exemplo; atualizacoes nao sobrescrevem
Source: "config.json.exemplo"; DestDir: "{app}"; DestName: "config.json"; Flags: onlyifdoesntexist
Source: "config.json.exemplo"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppShortName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"
Name: "{group}\Configuracao (config.json)"; Filename: "{app}\config.json"
Name: "{group}\Pasta de dados"; Filename: "{app}"
Name: "{group}\Desinstalar {#AppShortName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppShortName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Description: "Executar o sistema agora"; Flags: nowait postinstall skipifsilent
