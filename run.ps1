# TPA Antigravity 2.0 - Launcher & Auto-Setup Script

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "🚀 TPA Poster Sender - Auto-Setup & Launcher" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

# Force TLS 1.2 protocol for secure web downloads in PowerShell
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
} catch {}

# Ensure local bin directories are in PATH
$localBinPath = Join-Path $env:USERPROFILE ".local\bin"
$cargoBinPath = Join-Path $env:USERPROFILE ".cargo\bin"
if (-not ($env:PATH -split ';' -contains $localBinPath)) {
    $env:PATH = "$localBinPath;" + $env:PATH
}
if (-not ($env:PATH -split ';' -contains $cargoBinPath)) {
    $env:PATH = "$cargoBinPath;" + $env:PATH
}

function Test-PythonWorks($cmd) {
    try {
        $testOut = (& $cmd -c "print('OK')" 2>&1)
        return ($testOut -eq "OK")
    } catch {
        return $false
    }
}

# 1. Check for 'uv' or system Python
Write-Host "[1/4] Checking Python environment..." -ForegroundColor Gray
$uvAvailable = Get-Command uv -ErrorAction SilentlyContinue

if (-not $uvAvailable) {
    Write-Host "👉 'uv' not found. Trying quick install..." -ForegroundColor Yellow
    try {
        $installerContent = (Invoke-WebRequest -Uri "https://astral.sh/uv/install.ps1" -UseBasicParsing).Content
        Invoke-Expression $installerContent
        $env:PATH = "$localBinPath;$cargoBinPath;" + $env:PATH
        $uvAvailable = Get-Command uv -ErrorAction SilentlyContinue
    } catch {}
}

$venvPath = Join-Path $PSScriptRoot ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"

# If uv is available, use uv
if ($uvAvailable) {
    Write-Host "✅ Using 'uv' portable package manager!" -ForegroundColor Green
    if (-not (Test-Path $venvPath)) {
        Write-Host "[2/4] Initializing Python 3.12 environment..." -ForegroundColor Yellow
        uv venv .venv --python 3.12
    }
    Write-Host "[3/4] Installing / Verifying dependencies..." -ForegroundColor Gray
    & uv pip install -r requirements.txt
    Write-Host "[4/4] Launching TPA Poster Sender in Chrome..." -ForegroundColor Cyan
    & uv run streamlit run app.py
} else {
    # Check for real working system Python (skips dummy WindowsApps store alias)
    Write-Host "👉 Checking for installed Python..." -ForegroundColor Yellow
    $pyCmd = $null
    if (Test-PythonWorks "py") {
        $pyCmd = "py"
    } elseif (Test-PythonWorks "python") {
        $pyCmd = "python"
    }

    if (-not $pyCmd) {
        Write-Host "⚠️ Real Python is not yet installed on this PC." -ForegroundColor Yellow
        Write-Host "👉 Installing Python automatically via Windows Package Manager..." -ForegroundColor Cyan
        
        $wingetAvailable = Get-Command winget -ErrorAction SilentlyContinue
        if ($wingetAvailable) {
            winget install Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements
            # Refresh path
            $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH","User")
            if (Test-PythonWorks "python") { $pyCmd = "python" }
            elseif (Test-PythonWorks "py") { $pyCmd = "py" }
        }
    }

    if (-not $pyCmd) {
        Write-Host "==========================================================" -ForegroundColor Red
        Write-Host "❌ Python 3 is required to run the app on this computer." -ForegroundColor Red
        Write-Host "==========================================================" -ForegroundColor Red
        Write-Host "👉 1-Minute Fix: Opening the Python official download page..." -ForegroundColor Yellow
        Write-Host "👉 Please install it and MAKE SURE to check ☑️ 'Add python.exe to PATH'!" -ForegroundColor Yellow
        Write-Host "==========================================================" -ForegroundColor Red
        Start-Process "https://www.python.org/downloads/"
        Write-Host "Press any key to exit..."
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        Exit 1
    }

    Write-Host "✅ Found working Python ($pyCmd)!" -ForegroundColor Green
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
