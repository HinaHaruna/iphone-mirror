# build_uxplay.ps1
# Build UxPlay on Windows with MSYS2 (UCRT64) and copy uxplay.exe plus every DLL,
# GStreamer plugin and helper it needs into .\bin\ so the GUI can run it standalone.
#
# Requirements:
#   1) MSYS2            https://www.msys2.org/   (default install path C:\msys64)
#   2) Bonjour SDK for Windows v3.0 - either installed at "C:\Program Files\Bonjour SDK",
#      or its Include\ and Lib\ folders copied into .\bonjour_sdk\  (see BUILD_WINDOWS.md)
#
# Usage:
#   Right-click -> Run with PowerShell
#   or: powershell -ExecutionPolicy Bypass -File .\build_uxplay.ps1
#
#   -SkipBuild        only re-copy uxplay.exe + runtime DLLs/plugins into bin\ (no pacman/git/compile)
#   -OutDir <path>    bundle into another folder instead of .\bin\
#
# (This file is kept ASCII-only on purpose: Windows PowerShell 5.1 misreads UTF-8 without BOM.)

param(
    [switch]$SkipBuild,
    [string]$OutDir
)

$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$BinDir     = if ($OutDir) { [IO.Path]::GetFullPath($OutDir) } else { Join-Path $ScriptRoot "bin" }
$BuildDir   = Join-Path $ScriptRoot "build_uxplay"
$UxPlayRepo = "https://github.com/FDH2/UxPlay.git"

function ConvertTo-MsysPath([string]$p) {
    $p = $p -replace '\\', '/'
    if ($p -match '^([A-Za-z]):/(.*)$') {
        return "/$($Matches[1].ToLower())/$($Matches[2])"
    }
    return $p
}

# Run a bash snippet inside MSYS2. The snippet goes through a temp .sh file (LF endings)
# instead of "bash -lc": Windows PowerShell 5.1 mangles embedded double quotes in native
# arguments, which breaks any path containing spaces.
function Invoke-Msys([string]$Script, [switch]$AllowFail) {
    $tmp = Join-Path $env:TEMP ("uxplay_build_" + [guid]::NewGuid().ToString("N") + ".sh")
    [IO.File]::WriteAllText($tmp, ($Script -replace "`r`n", "`n"))
    try {
        & $Bash -l (ConvertTo-MsysPath $tmp) | Out-Host
        $code = $LASTEXITCODE
    } finally {
        Remove-Item $tmp -ErrorAction SilentlyContinue
    }
    if ($code -ne 0 -and -not $AllowFail) {
        throw "MSYS2 step failed (exit code $code). See the output above."
    }
}

# 1. Locate MSYS2 --------------------------------------------------------------
$Msys2Root = @("C:\msys64", "D:\msys64", "$env:USERPROFILE\msys64") |
    Where-Object { Test-Path "$_\usr\bin\bash.exe" } | Select-Object -First 1
if (-not $Msys2Root) {
    Write-Host "[!] MSYS2 not found. Install it from https://www.msys2.org/ first," -ForegroundColor Red
    Write-Host "    open 'MSYS2 UCRT64' once, then run this script again."
    exit 1
}
Write-Host "[*] Using MSYS2 at: $Msys2Root" -ForegroundColor Cyan

$Bash = "$Msys2Root\usr\bin\bash.exe"
$env:MSYSTEM          = "UCRT64"
$env:CHERE_INVOKING   = "1"
$env:UXP_BUILD        = ConvertTo-MsysPath $BuildDir
$env:UXP_BIN          = ConvertTo-MsysPath $BinDir
$env:UXP_REPO         = $UxPlayRepo

