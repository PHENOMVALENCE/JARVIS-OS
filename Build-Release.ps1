$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
Set-Location $ProjectRoot

if (-not (Test-Path $Python)) { throw "Run .\Setup-Jarvis.ps1 first." }
& $Python -m pip install -r requirements-dev.txt
& $Python -m unittest discover -s tests -q
& $Python -m PyInstaller --noconfirm --clean jarvis.spec

$Executable = Join-Path $ProjectRoot "dist\JARVIS-Mark-7.exe"
if (-not (Test-Path $Executable)) { throw "Release executable was not created." }

if ($env:JARVIS_SIGN_CERTIFICATE) {
    $SignTool = Get-Command signtool.exe -ErrorAction Stop
    & $SignTool.Source sign /f $env:JARVIS_SIGN_CERTIFICATE /p $env:JARVIS_SIGN_PASSWORD /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 $Executable
}
Write-Host "Release ready: $Executable"
