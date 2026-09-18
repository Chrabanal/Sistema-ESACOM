# Sistema ESACOM

Estructura inicial del proyecto ESACOM CRM para el Proyecto de Título DUOC UC 2026.

## Estructura

- `esacom_backend/`: backend Django.
- `esacom_frontend/`: frontend React/Vite.
- `scripts/`: utilidades técnicas.
- `docker-compose.yml`: configuración base de contenedores.
- `docker-compose.postgres.yml`: configuración PostgreSQL.
- `.env.docker.example`: ejemplo de variables de entorno sin secretos.

## Regla de seguridad

No versionar:

- `.env`
- `.env.docker`
- `db.sqlite3`
- credenciales de Google
- contraseñas o llaves privadas

## Flujo inicial

1. Cargar esta estructura en `main`.
2. Crear rama `develop`.
3. Crear ramas individuales del Bloque 1 para Charlien Rabanal, Carmen López y Kevin Stuardo.
