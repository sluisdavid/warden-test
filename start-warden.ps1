param(
    [switch]$Detached
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

function Get-DotEnvValue {
    param(
        [string]$Path,
        [string]$Name
    )

    if (-not (Test-Path $Path)) {
        return $null
    }

    $line = Get-Content $Path | Where-Object { $_ -match "^\s*$Name=" } | Select-Object -First 1
    if (-not $line) {
        return $null
    }

    return ($line -split "=", 2)[1].Trim()
}

$envFile = Join-Path $projectRoot ".env"
$provider = if ($env:WARDEN_LLM_PROVIDER) { $env:WARDEN_LLM_PROVIDER } else { Get-DotEnvValue -Path $envFile -Name "WARDEN_LLM_PROVIDER" }

if (-not $provider) {
    $answer = Read-Host "Usar Groq como proveedor LLM? (s/N)"
    if ($answer -match "^(s|si|y|yes)$") {
        $provider = "groq"
    }
    else {
        $provider = "heuristic"
    }
    $env:WARDEN_LLM_PROVIDER = $provider
}

$apiKey = if ($env:WARDEN_LLM_API_KEY) { $env:WARDEN_LLM_API_KEY } else { Get-DotEnvValue -Path $envFile -Name "WARDEN_LLM_API_KEY" }

if ($provider -eq "groq" -and [string]::IsNullOrWhiteSpace($apiKey)) {
    Write-Host "WARDEN_LLM_PROVIDER=groq y no se encontro WARDEN_LLM_API_KEY."
    $secure = Read-Host "Ingresa la API key de Groq para esta sesion" -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        $apiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
    }

    if ([string]::IsNullOrWhiteSpace($apiKey)) {
        throw "No se proporciono una API key."
    }

    $env:WARDEN_LLM_API_KEY = $apiKey
}

if ($Detached) {
    docker compose up --build -d
}
else {
    docker compose up --build
}
