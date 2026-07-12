[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$Runtime = Join-Path $Root '.runtime'
$VenvPython = Join-Path $Root '.venv\Scripts\python.exe'
$BackendDir = Join-Path $Root 'backend'
$FrontendDir = Join-Path $Root 'frontend'

function Test-ProjectProcess([string]$PidFile, [string]$Marker) {
    if (-not (Test-Path -LiteralPath $PidFile)) { return $false }
    $savedPid = (Get-Content -Raw -LiteralPath $PidFile).Trim()
    if ($savedPid -notmatch '^\d+$') { Remove-Item -LiteralPath $PidFile -Force; return $false }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $savedPid" -ErrorAction SilentlyContinue
    if (-not $process -or $process.CommandLine -notlike "*$Marker*") {
        Remove-Item -LiteralPath $PidFile -Force
        return $false
    }
    return $true
}

if (-not (Test-Path -LiteralPath $VenvPython) -or -not (Test-Path -LiteralPath (Join-Path $FrontendDir 'node_modules'))) {
    throw 'Окружение не настроено. Сначала выполните .\setup.ps1'
}
if (-not (Test-Path -LiteralPath (Join-Path $Root '.env'))) { throw '.env отсутствует. Сначала выполните .\setup.ps1' }
New-Item -ItemType Directory -Force -Path $Runtime | Out-Null

$backendPidFile = Join-Path $Runtime 'backend.pid'
$frontendPidFile = Join-Path $Runtime 'frontend.pid'
$backendRunning = Test-ProjectProcess $backendPidFile 'uvicorn'
$frontendRunning = Test-ProjectProcess $frontendPidFile $Root

if (-not $backendRunning) {
    $backend = Start-Process -FilePath $VenvPython `
        -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000') `
        -WorkingDirectory $BackendDir -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $Runtime 'backend.stdout.log') `
        -RedirectStandardError (Join-Path $Runtime 'backend.stderr.log')
    Set-Content -LiteralPath $backendPidFile -Value $backend.Id -Encoding ascii
}

if (-not $frontendRunning) {
    $escapedFrontend = $FrontendDir.Replace("'", "''")
    $command = "Set-Location -LiteralPath '$escapedFrontend'; & npm.cmd run dev -- --host 127.0.0.1 --port 5173"
    $frontend = Start-Process -FilePath (Get-Process -Id $PID).Path `
        -ArgumentList @('-NoProfile', '-Command', $command) -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $Runtime 'frontend.stdout.log') `
        -RedirectStandardError (Join-Path $Runtime 'frontend.stderr.log')
    Set-Content -LiteralPath $frontendPidFile -Value $frontend.Id -Encoding ascii
}

Start-Sleep -Seconds 2
try { $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 5 } catch {
    throw "Backend не прошёл healthcheck. Проверьте .runtime\backend.stderr.log. $($_.Exception.Message)"
}
try { $response = Invoke-WebRequest -Uri 'http://127.0.0.1:5173/' -TimeoutSec 5 } catch {
    throw "Frontend не отвечает. Проверьте .runtime\frontend.stderr.log. $($_.Exception.Message)"
}
if ($health.status -ne 'ok' -or $response.StatusCode -ne 200) { throw 'Проект запущен, но проверка готовности не пройдена.' }

Write-Host 'Backend:  http://127.0.0.1:8000'
Write-Host 'Dashboard: http://127.0.0.1:5173'
if ($backendRunning -and $frontendRunning) { Write-Host 'Проект уже был запущен; повторные процессы не созданы.' }
