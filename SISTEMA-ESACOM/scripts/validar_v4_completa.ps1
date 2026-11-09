param(
    [Parameter(Mandatory = $true)]
    [string]$KpiPath
)

$ErrorActionPreference = "Stop"

function Assert-ExitCode([string]$Paso) {
    if ($LASTEXITCODE -ne 0) {
        throw "Fallo: $Paso (exit code $LASTEXITCODE). No continuar UAT."
    }
}

Write-Host "=== ESACOM CRM V4.2.1 - VALIDACION COMPLETA V3 + KPI V4.2.1 ===" -ForegroundColor Cyan
Write-Host "Produccion V3 se valida sin cambiar sus reglas. KPI V4.2.1 se prueba contra el XLSX oficial con rollback." -ForegroundColor Yellow
Write-Host "No se utiliza docker compose down -v." -ForegroundColor Yellow

$origen = (Resolve-Path -LiteralPath $KpiPath).Path
$destino = Join-Path (Get-Location) "data\KPI24082026_ESACOM_V4_UAT.xlsx"
$origenFull = [System.IO.Path]::GetFullPath($origen)
$destinoFull = [System.IO.Path]::GetFullPath($destino)

if ($origenFull -ne $destinoFull) {
    Copy-Item -LiteralPath $origenFull -Destination $destinoFull -Force
}

try {
    Write-Host "`n[1/9] Estado de contenedores" -ForegroundColor Cyan
    docker compose ps
    Assert-ExitCode "docker compose ps"

    Write-Host "`n[2/9] Django check + migraciones pendientes" -ForegroundColor Cyan
    docker compose exec backend python manage.py check
    Assert-ExitCode "Django check"
    docker compose exec backend python manage.py makemigrations --check
    Assert-ExitCode "makemigrations --check"

    Write-Host "`n[3/9] Regresion PRODUCCION V3" -ForegroundColor Cyan
    docker compose exec backend python manage.py test integraciones.tests_duplicados_pedido integraciones.tests_produccion_fuente ventas.tests_fila_fuente ventas.tests_produccion
    Assert-ExitCode "tests produccion V3"

    Write-Host "`n[4/9] Tests KPI V4.2.1" -ForegroundColor Cyan
    docker compose exec backend python manage.py test ventas.tests_kpi_v4 integraciones.tests_kpi_v4_import integraciones.tests_kpi_population integraciones.tests
    Assert-ExitCode "tests KPI V4.2.1"

    Write-Host "`n[5/9] Validacion viva PRODUCCION V3" -ForegroundColor Cyan
    powershell -ExecutionPolicy Bypass -File .\scripts\validar_produccion_2508.ps1
    Assert-ExitCode "script produccion V3"

    Write-Host "`n[6/9] Gate atomico PRODUCCION V3" -ForegroundColor Cyan
    docker compose exec backend python manage.py auditar_ultimo_sync_esacom
    Assert-ExitCode "gate atomico produccion"

    Write-Host "`n[7/9] Auditoria KPI24082026 directa + snapshot vigente + importacion transaccional" -ForegroundColor Cyan
    docker compose exec backend python manage.py auditar_kpi_v4 /app/data/KPI24082026_ESACOM_V4_UAT.xlsx --fecha-corte 2026-08-24 --dia-reporte LUNES --control-2408 --probar-importacion
    Assert-ExitCode "auditoria KPI V4.2.1"

    Write-Host "`n[8/9] Re-check Django despues de pruebas" -ForegroundColor Cyan
    docker compose exec backend python manage.py check
    Assert-ExitCode "Django check final"

    Write-Host "`n[9/9] RESULTADO" -ForegroundColor Cyan
    Write-Host "[OK] Regresion V3 + KPI V4.2.1 completadas." -ForegroundColor Green
    Write-Host "Esperado KPI24082026: B1 82.27% / Proy 89.91% / Q23; B2 77.46% / Proy 80.65% / Q50; B3 71.54% / Proy 75.23% / Q48." -ForegroundColor Green
    Write-Host "La auditoria KPI usa ROLLBACK: no crea un snapshot historico de laboratorio." -ForegroundColor Green
}
finally {
    if ($origenFull -ne $destinoFull -and (Test-Path -LiteralPath $destinoFull)) {
        Remove-Item -LiteralPath $destinoFull -Force
    }
}
