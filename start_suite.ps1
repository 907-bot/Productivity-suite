# AI Productivity Suite Launcher
# Starts all 5 Gemini-powered backends with uvicorn

$projects = @(
    @{ name="Life Admin";    port=8001; dir="life-admin\backend" },
    @{ name="Wellness";      port=8002; dir="wellness-manager\backend" },
    @{ name="Finance";       port=8003; dir="finance-manager\backend" },
    @{ name="Content";       port=8004; dir="content-manager\backend" },
    @{ name="Relationship";  port=8005; dir="relationship-manager\backend" }
)

Write-Host "Stopping any existing backends..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep 1

Write-Host "Starting AI Productivity Suite (Gemini 2.0 Flash)..." -ForegroundColor Cyan

foreach ($proj in $projects) {
    Write-Host "Starting $($proj.name) on port $($proj.port)..."
    $fullDir = "d:\productivity\$($proj.dir)"
    Start-Process python -ArgumentList "-m uvicorn main:app --host 0.0.0.0 --port $($proj.port) --reload" -WorkingDirectory $fullDir -NoNewWindow -PassThru
    Start-Sleep 1
}

Write-Host "All backends started! Waiting for them to warm up..." -ForegroundColor Green
Start-Sleep 3
Write-Host "Opening dashboard..." -ForegroundColor Green
Start-Process "d:\productivity\index.html"
