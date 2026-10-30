# Local/CI verification for TCMS (PowerShell 5.1+).
# Usage: .\scripts\verify.ps1 [-SkipTests] [-SkipDeployCheck]
param(
    [switch]$SkipTests,
    [switch]$SkipDeployCheck
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)

if (-not $env:USE_SQLITE) { $env:USE_SQLITE = "true" }

function Invoke-Check {
    param([string]$Label, [scriptblock]$Action)
    Write-Host "==> $Label" -ForegroundColor Cyan
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed (exit $LASTEXITCODE)"
    }
}

if (-not $SkipTests) {
    Invoke-Check "Django test suite" { python manage.py test }
}
Invoke-Check "Ruff lint" { python -m ruff check apps config scripts }
Invoke-Check "Django system check" { python manage.py check }
Invoke-Check "Migration drift" { python manage.py makemigrations --check --dry-run }
Invoke-Check "OpenAPI schema" { python manage.py spectacular --file schema.yml }

if (-not $SkipDeployCheck) {
    $saved = @{
        Settings = $env:DJANGO_SETTINGS_MODULE
        Secret = $env:SECRET_KEY
        Hosts = $env:ALLOWED_HOSTS
    }
    try {
        $env:DJANGO_SETTINGS_MODULE = "config.settings.prod"
        $env:SECRET_KEY = "verify-only-not-a-production-secret-0123456789-abcdefghij"
        $env:ALLOWED_HOSTS = "tcms.example.com"
        Invoke-Check "Production deploy check" { python manage.py check --deploy }
    }
    finally {
        $env:DJANGO_SETTINGS_MODULE = $saved.Settings
        $env:SECRET_KEY = $saved.Secret
        $env:ALLOWED_HOSTS = $saved.Hosts
    }
}

Write-Host "All verification checks passed." -ForegroundColor Green
