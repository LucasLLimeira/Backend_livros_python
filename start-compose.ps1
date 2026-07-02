param(
    [int]$PreferredPort = 8000
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-ComposeRunner {
    if (Get-Command docker -ErrorAction SilentlyContinue) {
        try {
            docker compose version | Out-Null
            return @{ Type = "docker"; Prefix = @("docker", "compose") }
        } catch {
        }
    }

    if (Get-Command podman-compose -ErrorAction SilentlyContinue) {
        return @{ Type = "podman"; Prefix = @("podman-compose") }
    }

    throw "No compose runner found. Install Docker Compose v2 or podman-compose."
}

function Test-PortInUse {
    param([int]$Port)
    $conn = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
    return $null -ne $conn
}

function Get-AvailablePort {
    param([int]$StartPort)

    $candidates = @($StartPort, 8001, 8002, 9000)
    foreach ($p in $candidates) {
        if (-not (Test-PortInUse -Port $p)) {
            return $p
        }
    }

    throw "No available port found in: $($candidates -join ', ')"
}

$runner = Get-ComposeRunner
$selectedPort = Get-AvailablePort -StartPort $PreferredPort

if ($selectedPort -ne $PreferredPort) {
    Write-Host "Port $PreferredPort is in use. Falling back to port $selectedPort." -ForegroundColor Yellow
}

$env:APP_PORT = "$selectedPort"

if ($runner.Type -eq "docker") {
    docker info | Out-Null
}

Write-Host "Validating compose file..." -ForegroundColor Cyan
if ($runner.Type -eq "docker") {
    docker compose config | Out-Null
} else {
    podman-compose config | Out-Null
}

Write-Host "Starting services with APP_PORT=$selectedPort..." -ForegroundColor Green
if ($runner.Type -eq "docker") {
    docker compose up -d
    docker compose ps
} else {
    podman-compose up -d
    podman ps
}

Write-Host "API: http://127.0.0.1:$selectedPort" -ForegroundColor Green
Write-Host "Docs: http://127.0.0.1:$selectedPort/docs" -ForegroundColor Green
Write-Host "Kibana: http://127.0.0.1:5601" -ForegroundColor Green
