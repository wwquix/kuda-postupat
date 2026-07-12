[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$EnvFile = Join-Path $PSScriptRoot '.env'
if (-not (Test-Path -LiteralPath $EnvFile)) { throw '.env не найден. Выполните .\setup.ps1' }

$tokenLine = Get-Content -LiteralPath $EnvFile | Where-Object { $_ -match '^MANUAL_REFRESH_TOKEN=' } | Select-Object -Last 1
if (-not $tokenLine) { throw 'MANUAL_REFRESH_TOKEN отсутствует в .env.' }
$token = ($tokenLine -split '=', 2)[1].Trim()
if (-not $token) { throw 'MANUAL_REFRESH_TOKEN пуст.' }

try {
    $response = Invoke-WebRequest -Method Post -Uri 'http://127.0.0.1:8000/api/refresh' `
        -Headers @{ 'X-Refresh-Token' = $token } -TimeoutSec 90
    $result = $response.Content | ConvertFrom-Json
    $message = if ($result.message) { ", $($result.message)" } else { "" }
    Write-Host "Обновление завершено: HTTP=$($response.StatusCode), status=$($result.status), создано snapshots=$($result.created), строк найдено=$($result.rows_found)$message"
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    if ($statusCode -eq 429) { Write-Error 'Обновление отклонено: запросы к БГЭУ разрешены не чаще одного раза в 5 минут.' }
    elseif ($statusCode -eq 401) { Write-Error 'Обновление отклонено: проверьте MANUAL_REFRESH_TOKEN в .env.' }
    else { Write-Error "Не удалось обновить данные: $($_.Exception.Message)" }
    exit 1
}
