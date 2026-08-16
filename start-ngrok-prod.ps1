# Starts Docker + orid-prod, waits until the frontend answers, then launches ngrok.
# Use start-ngrok-prod.bat so this runs in a visible window after login.

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$composeProject = "orid-prod"
$composeFile = "docker-compose.prod.yml"
$envFile = ".env.prod"
$port = 3200
$ngrokDomain = $null

function Read-DotEnvValue {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Key
    )
    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match "^\s*$" -or $line -match "^\s*#") {
            continue
        }
        $eq = $line.IndexOf("=")
        if ($eq -lt 1) {
            continue
        }
        $name = $line.Substring(0, $eq).Trim()
        if ($name -eq $Key) {
            return $line.Substring($eq + 1).Trim()
        }
    }
    return $null
}

if (Test-Path -LiteralPath $envFile) {
    $envPort = Read-DotEnvValue -Path $envFile -Key "PROD_FRONTEND_PORT"
    if ($envPort) {
        $port = [int]$envPort
    }
    $frontendUrl = Read-DotEnvValue -Path $envFile -Key "FRONTEND_URL"
    if ($frontendUrl) {
        $uri = [Uri]$frontendUrl
        if ($uri.Host) {
            $ngrokDomain = $uri.Host
        }
    }
}

function Wait-Until {
    param(
        [scriptblock]$Condition,
        [int]$Attempts,
        [int]$DelaySeconds,
        [string]$Message
    )
    for ($i = 1; $i -le $Attempts; $i++) {
        try {
            if (& $Condition) {
                return $true
            }
        } catch {
            # keep waiting
        }
        Write-Host "$Message ($i/$Attempts)"
        Start-Sleep -Seconds $DelaySeconds
    }
    return $false
}

$dockerDesktop = @(
    "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe",
    "${env:ProgramFiles(x86)}\Docker\Docker\Docker Desktop.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

Write-Host "Ensuring Docker Desktop is running..."
if ($dockerDesktop) {
    $dockerInfo = & docker info 2>&1
    if ($LASTEXITCODE -ne 0) {
        Start-Process -FilePath $dockerDesktop | Out-Null
    }
}

if (-not (Wait-Until -Attempts 60 -DelaySeconds 3 -Message "Waiting for Docker engine" -Condition {
    & docker info --format "{{.ServerVersion}}" 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
})) {
    throw "Docker engine did not become ready. Open Docker Desktop and run this script again."
}

if (-not (Test-Path -LiteralPath $composeFile)) {
    throw "Missing $composeFile"
}
if (-not (Test-Path -LiteralPath $envFile)) {
    throw "Missing $envFile"
}

Write-Host "Starting production containers..."
& docker compose -p $composeProject -f $composeFile --env-file $envFile up -d
if ($LASTEXITCODE -ne 0) {
    throw "docker compose up failed"
}

$loginUrl = "http://127.0.0.1:$port/login"
Write-Host "Waiting for frontend at $loginUrl ..."
if (-not (Wait-Until -Attempts 90 -DelaySeconds 2 -Message "Waiting for frontend" -Condition {
    $response = Invoke-WebRequest -Uri $loginUrl -UseBasicParsing -TimeoutSec 5
    return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400)
})) {
    throw "Frontend did not become ready on 127.0.0.1:$port. Check: docker compose -p orid-prod logs frontend"
}

Write-Host "Frontend is ready."

$ngrokCmd = Get-Command ngrok -ErrorAction SilentlyContinue
if (-not $ngrokCmd) {
    throw "ngrok not found in PATH. Install from https://ngrok.com/download"
}

Get-Process ngrok -ErrorAction SilentlyContinue | Stop-Process -Force

$ngrokArgs = @("http", "127.0.0.1:$port")
if ($ngrokDomain) {
    $ngrokArgs = @("http", "--domain=$ngrokDomain", "127.0.0.1:$port")
    Write-Host "Starting ngrok: https://$ngrokDomain -> http://127.0.0.1:$port"
} else {
    Write-Host "Starting ngrok: http://127.0.0.1:$port"
}

& ngrok @ngrokArgs
if ($LASTEXITCODE -ne 0) {
    throw "ngrok exited with code $LASTEXITCODE"
}
