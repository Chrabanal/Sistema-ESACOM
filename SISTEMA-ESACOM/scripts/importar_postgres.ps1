$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Push-Location $Root
try {
    if (!(Test-Path "data\esacom_sqlite_export.json")) { throw "Falta data\esacom_sqlite_export.json. Ejecuta scripts\exportar_sqlite.ps1 primero." }
    docker compose --env-file .env.docker up -d db redis backend
    docker compose --env-file .env.docker exec backend python manage.py flush --noinput
    docker compose --env-file .env.docker exec backend python manage.py migrate --noinput
    docker compose --env-file .env.docker exec backend python manage.py loaddata /app/data/esacom_sqlite_export.json
    Write-Host "Importacion PostgreSQL OK" -ForegroundColor Green
} finally { Pop-Location }
