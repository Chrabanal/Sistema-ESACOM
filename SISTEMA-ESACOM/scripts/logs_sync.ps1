$Root = Split-Path -Parent $PSScriptRoot
Push-Location $Root
try {
    docker compose --env-file .env.docker logs -f --tail=150 beat worker
} finally { Pop-Location }
