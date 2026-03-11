# run_system.ps1
# Automates the startup of the Smart Parking AI system

Write-Host "--- Automated Smart Parking AI Startup ---" -ForegroundColor Cyan

# 0. Stop existing services
Write-Host "Cleaning up existing uvicorn and node processes..." -ForegroundColor Yellow
Stop-Process -Name uvicorn -Force -ErrorAction SilentlyContinue
Stop-Process -Name node -Force -ErrorAction SilentlyContinue

# 1. Project Root Check
$RootDir = Get-Location
Write-Host "Project Root: $RootDir"

# 2. Setup Python environment
Write-Host "`n[SECTION 3] Setting up Python Environment..." -ForegroundColor Green
if (-not (Test-Path "backend\venv")) {
    Write-Host "Creating Virtual Environment..."
    python -m venv backend\venv
}

$Python = "$RootDir\backend\venv\Scripts\python.exe"
$Pip = "$RootDir\backend\venv\Scripts\pip.exe"

Write-Host "Installing dependencies..."
& $Pip install -r backend\requirements.txt --quiet
& $Pip install requests --quiet

# 3. Initialize Database
Write-Host "`n[SECTION 1] Initializing Database and Seeding..." -ForegroundColor Green
& $Python backend\init_db_and_seed.py

# 4. Start Backend API
Write-Host "`n[SECTION 3] Starting Backend API..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd backend; .\venv\Scripts\activate; uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

# 5. Wait for Backend readiness
Write-Host "Waiting for backend health check (max 60 attempts)..." -ForegroundColor Yellow
$attempts = 0
while ($attempts -lt 60) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/api/system/health" -UseBasicParsing -ErrorAction Ignore
        if ($response.StatusCode -eq 200) {
            Write-Host "Backend is UP!" -ForegroundColor Green
            break
        }
    } catch {}
    $attempts++
    Start-Sleep -Seconds 2
}
if ($attempts -ge 60) { Write-Host "Timeout waiting for backend!" -ForegroundColor Red; Exit 1 }

# 6. Start Frontend
Write-Host "`n[SECTION 3] Starting Frontend..." -ForegroundColor Green
if (-not (Test-Path "node_modules")) { npm install --silent }
Start-Process powershell -ArgumentList "-NoExit", "-Command", "npm run dev"

# 7. Wait for Frontend readiness
Write-Host "Waiting for frontend server..." -ForegroundColor Yellow
$start = Get-Date
while ($true) {
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $tcp.Connect("localhost", 5173)
        $tcp.Close()
        Write-Host "Frontend is UP!" -ForegroundColor Green
        break
    } catch {}
    if ((Get-Date) -gt $start.AddSeconds(30)) { Break }
    Start-Sleep -Seconds 2
}

# 8. Trigger AI worker
Write-Host "`n[SECTION 3] Triggering AI worker demo..." -ForegroundColor Green
try {
    Invoke-RestMethod -Uri "http://localhost:8000/api/jobs/start-demo" -Method POST -Body (@{video="parking_video.mp4"}|ConvertTo-Json) -ContentType "application/json"
    Write-Host "Worker triggered successfully." -ForegroundColor Green
} catch {
    Write-Host "Warning: Worker trigger failed. You may need to start it manually in the dashboard." -ForegroundColor Yellow
}

# 9. Start Worker Watchdog (Optional)
Write-Host "`n[SECTION 5] Starting Worker Watchdog..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", ".\backend\venv\Scripts\python.exe worker_watchdog.py"

# 10. Open Admin Dashboard
Write-Host "`n[SYSTEM READY] Launching Dashboard..." -ForegroundColor Cyan
Start-Process "http://localhost:5173/admin"
