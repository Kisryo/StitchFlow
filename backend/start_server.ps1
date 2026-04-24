# StitchFlow V2 - Quick Start Script (PowerShell)
# This script helps you start the backend server quickly

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "StitchFlow V2 - Backend Server Startup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if virtual environment exists
if (Test-Path "venv") {
    Write-Host "[OK] Virtual environment found" -ForegroundColor Green
} else {
    Write-Host "[INFO] Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
    Write-Host "[OK] Virtual environment created" -ForegroundColor Green
}

# Activate virtual environment
Write-Host "[INFO] Activating virtual environment..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1

# Check if requirements are installed
Write-Host "[INFO] Checking dependencies..." -ForegroundColor Yellow
$pipList = pip list
if ($pipList -match "fastapi") {
    Write-Host "[OK] Dependencies already installed" -ForegroundColor Green
} else {
    Write-Host "[INFO] Installing dependencies..." -ForegroundColor Yellow
    pip install -r requirements.txt
    Write-Host "[OK] Dependencies installed" -ForegroundColor Green
}

# Check if .env file exists
if (Test-Path ".env") {
    Write-Host "[OK] Environment file found" -ForegroundColor Green
} else {
    Write-Host "[WARNING] .env file not found!" -ForegroundColor Red
    Write-Host "[INFO] Copying .env.example to .env..." -ForegroundColor Yellow
    Copy-Item .env.example .env
    Write-Host "[WARNING] Please edit .env file with your API keys!" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to continue after editing .env file"
}

# Create uploads directory
if (-not (Test-Path "uploads")) {
    New-Item -ItemType Directory -Path "uploads" | Out-Null
    Write-Host "[OK] Created uploads directory" -ForegroundColor Green
}

# Start the server
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Starting FastAPI Server..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Server will be available at:" -ForegroundColor Yellow
Write-Host "  - API: http://localhost:8000" -ForegroundColor White
Write-Host "  - Docs: http://localhost:8000/docs" -ForegroundColor White
Write-Host "  - Health: http://localhost:8000/health" -ForegroundColor White
Write-Host ""
Write-Host "Press CTRL+C to stop the server" -ForegroundColor Yellow
Write-Host ""

# Run the server
python main.py
