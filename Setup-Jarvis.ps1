$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    py -3.11 -m venv .venv
}

& ".venv\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt whisper_mic python-dotenv

if (Get-Command ollama -ErrorAction SilentlyContinue) {
    & ollama pull nomic-embed-text
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}

Write-Host "Setup complete. Start with: .\Start-Jarvis.ps1"
Write-Host "Optional startup at sign-in: .\Install-Startup.ps1"
