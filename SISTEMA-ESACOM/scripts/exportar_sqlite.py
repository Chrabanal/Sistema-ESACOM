from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "esacom_backend"
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

if not (BACKEND / "db.sqlite3").exists():
    raise SystemExit("No existe esacom_backend/db.sqlite3")

sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "esacom_backend.settings")

import django
django.setup()
from django.core.management import call_command

output = DATA / "esacom_sqlite_export.json"
with output.open("w", encoding="utf-8", newline="\n") as fh:
    call_command(
        "dumpdata",
        natural_foreign=True,
        natural_primary=True,
        exclude=[
            "contenttypes",
            "auth.permission",
            "admin.logentry",
            "sessions.session",
            "token_blacklist",
        ],
        indent=2,
        stdout=fh,
    )
print(f"Exportación OK: {output}")
