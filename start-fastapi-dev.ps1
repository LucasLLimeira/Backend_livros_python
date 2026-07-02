param(
    [string]$HostAddress = "127.0.0.1",
    [int[]]$PreferredPorts = @(8000, 8002, 8003, 9000)
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
if (Get-Variable PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

function Test-PortInUse {
    param([int]$Port)

    $conn = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
    return $null -ne $conn
}

function Test-PoetryModule {
    param([string]$ModuleName)

    $probeCmd = "poetry run python -c ""import $ModuleName"" >nul 2>nul"
    cmd /c $probeCmd | Out-Null
    return $LASTEXITCODE -eq 0
}

function Test-ActivePythonModule {
    param([string]$ModuleName)

    python -c "import $ModuleName" 1>$null 2>$null
    return $LASTEXITCODE -eq 0
}

$selectedPort = $null
foreach ($port in $PreferredPorts) {
    if (-not (Test-PortInUse -Port $port)) {
        $selectedPort = $port
        break
    }
}

if ($null -eq $selectedPort) {
    throw "Nenhuma porta disponivel encontrada em: $($PreferredPorts -join ', ')."
}

Write-Host "Iniciando FastAPI em http://$HostAddress`:$selectedPort" -ForegroundColor Green

if (Test-ActivePythonModule -ModuleName "fastapi") {
    Write-Host "Comando: python -m fastapi dev main.py --host $HostAddress --port $selectedPort" -ForegroundColor DarkGray
    python -m fastapi dev main.py --host $HostAddress --port $selectedPort
    exit $LASTEXITCODE
}

if (Test-ActivePythonModule -ModuleName "uvicorn") {
    Write-Host "FastAPI CLI indisponivel no shell ativo; usando uvicorn em modo reload." -ForegroundColor Yellow
    Write-Host "Comando: python -m uvicorn main:app --reload --host $HostAddress --port $selectedPort" -ForegroundColor DarkGray
    python -m uvicorn main:app --reload --host $HostAddress --port $selectedPort
    exit $LASTEXITCODE
}

if (-not (Test-PoetryModule -ModuleName "fastapi")) {
    Write-Host "Dependencias ausentes no ambiente Poetry atual. Executando poetry install --no-root..." -ForegroundColor Yellow
    cmd /c "poetry install --no-root"
}

if (Test-PoetryModule -ModuleName "fastapi") {
    Write-Host "Comando: poetry run python -m fastapi dev main.py --host $HostAddress --port $selectedPort" -ForegroundColor DarkGray
    cmd /c "poetry run python -m fastapi dev main.py --host $HostAddress --port $selectedPort"
    exit $LASTEXITCODE
}

if (Test-PoetryModule -ModuleName "uvicorn") {
    Write-Host "FastAPI CLI indisponivel; usando uvicorn em modo reload." -ForegroundColor Yellow
    Write-Host "Comando: poetry run python -m uvicorn main:app --reload --host $HostAddress --port $selectedPort" -ForegroundColor DarkGray
    cmd /c "poetry run python -m uvicorn main:app --reload --host $HostAddress --port $selectedPort"
    exit $LASTEXITCODE
}

throw "Nao foi possivel encontrar fastapi/uvicorn no ambiente Poetry. Rode poetry install --no-root e tente novamente."
