from django.core.management.base import BaseCommand, CommandError

from integraciones.models import CargaExcel
from ventas.produccion import resumen_produccion_actual


def _campos(r):
    fija = r.get("fija") or {}
    movil = r.get("movil") or {}
    return (
        int(fija.get("completadas") or 0),
        int(fija.get("pendiente_instalacion") or 0),
        int(movil.get("principal") or 0),
        int(movil.get("adicional") or 0),
        int(movil.get("ppm") or 0),
    )


def _resumen_actual():
    p = resumen_produccion_actual()
    return {
        "fija": {
            "completadas": p["fija"]["completadas"],
            "pendiente_instalacion": p["fija"]["pendiente_instalacion"],
            "total_control": p["fija"]["total_control"],
        },
        "movil": {
            "principal": p["movil"]["principal"],
            "adicional": p["movil"]["adicional"],
            "ppm": p["movil"]["ppm"],
            "total": p["movil"]["total"],
        },
        "total_produccion": p["total_produccion"],
    }


class Command(BaseCommand):
    help = "Audita de forma atómica el último XLSX importado contra el snapshot CRM de ese mismo sync."

    def _print(self, titulo, r):
        f = r.get("fija") or {}
        m = r.get("movil") or {}
        self.stdout.write(f"\n{titulo}")
        self.stdout.write(
            f"  Fija: {f.get('completadas', 0)} + {f.get('pendiente_instalacion', 0)} = "
            f"{f.get('total_control', 0)} RGU"
        )
        self.stdout.write(
            f"  Móvil: Pr{m.get('principal', 0)} + A{m.get('adicional', 0)} + "
            f"PPM{m.get('ppm', 0)} = {m.get('total', 0)} líneas"
        )
        self.stdout.write(f"  TOTAL: {r.get('total_produccion', 0)}")

    def handle(self, *args, **options):
        carga = CargaExcel.objects.filter(
            tipo_base=CargaExcel.TipoBase.BASE_MATRIZ,
        ).exclude(resumen_produccion={}).order_by("-creado_en").first()
        if not carga:
            raise CommandError("No existe un snapshot ESACOM. Ejecuta verificar_sync_esacom --sincronizar.")

        snap = carga.resumen_produccion or {}
        fuente = snap.get("fuente_directa") or {}
        crm_sync = snap.get("crm_post_import") or {
            "fija": snap.get("fija") or {},
            "movil": snap.get("movil") or {},
            "total_produccion": snap.get("total_produccion") or 0,
        }
        if not fuente:
            raise CommandError(
                "El último snapshot fue creado por una build anterior y no contiene fuente_directa. "
                "Ejecuta una nueva sincronización con esta build."
            )

        self.stdout.write(self.style.SUCCESS("ESACOM · AUDITORÍA ATÓMICA DEL ÚLTIMO SYNC"))
        self.stdout.write(f"Carga: #{carga.id}")
        self.stdout.write(f"modifiedTime registrado: {carga.fuente_modificada_en or '-'}")
        self.stdout.write(f"SHA-256 XLSX: {carga.fuente_sha256 or '-'}")
        self._print("FUENTE DIRECTA · MISMO XLSX IMPORTADO", fuente)
        self._print("CRM · INMEDIATAMENTE POST-IMPORT", crm_sync)

        mismo_sync_ok = _campos(fuente) == _campos(crm_sync)
        if mismo_sync_ok:
            self.stdout.write(self.style.SUCCESS("\n[OK] MISMO XLSX = CRM POST-IMPORT. Importador validado atómicamente."))
        else:
            self.stdout.write(self.style.ERROR("\n[ERROR] MISMO XLSX != CRM POST-IMPORT. No cerrar UAT."))

        actual = _resumen_actual()
        self._print("CRM · ESTADO ACTUAL", actual)
        if _campos(actual) == _campos(crm_sync):
            self.stdout.write(self.style.SUCCESS("[OK] La BD no cambió desde el último sync."))
        else:
            self.stdout.write(self.style.WARNING(
                "[CAMBIO LOCAL] La BD cambió después del snapshot. Revisar sincronizaciones o ediciones posteriores."
            ))

        if not mismo_sync_ok:
            raise CommandError("La auditoría atómica detectó diferencia entre fuente e importador.")
