[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$Python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) { throw '.venv отсутствует. Выполните .\setup.ps1' }
if (-not (Test-Path -LiteralPath (Join-Path $Root 'frontend\node_modules'))) { throw 'node_modules отсутствует. Выполните .\setup.ps1' }

function Invoke-Check([string]$Name, [scriptblock]$Command) {
    Write-Host "`n=== $Name ===" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$Name завершился с кодом $LASTEXITCODE." }
}

Push-Location (Join-Path $Root 'backend')
try {
    Invoke-Check 'Pytest' { & $Python -m pytest }
    Invoke-Check 'Live integration test' { & $Python -m pytest -m live -o addopts= }
    Invoke-Check 'Ruff' { & $Python -m ruff check . }
} finally { Pop-Location }

Push-Location (Join-Path $Root 'frontend')
try {
    Invoke-Check 'ESLint' { & npm.cmd run lint }
    Invoke-Check 'TypeScript' { & npm.cmd run typecheck }
    Invoke-Check 'Vite production build' { & npm.cmd run build }
} finally { Pop-Location }

Write-Host "`nВсе проверки успешно завершены." -ForegroundColor Green
