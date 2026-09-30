# Procedimiento seguro para compartir configuraciones

## Objetivo

Definir cómo preparar y compartir la configuración del Sistema ESACOM sin publicar contraseñas, credenciales ni archivos privados en GitHub.

## Archivos de ejemplo permitidos

Los siguientes archivos pueden guardarse en GitHub porque no deben contener valores reales:

- `.env.docker.example`
- `esacom_frontend/.env.example`

Estos archivos muestran únicamente los nombres de las variables y valores de ejemplo.

## Archivos privados

Los siguientes archivos no deben subirse ni enviarse mediante GitHub:

- `.env`
- `.env.docker`
- `db.sqlite3`
- Archivos JSON de cuentas de servicio Google
- Contraseñas
- Llaves privadas
- Copias de respaldo con datos reales

## Preparación del ambiente local

1. Copiar el archivo `.env.docker.example`.
2. Renombrar la copia como `.env.docker`.
3. Completar las variables solamente en el computador local.
4. Preparar `esacom_backend/.env` con los valores requeridos por Django.
5. Guardar la credencial Google dentro de:

   `esacom_backend/credentials/`

6. No copiar ni publicar el contenido de esos archivos en Trello, GitHub, capturas o mensajes.

## Forma segura de compartir configuraciones

- Compartir solamente los archivos `.example` mediante GitHub.
- Entregar las credenciales reales por un medio privado autorizado por ESACOM.
- No enviar secretos dentro de Pull Requests, commits o comentarios.
- No mostrar contraseñas ni contenido de archivos JSON en capturas.
- Confirmar que el destinatario correcto recibió la configuración.
- Eliminar copias temporales que ya no sean necesarias.

## Validación antes de realizar un commit

Ejecutar:

`git check-ignore -v .env.docker esacom_backend/.env`

Los dos archivos deben aparecer protegidos por `.gitignore`.

Después ejecutar:

`git status --short`

No deben aparecer archivos `.env`, credenciales, bases SQLite ni JSON privados.

También se puede revisar lo actualmente versionado con:

`git ls-files | Select-String -Pattern '(^|/)\.env($|\.)|credentials|\.json$|db\.sqlite3'`

Los archivos `.env.*.example` y `package*.json` son permitidos. No deben aparecer credenciales reales.

## Regla para credenciales de Google

El archivo JSON de la cuenta de servicio debe:

- Permanecer fuera de Git.
- Guardarse en `esacom_backend/credentials/`.
- Tener acceso limitado a las personas autorizadas.
- No mostrarse en capturas ni copiarse dentro de documentos.
- Ser reemplazado si existe sospecha de exposición.

## Resultado esperado

Cada integrante puede preparar su ambiente local utilizando los archivos de ejemplo, sin modificar el código y sin publicar información privada.