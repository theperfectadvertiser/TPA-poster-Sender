# TPA Antigravity 2.0 - Launcher & Auto-Setup Script

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "🚀 TPA Antigravity 2.0 - Auto-Setup & Launcher" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

# Ensure local bin directory is in PATH for this execution
$localBinPath = Join-Path $env:USERPROFILE ".local\bin"
if (-not ($env:PATH -split ';' -contains $localBinPath)) {
    $env:PATH = "$localBinPath;" + $env:PATH
}

# 1. Check for uv package manager
Write-Host "[1/4] Checking for 'uv' Python package manager..." -ForegroundColor Gray
$uvAvailable = Get-Command uv -ErrorAction SilentlyContinue

if (-not $uvAvailable) {
    Write-Host "👉 'uv' is not detected. Installing it now (portable, user-level)..." -ForegroundColor Yellow
    try {
        # Run uv installer script
        Invoke-Expression (Invoke-WebRequest -Uri "https://astral.sh/uv/install.ps1" -UseBasicParsing).Content
        Write-Host "✅ 'uv' installed successfully!" -ForegroundColor Green
    }
    catch {
        Write-Error "❌ Failed to install 'uv'. Please check your internet connection."
        Exit 1
    }
} else {
    Write-Host "✅ 'uv' is already installed!" -ForegroundColor Green
}

# 2. Check virtual environment
Write-Host "[2/4] Ensuring Python environment exists..." -ForegroundColor Gray
$venvPath = Join-Path $PSScriptRoot ".venv"

if (-not (Test-Path $venvPath)) {
    Write-Host "👉 Virtual environment not found. Initializing Python 3.12..." -ForegroundColor Yellow
    try {
        # Create virtual env using uv (it will fetch Python 3.12 automatically)
        uv venv .venv --python 3.12
        Write-Host "✅ Python 3.12 environment initialized!" -ForegroundColor Green
    }
    catch {
        Write-Error "❌ Failed to initialize virtual environment."
        Exit 1
    }
} else {
    Write-Host "✅ Environment exists." -ForegroundColor Green
}

# 3. Install/sync dependencies
Write-Host "[3/4] Checking and installing dependencies..." -ForegroundColor Gray
try {
    # Activate virtual environment temporarily and run pip install via uv
    & uv pip install -r requirements.txt
    Write-Host "✅ Dependencies synchronized successfully!" -ForegroundColor Green
}
catch {
    Write-Error "❌ Dependency installation failed."
    Exit 1
}

# 4. Populate database with mock records (if not already done)
Write-Host "[4/5] Preparing client database (1,500 permanent records)..." -ForegroundColor Gray
& uv run python test_db.py

# Start Webhook server in background
Write-Host "[Webhook] Starting webhook server in background..." -ForegroundColor Gray
Start-Process -FilePath "uv" -ArgumentList "run", "python", "webhook.py" -WindowStyle Hidden

# 5. Run Streamlit Application
Write-Host "[5/5] Launching TPA Poster Sender Web Interface..." -ForegroundColor Cyan
Write-Host "👉 The app will open automatically in your browser." -ForegroundColor Gray
Write-Host "👉 Press Ctrl+C in this terminal to stop the application." -ForegroundColor Gray
Write-Host "---------------------------------------------" -ForegroundColor Cyan

# Start Streamlit application
& uv run streamlit run app.py
