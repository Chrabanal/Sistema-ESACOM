$ErrorActionPreference = "Stop"

Write-Host "=== ESACOM - VALIDACION PRODUCCION ATOMICA 25/08/2026 ===" -ForegroundColor Cyan
Write-Host "Ejecutar desde la carpeta que contiene docker-compose.yml." -ForegroundColor Yellow
Write-Host "No se utiliza docker compose down -v." -ForegroundColor Yellow

Write-Host "`n[1/10] Estado de contenedores" -ForegroundColor Cyan
docker compose ps

Write-Host "`n[2/10] Validacion Django" -ForegroundColor Cyan
docker compose exec backend python manage.py check

Write-Host "`n[3/10] Hojas ESACOM visibles y ocultas (Sheets API o fallback Drive/XLSX)" -ForegroundColor Cyan
docker compose exec backend python manage.py listar_hojas_esacom --todas

Write-Host "`n[4/10] Sincronizacion atomica desde la matriz ESACOM" -ForegroundColor Cyan
Write-Host "El mismo XLSX se calcula directamente y luego se importa; no hay una segunda descarga para esta comprobacion." -ForegroundColor DarkGray
docker compose exec backend python manage.py verificar_sync_esacom --sincronizar

Write-Host "`n[5/10] Auditoria ATOMICA del mismo XLSX importado" -ForegroundColor Cyan
docker compose exec backend python manage.py auditar_ultimo_sync_esacom

Write-Host "`n[6/10] Historial de snapshots ESACOM" -ForegroundColor Cyan
docker compose exec backend python manage.py historial_produccion_esacom --ultimos 5

Write-Host "`n[7/10] Fuente viva actual vs CRM" -ForegroundColor Cyan
Write-Host "Si la matriz cambio despues del sync, se reporta como EVOLUCION POST-SYNC y no como error del importador." -ForegroundColor DarkGray
docker compose exec backend python manage.py auditar_fuente_esacom --control-2508 --solo-diferencias

Write-Host "`n[8/10] Auditoria Gerencia 25/08 (snapshot historico)" -ForegroundColor Cyan
docker compose exec backend python manage.py auditar_produccion_esacom --control-2508 --detalle-control --solo-diferencias --pendientes-movil

Write-Host "`n[9/10] Auditoria Sergio Osses" -ForegroundColor Cyan
docker compose exec backend python manage.py auditar_produccion_esacom --rut 19665650-2 --control-2508

Write-Host "`n[10/10] Auditoria Camilo Bascunan" -ForegroundColor Cyan
docker compose exec backend python manage.py auditar_produccion_esacom --rut 19776727-8 --control-2508

Write-Host "`nReferencia historica Gerencia 25/08 AM: FIJA 693 RGU + MOVIL 144 = 837." -ForegroundColor Yellow
Write-Host "Criterio critico UAT: MISMO XLSX IMPORTADO = CRM POST-IMPORT." -ForegroundColor Green
Write-Host "La fuente viva puede avanzar segundos despues; eso se registra como evolucion post-sync." -ForegroundColor Green
Write-Host "No ajustar cifras manualmente para hacer coincidir un snapshot anterior." -ForegroundColor Green