if (-not $SkipBuild) {

# 2. Locate the Bonjour SDK (needed to compile; the runtime uses the Bonjour service) ---
$BonjourCandidates = @()
if ($env:BONJOUR_SDK_HOME) { $BonjourCandidates += $env:BONJOUR_SDK_HOME }
$BonjourCandidates += (Join-Path $ScriptRoot "bonjour_sdk")
$BonjourCandidates += "C:\Program Files\Bonjour SDK"
$BonjourSdk = $BonjourCandidates |
    Where-Object { (Test-Path (Join-Path $_ "Include\dns_sd.h")) -and (Test-Path (Join-Path $_ "Lib\x64\dnssd.lib")) } |
    Select-Object -First 1
if (-not $BonjourSdk) {
    Write-Host "[!] Bonjour SDK not found (need Include\dns_sd.h and Lib\x64\dnssd.lib)." -ForegroundColor Red
    Write-Host "    Install 'Bonjour SDK for Windows v3.0', or copy its Include\ and Lib\ folders to:"
    Write-Host "    $(Join-Path $ScriptRoot 'bonjour_sdk')"
    exit 1
}
Write-Host "[*] Using Bonjour SDK at: $BonjourSdk" -ForegroundColor Cyan

$env:BONJOUR_SDK_HOME = $BonjourSdk -replace '\\', '/'

# 3. Toolchain + dependencies --------------------------------------------------
Write-Host "[*] Updating MSYS2 and installing dependencies (slow the first time)..." -ForegroundColor Cyan
Invoke-Msys "pacman -Syu --noconfirm" -AllowFail
Invoke-Msys @'
pacman -S --needed --noconfirm \
  git \
  mingw-w64-ucrt-x86_64-toolchain \
  mingw-w64-ucrt-x86_64-cmake \
  mingw-w64-ucrt-x86_64-ninja \
  mingw-w64-ucrt-x86_64-pkgconf \
  mingw-w64-ucrt-x86_64-openssl \
  mingw-w64-ucrt-x86_64-libplist \
  mingw-w64-ucrt-x86_64-gstreamer \
  mingw-w64-ucrt-x86_64-gst-plugins-base \
  mingw-w64-ucrt-x86_64-gst-plugins-good \
  mingw-w64-ucrt-x86_64-gst-plugins-bad \
  mingw-w64-ucrt-x86_64-gst-plugins-ugly \
  mingw-w64-ucrt-x86_64-gst-libav
'@

# 4. Get / update the UxPlay source -------------------------------------------
if (-not (Test-Path (Join-Path $BuildDir ".git"))) {
    Write-Host "[*] Cloning UxPlay source..." -ForegroundColor Cyan
    Invoke-Msys 'git clone --depth=1 "$UXP_REPO" "$UXP_BUILD"'
} else {
    Write-Host "[*] UxPlay source found - pulling updates" -ForegroundColor Cyan
    Invoke-Msys 'cd "$UXP_BUILD" && git pull --ff-only' -AllowFail
}

# 5. Build -----------------------------------------------------------------------
Write-Host "[*] Building UxPlay (UCRT64, Release)..." -ForegroundColor Cyan
Invoke-Msys @'
set -e
cd "$UXP_BUILD"
rm -rf build
mkdir build && cd build
cmake -G Ninja -DCMAKE_BUILD_TYPE=Release ..
ninja
'@

if (-not (Test-Path (Join-Path $BuildDir "build\uxplay.exe"))) {
    Write-Host "[!] Build finished but uxplay.exe is missing - check the log above." -ForegroundColor Red
    exit 1
}

} # end if (-not $SkipBuild)

$UxPlayExe = Join-Path $BuildDir "build\uxplay.exe"
if (-not (Test-Path $UxPlayExe)) {
    Write-Host "[!] $UxPlayExe not found - run without -SkipBuild first." -ForegroundColor Red
    exit 1
}

# 6. Bundle uxplay.exe + runtime into bin\ -----------------------------------------
Write-Host "[*] Copying uxplay.exe, GStreamer plugins and all dependent DLLs to bin\ ..." -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
Invoke-Msys @'
set -e
GST_LIB=/ucrt64/lib/gstreamer-1.0
GST_HELPERS=/ucrt64/libexec/gstreamer-1.0
mkdir -p "$UXP_BIN/gstreamer-1.0" "$UXP_BIN/gst-helpers"

cp -f "$UXP_BUILD/build/uxplay.exe" "$UXP_BIN/"
cp -f "$GST_LIB"/*.dll "$UXP_BIN/gstreamer-1.0/"
# plugin scanner lets GStreamer load the bundled plugins without MSYS2 on PATH
for h in gst-plugin-scanner.exe gst-ptp-helper.exe; do
  if [ -f "$GST_HELPERS/$h" ]; then cp -f "$GST_HELPERS/$h" "$UXP_BIN/gst-helpers/"; fi
done

# every DLL from /ucrt64/bin that uxplay.exe, any plugin, or the scanner links against
{
  ldd "$UXP_BUILD/build/uxplay.exe"
  for f in "$GST_LIB"/*.dll "$GST_HELPERS/gst-plugin-scanner.exe"; do
    ldd "$f" 2>/dev/null || true
  done
} | awk '$3 ~ /^\/ucrt64\/bin\// { print $3 }' | sort -u | while read -r dll; do
  cp -u "$dll" "$UXP_BIN/"
done

# stale plugin cache from an older build would hide new plugins
rm -f "$UXP_BIN/gst-registry.bin"
echo "bin/ now holds $(ls "$UXP_BIN" | wc -l) entries, $(ls "$UXP_BIN/gstreamer-1.0" | wc -l) plugins"
'@

Write-Host ""
Write-Host "[OK] Done: $BinDir\uxplay.exe" -ForegroundColor Green
Write-Host "     Start the GUI with run.bat"
