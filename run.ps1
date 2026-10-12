# TPA Antigravity 2.0 - Launcher & Auto-Setup Script

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "🚀 TPA Poster Sender - Auto-Setup & Launcher" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

# Force TLS 1.2 / TLS 1.3 protocol so Windows PowerShell 5.1 can download from modern HTTPS servers
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    if ([Net.SecurityProtocolType]::Tls13) {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls13
    }
} catch {}

# Ensure local bin directories are in PATH for this execution
$localBinPath = Join-Path $env:USERPROFILE ".local\bin"
$cargoBinPath = Join-Path $env:USERPROFILE ".cargo\bin"
if (-not ($env:PATH -split ';' -contains $localBinPath)) {
    $env:PATH = "$localBinPath;" + $env:PATH
}
if (-not ($env:PATH -split ';' -contains $cargoBinPath)) {
    $env:PATH = "$cargoBinPath;" + $env:PATH
}

# 1. Check for 'uv' or system Python
Write-Host "[1/4] Checking Python / Package Manager..." -ForegroundColor Gray
$uvAvailable = Get-Command uv -ErrorAction SilentlyContinue

if (-not $uvAvailable) {
    Write-Host "👉 'uv' is not detected. Downloading portable installer..." -ForegroundColor Yellow
    try {
        $installerContent = (Invoke-WebRequest -Uri "https://astral.sh/uv/install.ps1" -UseBasicParsing).Content
        Invoke-Expression $installerContent
        $env:PATH = "$localBinPath;$cargoBinPath;" + $env:PATH
        $uvAvailable = Get-Command uv -ErrorAction SilentlyContinue
    } catch {
        Write-Host "⚠️ Astral download notice: $($_.Exception.Message)" -ForegroundColor Yellow
        $wingetAvailable = Get-Command winget -ErrorAction SilentlyContinue
        if ($wingetAvailable) {
            Write-Host "👉 Attempting winget install for uv..." -ForegroundColor Yellow
            winget install --id=astral-sh.uv -e --accept-source-agreements --accept-package-agreements
            $env:PATH = "$localBinPath;$cargoBinPath;" + $env:PATH
            $uvAvailable = Get-Command uv -ErrorAction SilentlyContinue
        }
    }
}

$venvPath = Join-Path $PSScriptRoot ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"

# If uv is available, use uv
if ($uvAvailable) {
    Write-Host "✅ Using 'uv' fast package manager!" -ForegroundColor Green
    if (-not (Test-Path $venvPath)) {
        Write-Host "[2/4] Initializing Python 3.12 environment..." -ForegroundColor Yellow
        uv venv .venv --python 3.12
    }
    Write-Host "[3/4] Installing / Verifying dependencies..." -ForegroundColor Gray
    & uv pip install -r requirements.txt
    Write-Host "[4/4] Launching TPA Poster Sender in Chrome..." -ForegroundColor Cyan
    & uv run streamlit run app.py
} else {
    # Fallback to system Python if uv couldn't be installed
    Write-Host "👉 Checking for system Python..." -ForegroundColor Yellow
    $pyCmd = $null
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $pyCmd = "python"
    } elseif (Get-Command py -ErrorAction SilentlyContinue) {
        $pyCmd = "py"
    }

    if (-not $pyCmd) {
        Write-Host "❌ Python is not detected on this computer." -ForegroundColor Red
        Write-Host "👉 Please install Python (visit https://www.python.org/downloads/ and check 'Add python.exe to PATH')." -ForegroundColor Yellow
        Write-Host "Press any key to exit..."
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        Exit 1
    }

    Write-Host "✅ Found system Python ($pyCmd)!" -ForegroundColor Green
    if (-not (Test-Path $venvPath)) {
        Write-Host "[2/4] Creating virtual environment (.venv)..." -ForegroundColor Yellow
        & $pyCmd -m venv .venv
    }
    Write-Host "[3/4] Installing dependencies via pip..." -ForegroundColor Gray
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -r requirements.txt
    Write-Host "[4/4] Launching TPA Poster Sender in Chrome..." -ForegroundColor Cyan
    & $venvPython -m streamlit run app.py
}
