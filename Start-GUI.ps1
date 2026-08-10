$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Virtual environment missing. Run .\Setup-Jarvis.ps1 first."
}

Set-Location $ProjectRoot
$Ffmpeg = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter ffmpeg.exe -ErrorAction SilentlyContinue | Select-Object -First 1
if ($Ffmpeg) { $env:Path = "$($Ffmpeg.DirectoryName);$env:Path" }
& $Python "GUI.py"
