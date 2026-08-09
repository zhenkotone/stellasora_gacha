#define MyAppName "星塔旅人数据工具"
#define MyAppVersion "1.1.6"
#define MyAppExeName "StellaSoraGachaTool.exe"

#ifndef MySourceExe
  #define MySourceExe "..\release\gitee\StellaSoraGachaTool.exe"
#endif
#ifndef MyOutputDir
  #define MyOutputDir "..\release\gitee"
#endif
#ifndef MyOutputBaseFilename
  #define MyOutputBaseFilename "StellaSoraGachaTool-Setup"
#endif

[Setup]
AppId={{B8E6C27A-53CE-47F7-9EA7-4383B5C56E63}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=zhen-z
AppPublisherURL=https://gitee.com/zhen-z/stellasora_gacha
DefaultDirName={localappdata}\StellaSoraGachaTool
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#MyOutputDir}
OutputBaseFilename={#MyOutputBaseFilename}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\assets\app_icon.ico
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={app}\{#MyAppExeName}
VersionInfoVersion=1.1.6.0
VersionInfoProductName={#MyAppName}
VersionInfoDescription={#MyAppName} 安装程序

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加选项："; Flags: unchecked

[Files]
Source: "{#MySourceExe}"; DestDir: "{app}"; DestName: "{#MyAppExeName}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent
