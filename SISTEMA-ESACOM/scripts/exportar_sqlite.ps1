$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Push-Location $Root
try {
    python .\scripts\exportar_sqlite.py
} finally { Pop-Location }
