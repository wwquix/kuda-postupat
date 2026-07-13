[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$VenvPython = Join-Path $Root '.venv\Scripts\python.exe'
$Frontend = Join-Path $Root 'frontend'
$EnvFile = Join-Path $Root '.env'
$EnvExample = Join-Path $Root '.env.example'

foreach ($pidName in @('backend.pid', 'frontend.pid')) {
    $pidFile = Join-Path $Root ".runtime\$pidName"
    if (Test-Path -LiteralPath $pidFile) {
        $savedPid = (Get-Content -Raw -LiteralPath $pidFile).Trim()
        if ($savedPid -match '^\d+$' -and (Get-Process -Id ([int]$savedPid) -ErrorAction SilentlyContinue)) {
            throw 'Проект запущен. Перед повторным setup выполните .\stop-dev.ps1'
        }
    }
}

function Resolve-Python {
    if (Get-Command py.exe -ErrorAction SilentlyContinue) {
        & py.exe -3.12 -c 'import sys' 2>$null
        if ($LASTEXITCODE -eq 0) { return @('py.exe', '-3.12') }
    }
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if (-not $python) { throw 'Python 3.12+ не найден в PATH.' }
    $version = & $python.Source -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'
    if ([version]$version -lt [version]'3.12') { throw "Требуется Python 3.12+, найден $version." }
    if ($version -ne '3.12') { Write-Warning "Проект рассчитан на Python 3.12; локально будет использован Python $version." }
    return @($python.Source)
}

if (-not (Test-Path -LiteralPath $VenvPython)) {
    $pythonCommand = @(Resolve-Python)
    Write-Host 'Создаю Python virtual environment...'
    if ($pythonCommand.Count -eq 2) {
        & $pythonCommand[0] $pythonCommand[1] -m venv (Join-Path $Root '.venv')
    } else {
        & $pythonCommand[0] -m venv (Join-Path $Root '.venv')
    }
    if ($LASTEXITCODE -ne 0) { throw 'Не удалось создать .venv.' }
}

Write-Host 'Устанавливаю backend-зависимости...'
& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'Не удалось обновить pip.' }
& $VenvPython -m pip install -r (Join-Path $Root 'backend\requirements-dev.txt')
if ($LASTEXITCODE -ne 0) { throw 'Не удалось установить backend-зависимости.' }

if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw 'npm не найден в PATH.' }
Write-Host 'Устанавливаю frontend-зависимости...'
Push-Location $Frontend
try {
    & npm.cmd ci
    if ($LASTEXITCODE -ne 0) { throw 'npm ci завершился с ошибкой.' }
} finally { Pop-Location }

if (-not (Test-Path -LiteralPath $EnvFile)) {
    if (-not (Test-Path -LiteralPath $EnvExample)) { throw '.env.example не найден.' }
    $bytes = New-Object byte[] 32
    $random = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $random.GetBytes($bytes) } finally { $random.Dispose() }
    $token = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
    $content = Get-Content -Raw -LiteralPath $EnvExample
    $content = [regex]::Replace($content, '(?m)^MANUAL_REFRESH_TOKEN=.*$', "MANUAL_REFRESH_TOKEN=$token")
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($EnvFile, $content, $utf8NoBom)
    Write-Host '.env создан; безопасный MANUAL_REFRESH_TOKEN сгенерирован (значение не выводится).'
} else {
    Write-Host '.env уже существует и не был изменён.'
}

Write-Host 'Проверяю и применяю Alembic migrations...'
Push-Location (Join-Path $Root 'backend')
try {
    & $VenvPython -m app.schema setup
    if ($LASTEXITCODE -ne 0) {
        throw 'Не удалось подготовить схему БД. Для существующей unversioned legacy-базы сначала создайте backup и выполните documented verify/stamp procedure.'
    }
} finally { Pop-Location }

New-Item -ItemType Directory -Force -Path (Join-Path $Root '.runtime') | Out-Null
Write-Host 'Готово. Запуск: .\start-dev.ps1'
