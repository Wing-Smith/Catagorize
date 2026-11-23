# ==========================================
# Catagorize Nuitka Build Script (PowerShell)
# Description: Python → C → 原生 exe（standalone 文件夹模式，MSVC 编译）
# Encoding: UTF-8 with BOM
# 用法: powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\build_nuitka.ps1"
# ==========================================
$ErrorActionPreference = "Continue"
$baseDir = Split-Path -Parent $PSScriptRoot
Set-Location $baseDir

$pythonPath = Join-Path $baseDir ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonPath)) {
    Write-Host "[ERROR] 未找到 $pythonPath，请先创建虚拟环境" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# 从 config.py 读取版本号（单一来源）
$version = & $pythonPath -c "from app.core.config import APP_VERSION; print(APP_VERSION)" 2>$null
if (-not $version) { $version = "0.0.0" }
$version = $version.Trim()
Write-Host "Building Catagorize v$version" -ForegroundColor Cyan

# ---------------- Windows Defender 排除项（每次构建自动保证，幂等） ----------------
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
$exclusionPaths = @(
    (Join-Path $baseDir "dist_nuitka"),
    (Join-Path $baseDir "Release"),
    (Join-Path $env:LOCALAPPDATA "Nuitka")
)
if ($isAdmin) {
    foreach ($p in $exclusionPaths) {
        try {
            Add-MpPreference -ExclusionPath $p -ErrorAction Stop
            Write-Host "  [OK] Defender exclusion: $p" -ForegroundColor DarkGray
        } catch {
            Write-Host "  [WARN] Defender exclusion failed: $p -- $($_.Exception.Message)" -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "  [WARN] Not running as administrator - skipped Defender exclusions." -ForegroundColor Yellow
    Write-Host "         (Compile may be slow from real-time scanning.)" -ForegroundColor Yellow
}

# ---------------- 构建 ----------------
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Building Catagorize v$version (Nuitka)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 先跑测试，失败不打包（--basetemp 避开系统 Temp 的 junction 权限坑）
& $pythonPath -m pytest tests/ -q --basetemp=.pytest-tmp
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] 测试未通过，中止打包" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# 清理 Nuitka 缓存与旧产物
foreach ($d in @('dist_nuitka', 'app.build', 'app.dist', '.pytest-tmp')) {
    if (Test-Path $d) {
        Remove-Item -Recurse -Force $d -ErrorAction SilentlyContinue
        Write-Host "  Cleaned: $d" -ForegroundColor DarkGray
    }
}
if (Test-Path 'nuitka-crash-report.xml') {
    Remove-Item -Force 'nuitka-crash-report.xml' -ErrorAction SilentlyContinue
}
$output = "Release\Catagorize"
if (Test-Path $output) {
    Remove-Item -Recurse -Force $output -ErrorAction SilentlyContinue
    Write-Host "  Cleaned old folder: $output" -ForegroundColor DarkGray
}

# 编译参数（数组形式，避免引号转义问题）
$cmdArgs = @(
    "-m", "nuitka",
    "--standalone", "--remove-output", "--assume-yes-for-downloads", "--msvc=latest",
    "--jobs=14", "--lto=no",
    "--enable-plugin=pyside6",
    "--windows-console-mode=disable",
    "--windows-icon-from-ico=app/assets/app.ico",
    "--file-version=$version", "--product-version=$version",
    "--company-name=Wing North Studio",
    "--product-name=Catagorize",
    "--file-description=Catagorize - local-first folder organizer",
    "--copyright=Copyright (c) 2026 Wing North Studio",
    "--output-filename=Catagorize.exe", "--output-dir=dist_nuitka",
    "--include-package=app",
    "--include-package-data=qfluentwidgets", "--include-package-data=PySide6",
    "--include-data-dir=app/assets=app/assets",
    "app/main.py"
)
Write-Host ("  Command: " + ($cmdArgs -join " ")) -ForegroundColor DarkGray

# 直接在当前终端构建：进度条与彩色输出均为原生行为。
# 注意：不要对输出做管道/文件重定向 —— 会导致进度条与颜色消失（已踩坑回滚）。
Write-Host "  Compiling... (expect 10-30 min)" -ForegroundColor Yellow
& $pythonPath @cmdArgs
$exitCode = $LASTEXITCODE
Write-Host ""
if ($exitCode -ne 0) {
    Write-Host "[FAIL] Build failed with exit code $exitCode" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit $exitCode
}
Write-Host "[OK] Build succeeded." -ForegroundColor Green

# standalone 产物是整个文件夹：dist_nuitka\main.dist → Release\Catagorize
if (-not (Test-Path "Release")) { New-Item -ItemType Directory -Path "Release" | Out-Null }
Copy-Item "dist_nuitka\main.dist" $output -Recurse -Force
Write-Host "  [OK] $output\Catagorize.exe" -ForegroundColor Green

# 刷新图标缓存
Write-Host ""
ie4uinit.exe -show
Write-Host "  [OK] Icon cache refreshed" -ForegroundColor Green

Write-Host ""
Write-Host "  Output: $baseDir\Release\Catagorize" -ForegroundColor White
