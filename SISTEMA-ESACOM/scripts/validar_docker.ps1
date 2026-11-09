$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Push-Location $Root
try {
    Write-Host "=== Servicios ===" -ForegroundColor Cyan
    docker compose --env-file .env.docker ps
    Write-Host "`n=== Django check ===" -ForegroundColor Cyan
    docker compose --env-file .env.docker exec backend python manage.py check
    Write-Host "`n=== Camilo ===" -ForegroundColor Cyan
    docker compose --env-file .env.docker exec backend python manage.py validar_dashboard_ejecutivo --rut 19776727-8
    Write-Host "`n=== Supervisor Charly / Camilo ===" -ForegroundColor Cyan
    docker compose --env-file .env.docker exec backend python manage.py validar_dashboard_supervisor --rut 17480807-4 --ejecutivo-rut 19776727-8
    Write-Host "`n=== Gerencia ===" -ForegroundColor Cyan
    docker compose --env-file .env.docker exec backend python manage.py validar_dashboard_gerencia
} finally { Pop-Location }
