#requires -Version 5.1
<#
    Prepares a machine to run J.A.R.V.I.S hands-free.

    Installs dependencies, fetches the local language, embedding, wake word,
    and voice models, then hands over to the in-app wizard for the choices
    that need a person: microphone calibration, wake word, and startup.
#>

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

function Write-Step($Text) { Write-Host "`n>> $Text" -ForegroundColor Cyan }
function Write-Ok($Text) { Write-Host "   $Text" -ForegroundColor Green }
function Write-Warn($Text) { Write-Host "   $Text" -ForegroundColor Yellow }

Write-Step "Checking Python"
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    $python = Get-Command py -ErrorAction SilentlyContinue
    if (-not $python) { throw "Python 3.11 is required. Install it from python.org, then run this again." }
    py -3.11 -m venv .venv
}
$Python = ".venv\Scripts\python.exe"
Write-Ok ((& $Python --version) -join "")

Write-Step "Installing dependencies (this takes a few minutes the first time)"
& $Python -m pip install --upgrade pip setuptools wheel --quiet
& $Python -m pip install -r requirements.txt whisper_mic --quiet
Write-Ok "Dependencies installed"

Write-Step "Checking Ollama"
if (Get-Command ollama -ErrorAction SilentlyContinue) {
    $models = (& ollama list) -join "`n"
    if ($models -notmatch "gemma2:2b") { & ollama pull gemma2:2b }
    if ($models -notmatch "nomic-embed-text") { & ollama pull nomic-embed-text }
    Write-Ok "Language and embedding models ready"
} else {
    Write-Warn "Ollama was not found. Install it from https://ollama.com to run the assistant"
    Write-Warn "locally, then run: ollama pull gemma2:2b"
}

Write-Step "Downloading the offline voice and wake word"
& $Python -c @"
import sys
sys.path.insert(0, '.')
from pathlib import Path

try:
    from jarvis_os.speech import DEFAULT_PIPER_VOICE, PiperSpeech
    voice = PiperSpeech(DEFAULT_PIPER_VOICE, Path('models'))
    print('   offline voice ready' if voice.ensure_voice() else '   offline voice unavailable, will use the online voice')
except Exception as error:
    print(f'   offline voice unavailable: {error}')

try:
    import openwakeword.utils
    openwakeword.utils.download_models(['hey_jarvis'])
    print('   wake word ready')
except Exception as error:
    print(f'   wake word unavailable: {error}')
"@

Write-Step "Preparing configuration"
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }
Write-Ok "Configuration in place"

Write-Step "Verifying the installation"
& $Python Diagnose-Jarvis.py

Write-Host "`nSetup complete." -ForegroundColor Green
Write-Host "Start J.A.R.V.I.S with:  .\Start-Jarvis.ps1"
Write-Host "The first launch walks you through the microphone, voice, wake word, and startup."
