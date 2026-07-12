[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$Runtime = Join-Path $Root '.runtime'

function Stop-VerifiedTree([string]$PidFile, [string]$Marker, [string]$Name) {
    if (-not (Test-Path -LiteralPath $PidFile)) { Write-Host "${Name}: PID-файл отсутствует."; return }
    $savedPid = (Get-Content -Raw -LiteralPath $PidFile).Trim()
    if ($savedPid -notmatch '^\d+$') { Remove-Item -LiteralPath $PidFile -Force; Write-Host "${Name}: удалён повреждённый PID-файл."; return }
    $rootProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $savedPid" -ErrorAction SilentlyContinue
    if (-not $rootProcess) { Remove-Item -LiteralPath $PidFile -Force; Write-Host "${Name}: удалён устаревший PID-файл."; return }
    if ($rootProcess.CommandLine -notlike "*$Marker*") {
        Remove-Item -LiteralPath $PidFile -Force
        Write-Warning "${Name}: PID уже принадлежит другому процессу; процесс не остановлен. PID-файл удалён."
        return
    }
    $all = Get-CimInstance Win32_Process
    function Get-Children([int]$ParentId) {
        foreach ($child in $all | Where-Object ParentProcessId -eq $ParentId) {
            Get-Children $child.ProcessId
            $child.ProcessId
        }
    }
    $descendants = @(Get-Children ([int]$savedPid))
    foreach ($processId in $descendants) { Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue }
    Stop-Process -Id ([int]$savedPid) -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $PidFile -Force
    Write-Host "$Name остановлен."
}

if (-not (Test-Path -LiteralPath $Runtime)) { Write-Host 'Проект не запущен.'; exit 0 }
Stop-VerifiedTree (Join-Path $Runtime 'backend.pid') 'uvicorn' 'Backend'
Stop-VerifiedTree (Join-Path $Runtime 'frontend.pid') $Root 'Frontend'
