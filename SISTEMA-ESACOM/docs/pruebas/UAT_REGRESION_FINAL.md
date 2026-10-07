# UAT y regresión final del Sistema ESACOM

## Responsable

Charlien

## Rama

`test/charlien-uat-regresion-final`

## Objetivo

Validar el funcionamiento general del Sistema ESACOM después de la integración final, verificando servicios, acceso, navegación, sincronización y estabilidad operativa.

## Validaciones técnicas

- Backend: `healthy`
- Frontend: `healthy`
- PostgreSQL: `healthy`
- Redis: `healthy`
- Celery Worker: `Up`
- Celery Beat: `Up`

## Validaciones HTTP

- Backend `/api/health/`: `200 OK`
- Frontend `http://localhost:8081`: `200 OK`

## Validaciones funcionales

- Login válido: OK
- Login inválido: OK
- Navegación por perfiles: OK
- Ejecutivo: OK
- Supervisor: OK
- Gerencia: OK
- Soporte: OK
- Histórico KPI: OK
- Cierres KPI: OK
- Auditoría KPI: OK
- Seguimiento / Accionables: OK
- Cierre de sesión: OK
- Nuevo ingreso: OK

## Sincronización Google Sheets

La sincronización manual fue ejecutada correctamente mediante:

```bash
docker compose --env-file .env.docker -f docker-compose.postgres.yml exec backend python manage.py sincronizar_google_sheets