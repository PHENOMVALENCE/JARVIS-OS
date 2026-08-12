#requires -Version 5.1
<#
    Builds the distributable application.

    A frozen build can start and still fail the first time somebody speaks,
    because PyInstaller cannot see imports that happen inside functions. So
    this does not trust a successful build: it runs the frozen application's
    own import check before declaring success.
#>

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
Set-Location $ProjectRoot

function Write-Step($Text) { Write-Host "`n>> $Text" -ForegroundColor Cyan }
function Write-Ok($Text) { Write-Host "   $Text" -ForegroundColor Green }

if (-not (Test-Path $Python)) { throw "Run .\Setup-Jarvis.ps1 first." }

Write-Step "Installing build dependencies"
& $Python -m pip install -r requirements-dev.txt --quiet

Write-Step "Running the test suite"
& $Python -m unittest discover -s tests -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed. The build stops here." }
Write-Ok "Tests passed"

Write-Step "Building the application"
& $Python -m PyInstaller --noconfirm --clean jarvis.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }

$AppDir = Join-Path $ProjectRoot "dist\JARVIS"
$Executable = Join-Path $AppDir "JARVIS.exe"
if (-not (Test-Path $Executable)) { throw "The executable was not produced." }
$SizeMb = [math]::Round(((Get-ChildItem $AppDir -Recurse | Measure-Object Length -Sum).Sum / 1MB), 0)
Write-Ok "Built $Executable ($SizeMb MB)"

Write-Step "Verifying the frozen build can load every subsystem"
# Runs inside the frozen application, so it exercises the bundled interpreter
# and the collected binaries rather than the development environment.
$env:JARVIS_SELFTEST = "1"
& $Executable
$SelfTest = $LASTEXITCODE
Remove-Item Env:\JARVIS_SELFTEST
if ($SelfTest -ne 0) { throw "The frozen build failed its self-test. See the log in %LOCALAPPDATA%\JARVIS\logs." }
Write-Ok "Every subsystem imported inside the frozen build"

if ($env:JARVIS_SIGN_CERTIFICATE) {
    Write-Step "Signing"
    $SignTool = Get-Command signtool.exe -ErrorAction Stop
    & $SignTool.Source sign /f $env:JARVIS_SIGN_CERTIFICATE /p $env:JARVIS_SIGN_PASSWORD `
        /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 $Executable
    Write-Ok "Signed"
} else {
    Write-Host "   Not signed. Windows SmartScreen will warn on first run." -ForegroundColor Yellow
}

$Inno = Get-Command iscc.exe -ErrorAction SilentlyContinue
if ($Inno) {
    Write-Step "Building the installer"
    & $Inno.Source installer.iss
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed." }
    Write-Ok "Installer written to installer-output"
} else {
    Write-Host "   Inno Setup not found; skipping the installer." -ForegroundColor Yellow
    Write-Host "   Install it from jrsoftware.org to produce JARVIS-Setup-x64.exe." -ForegroundColor Yellow
}

Write-Host "`nRelease build complete." -ForegroundColor Green
