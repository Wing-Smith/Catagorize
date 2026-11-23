; ============================================================
; Catagorize 安装脚本（Inno Setup 7 适配）
; 依赖的 7 代特性：
;   - WizardStyle=modern dynamic   向导跟随 Windows 明暗模式（6.6+）
;   - WizardImageFile 支持 PNG     向导图无需转 BMP（6.5.2+）
;   - RedirectionGuard             Windows 重定向防护（6.7+）
; 编译前先运行：scripts\build_nuitka.ps1
; 产物目录：..\Release\Catagorize（含 Catagorize.exe）
; ============================================================

#define MyAppName      "Catagorize"
#define MyAppVersion   "0.1.8"
#define MyAppPublisher "Wing North Studio"
#define MyAppURL       "https://github.com/Wing-Smith/Catagorize"
#define MyAppExe       "Catagorize.exe"
#define MyAppId        "{43E8EEC5-775B-4017-B07B-9A01D39E15A8}"

[Setup]
; 固定 AppId：升级安装时覆盖旧版本而不是并存
AppId={{#MyAppId}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases

; 目标系统：Windows 10 1809+（Mica 毛玻璃的最低要求）
MinVersion=10.0.17763
; 仅 64 位 Windows
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Windows 重定向防护（DLL 劫持缓解，Inno 6.7+）
RedirectionGuard=yes

; 用户级安装，不需要管理员权限（写入 %LOCALAPPDATA%\Programs）
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; 注意：不使用 SourceDir，否则 LicenseFile/OutputDir/SetupIconFile 等
; 所有相对路径都会改为相对 ..\Release\Catagorize 解析（Inno 行为）。
; 保持脚本所在目录为基准，[Files] 段直接指向 ..\Release\Catagorize。
OutputDir=..\Release\installer
OutputBaseFilename=Catagorize-Setup-{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; 向导风格：modern + 跟随系统明暗模式
WizardStyle=modern dynamic

; 向导图片（预留位——素材到位后放 PNG 到本目录，取消注释即可）
;WizardImageFile=setup_banner.png
;WizardSmallImageFile=setup_small.png

; 图标与版本信息（写入安装程序属性；图标 = 应用图标）
SetupIconFile=..\app\assets\app.ico
UninstallDisplayIcon={app}\{#MyAppExe}
VersionInfoVersion={#MyAppVersion}
VersionInfoTextVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=Catagorize Setup
VersionInfoCopyright=Copyright (c) 2026 Wing North Studio
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
VersionInfoOriginalFileName=Catagorize-Setup-{#MyAppVersion}.exe

; 用户协议（安装向导第一步显示）
LicenseFile=EULA.rtf

; 关闭运行中的实例再装
CloseApplications=yes
CloseApplicationsFilter={#MyAppExe}

DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

[Languages]
; 安装界面语言由用户在向导第一步选择（官方中文语言包随 Inno 自带）
Name: "chs"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "en";  MessagesFile: "compiler:Default.isl"

[Messages]
; 向导底部提示语（两种语言都显示，版本号随 #define 自动更新）
chs.BeveledLabel=Catagorize v{#MyAppVersion} ©{#MyAppPublisher} 2026
en.BeveledLabel=Catagorize v{#MyAppVersion} ©{#MyAppPublisher} 2026

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; standalone 模式整个文件夹原样安装
Source: "..\Release\Catagorize\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; AppUserModelID 必须与应用内 WindowsToaster("Catagorize") 完全一致，
; 系统通知才能显示应用图标与名称
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; AppUserModelID: "Catagorize"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon; AppUserModelID: "Catagorize"

[Run]
; 装完可选直接启动
Filename: "{app}\{#MyAppExe}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 可选：卸载时清理用户数据（取消注释生效；便携模式的 CatagorizeData 在安装目录，会被自动移除）
;Type: filesandordirs; Name: "{appdata}\Wing North Studio\Catagorize"
