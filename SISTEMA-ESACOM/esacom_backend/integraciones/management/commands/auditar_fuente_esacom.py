import re
import unicodedata
from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime

from integraciones.models import CargaExcel

from integraciones.services.google_sheets import (
    escapar_titulo_hoja, leer_valores_multiples, obtener_metadata_spreadsheet,
)
from ventas.controles_manual import CONTROL_2508_DETALLE
from ventas.produccion import detalle_produccion_actual


def _norm(valor):
    texto = str(valor or "").strip().upper()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return " ".join(texto.split())


def _cabecera(valor):
    return re.sub(r"[^A-Z0-9]+", " ", _norm(valor)).strip()


def _mapa(headers):
    return {_cabecera(valor): idx for idx, valor in enumerate(headers)}


def _valor(row, mapa, nombre, default=""):
    idx = mapa.get(_cabecera(nombre))
    if idx is None or idx >= len(row):
        return default
    valor = row[idx]
    return default if valor is None else valor


def _valor_alias(row, mapa, *nombres, default=""):
    for nombre in nombres:
        idx = mapa.get(_cabecera(nombre))
        if idx is not None and idx < len(row):
            valor = row[idx]
            return default if valor is None else valor
    return default


def _tiene_alias(mapa, *nombres):
    return any(_cabecera(nombre) in mapa for nombre in nombres)


def _rgu(valor):
    if valor in (None, ""):
        return 0
    try:
        return max(int(float(str(valor).replace(",", "."))), 0)
    except (TypeError, ValueError):
        return 0


def _estado_fijo(valor):
    estado = _norm(valor)
    if "COMPLETAD" in estado or "INSTALAD" in estado:
        return "completadas"
    if "PENDIENTE" in estado and "INSTAL" in estado:
        return "pendiente_instalacion"
    return "fuera_control"


def _tipo_movil(valor):
    tipo = _norm(valor)
    if "PRINC" in tipo:
        return "principal"
    if "ADIC" in tipo:
        return "adicional"
    if tipo == "PPM" or " PPM" in f" {tipo}":
        return "ppm"
    return "otros"


_ESTADOS_POSITIVOS = (
    "PORTADO", "ACTIVADO", "ACTIVADA", "ACTIVO", "ACTIVA", "COMPLETADO", "COMPLETADA",
)
_ESTADOS_BLOQUEADOS = (
    "ANULAD", "CANCEL", "RECHAZ", "NO PORTAD", "PENDIENT", "POR PORTAR", "MANDATO",
)


def _movil_efectiva(estado, fecha_activacion):
    estado = _norm(estado)
    if estado and any(token in estado for token in _ESTADOS_BLOQUEADOS):
        return False
    if fecha_activacion not in (None, "", 0):
        return True
    return bool(estado and any(token in estado for token in _ESTADOS_POSITIVOS))


def _bucket():
    return {
        "fija": {"completadas": 0, "pendiente_instalacion": 0, "total_control": 0},
        "movil": {"principal": 0, "adicional": 0, "ppm": 0, "otros": 0, "total": 0, "pendientes": 0},
        "total_produccion": 0,
    }


def _cerrar(bucket):
    bucket["fija"]["total_control"] = (
        bucket["fija"]["completadas"] + bucket["fija"]["pendiente_instalacion"]
    )
    bucket["movil"]["total"] = (
        bucket["movil"]["principal"] + bucket["movil"]["adicional"] + bucket["movil"]["ppm"] + bucket["movil"]["otros"]
    )
    bucket["total_produccion"] = bucket["fija"]["total_control"] + bucket["movil"]["total"]
    return bucket


def _fuente_en_vivo():
    rango_fija = f"{escapar_titulo_hoja('Base de Ventas')}!A:BD"
    rango_movil = f"{escapar_titulo_hoja('Ventas Móvil')}!A:AH"
    rangos = leer_valores_multiples([rango_fija, rango_movil])
    fija_rows = rangos.get(rango_fija, [])
    movil_rows = rangos.get(rango_movil, [])
    if not fija_rows:
        raise RuntimeError("La hoja 'Base de Ventas' no devolvió filas.")
    if not movil_rows:
        raise RuntimeError("La hoja 'Ventas Móvil' no devolvió filas.")

    global_ = _bucket()
    por_sup = defaultdict(_bucket)
    por_sup_evt = defaultdict(lambda: defaultdict(_bucket))

    fmap = _mapa(fija_rows[0])
    requeridos_fija = ["SUPERVISOR", "NOMBRE EVT", "RGU", "ESTADO DE INSTALACION"]
    faltantes = [h for h in requeridos_fija if _cabecera(h) not in fmap]
    if faltantes:
        raise RuntimeError(f"Faltan columnas en Base de Ventas: {', '.join(faltantes)}")

    fija_filas_control = 0
    fija_sin_rgu = 0
    for row in fija_rows[1:]:
        estado = _estado_fijo(_valor(row, fmap, "ESTADO DE INSTALACION"))
        if estado == "fuera_control":
            continue
        rgu = _rgu(_valor(row, fmap, "RGU"))
        if rgu <= 0:
            fija_sin_rgu += 1
        sup = str(_valor(row, fmap, "SUPERVISOR") or "SIN SUPERVISOR").strip()
        evt = str(_valor(row, fmap, "NOMBRE EVT") or "SIN EJECUTIVO").strip()
        for b in (global_, por_sup[sup], por_sup_evt[sup][evt]):
            b["fija"][estado] += rgu
        fija_filas_control += 1

    mmap = _mapa(movil_rows[0])
    requeridos_movil = ["SUPERVISOR", "PPAL/ADICI.", "FECHA ACTIVACIÓN", "ESTADO"]
    faltantes = [h for h in requeridos_movil if _cabecera(h) not in mmap]
    if not _tiene_alias(mmap, "NOMBRE EVT", "NOMBRE EJECUTIVO"):
        faltantes.append("NOMBRE EVT/NOMBRE EJECUTIVO")
    if faltantes:
        raise RuntimeError(f"Faltan columnas en Ventas Móvil: {', '.join(faltantes)}")

    movil_filas = movil_efectivas = movil_pendientes = 0
    for row in movil_rows[1:]:
        tipo = _tipo_movil(_valor(row, mmap, "PPAL/ADICI."))
        evt_fuente = _valor_alias(row, mmap, "NOMBRE EVT", "NOMBRE EJECUTIVO")
        # Filas de plantilla o fórmulas vacías no forman parte del universo móvil.
        if tipo == "otros" and not any(str(x or "").strip() for x in (_valor(row, mmap, "SUPERVISOR"), evt_fuente)):
            continue
        if tipo == "otros":
            # Se conserva como auditable si realmente trae datos.
            pass
        movil_filas += 1
        estado = _valor(row, mmap, "ESTADO")
        fecha_activacion = _valor(row, mmap, "FECHA ACTIVACIÓN")
        sup = str(_valor(row, mmap, "SUPERVISOR") or "SIN SUPERVISOR").strip()
        evt = str(evt_fuente or "SIN EJECUTIVO").strip()
        if not _movil_efectiva(estado, fecha_activacion):
            movil_pendientes += 1
            for b in (global_, por_sup[sup], por_sup_evt[sup][evt]):
                b["movil"]["pendientes"] += 1
            continue
        movil_efectivas += 1
        for b in (global_, por_sup[sup], por_sup_evt[sup][evt]):
            b["movil"][tipo] += 1

    _cerrar(global_)
    for b in por_sup.values():
        _cerrar(b)
    for ejecutivos in por_sup_evt.values():
        for b in ejecutivos.values():
            _cerrar(b)

    metadata = obtener_metadata_spreadsheet()
    return {
        "metadata": metadata,
        "global": global_,
        "supervisores": dict(por_sup),
        "ejecutivos_por_supervisor": {k: dict(v) for k, v in por_sup_evt.items()},
        "trazabilidad": {
            "filas_fija_control": fija_filas_control,
            "fija_sin_rgu": fija_sin_rgu,
            "filas_movil": movil_filas,
            "movil_efectivas": movil_efectivas,
            "movil_pendientes": movil_pendientes,
        },
    }


def _manual_2508():
    global_ = _bucket()
    por_sup = defaultdict(_bucket)
    por_sup_evt = defaultdict(lambda: defaultdict(_bucket))
    for sup, ejecutivos in CONTROL_2508_DETALLE.items():
        for evt, esperado in ejecutivos.items():
            for b in (global_, por_sup[sup], por_sup_evt[sup][evt]):
                b["fija"]["completadas"] += esperado["fija"]["completadas"]
                b["fija"]["pendiente_instalacion"] += esperado["fija"]["pendiente_instalacion"]
                for tipo in ("principal", "adicional", "ppm"):
                    b["movil"][tipo] += esperado["movil"][tipo]
    _cerrar(global_)
    for b in por_sup.values():
        _cerrar(b)
    for ejecutivos in por_sup_evt.values():
        for b in ejecutivos.values():
            _cerrar(b)
    return {
        "global": global_,
        "supervisores": dict(por_sup),
        "ejecutivos_por_supervisor": {k: dict(v) for k, v in por_sup_evt.items()},
    }


def _campos(bucket):
    return (
        bucket["fija"]["completadas"], bucket["fija"]["pendiente_instalacion"],
        bucket["movil"]["principal"], bucket["movil"]["adicional"], bucket["movil"]["ppm"],
    )


def _desde_db_bucket(bucket):
    return {
        "fija": {
            "completadas": bucket["fija"]["completadas"],
            "pendiente_instalacion": bucket["fija"]["pendiente_instalacion"],
            "total_control": bucket["fija"]["total_control"],
        },
        "movil": {
            "principal": bucket["movil"]["principal"],
            "adicional": bucket["movil"]["adicional"],
            "ppm": bucket["movil"]["ppm"],
            "otros": bucket["movil"].get("otros", 0),
            "total": bucket["movil"]["total"],
            "pendientes": bucket["movil"].get("pendiente_activacion", 0),
        },
        "total_produccion": bucket["total_produccion"],
    }


class Command(BaseCommand):
    help = (
        "Lee Base de Ventas y Ventas Móvil DIRECTAMENTE desde Google Sheets, "
        "recalcula el control de Gerencia y lo compara con la BD local."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--control-2508", action="store_true",
            help="Compara además contra las 48 filas de las tablas manuales entregadas el 25/08/2026.",
        )
        parser.add_argument(
            "--solo-diferencias", action="store_true",
            help="Muestra el detalle por Ejecutivo únicamente cuando hay diferencias.",
        )
        parser.add_argument(
            "--exigir-control-2508", action="store_true",
            help=(
                "Hace que una diferencia contra el control manual histórico del 25/08 "
                "sea fallo UAT. Sin esta opción, el control se usa como snapshot comparativo."
            ),
        )

    def _resumen(self, titulo, b):
        self.stdout.write(f"\n{titulo}")
        self.stdout.write(
            f"  Fija: {b['fija']['completadas']} completada + "
            f"{b['fija']['pendiente_instalacion']} pendiente = {b['fija']['total_control']} RGU"
        )
        self.stdout.write(
            f"  Móvil: {b['movil']['principal']} principal + {b['movil']['adicional']} adicional + "
            f"{b['movil']['ppm']} PPM = {b['movil']['total']} líneas"
        )
        self.stdout.write(f"  TOTAL: {b['total_produccion']}")

    def _comparar(self, etiqueta, actual, esperado):
        ok = _campos(actual) == _campos(esperado)
        marca = "OK" if ok else "DIF"
        texto = (
            f"  {etiqueta}: fija {actual['fija']['completadas']}/{actual['fija']['pendiente_instalacion']} "
            f"vs {esperado['fija']['completadas']}/{esperado['fija']['pendiente_instalacion']} · "
            f"móvil Pr{actual['movil']['principal']} A{actual['movil']['adicional']} PPM{actual['movil']['ppm']} "
            f"vs Pr{esperado['movil']['principal']} A{esperado['movil']['adicional']} PPM{esperado['movil']['ppm']} [{marca}]"
        )
        self.stdout.write(self.style.SUCCESS(texto) if ok else self.style.ERROR(texto))
        return ok

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("ESACOM · AUDITORÍA DIRECTA DE FUENTE"))
        self.stdout.write("Lee Google Sheets sin usar la BD para el cálculo de origen.")
        self.stdout.write("Claro NO participa.")

        try:
            fuente = _fuente_en_vivo()
        except Exception as exc:
            raise CommandError(f"No fue posible auditar la fuente ESACOM: {exc}") from exc

        meta = fuente.get("metadata") or {}
        self.stdout.write(
            f"Origen descargado: {meta.get('name', 'Ingreso de Ventas')} · "
            f"modifiedTime {meta.get('modifiedTime', '-')}"
        )

        ultima_carga = CargaExcel.objects.filter(
            tipo_base=CargaExcel.TipoBase.BASE_MATRIZ,
        ).order_by("-creado_en").first()
        live_dt = parse_datetime(str(meta.get("modifiedTime") or ""))
        sync_dt = getattr(ultima_carga, "fuente_modificada_en", None) if ultima_carga else None
        fuente_cambio_post_sync = bool(live_dt and sync_dt and live_dt > sync_dt)
        if fuente_cambio_post_sync:
            self.stdout.write(self.style.WARNING(
                f"[EVOLUCIÓN POST-SYNC] La fuente viva ({live_dt}) es más nueva que el XLSX "
                f"sincronizado en la carga #{ultima_carga.id} ({sync_dt}). "
                "Una diferencia vivo vs CRM en esta ejecución NO demuestra un error del importador."
            ))
            self.stdout.write(
                "Usa 'auditar_ultimo_sync_esacom' para validar de forma atómica el mismo XLSX importado."
            )
        self._resumen("GOOGLE SHEETS · CÁLCULO DIRECTO", fuente["global"])
        tr = fuente["trazabilidad"]
        self.stdout.write(
            f"  Trazabilidad: {tr['filas_fija_control']} filas fija control · "
            f"{tr['fija_sin_rgu']} sin RGU · {tr['filas_movil']} filas móvil · "
            f"{tr['movil_efectivas']} efectivas · {tr['movil_pendientes']} pendientes"
        )

        db_raw = detalle_produccion_actual()
        db = {
            "global": _desde_db_bucket(db_raw["global"]),
            "supervisores": {k: _desde_db_bucket(v) for k, v in db_raw["supervisores"].items()},
            "ejecutivos_por_supervisor": {
                sup: {evt: _desde_db_bucket(v) for evt, v in ejecutivos.items()}
                for sup, ejecutivos in db_raw.get("ejecutivos_por_supervisor", {}).items()
            },
        }
        self._resumen("BD CRM · DESPUÉS DEL ÚLTIMO SYNC", db["global"])
        comparacion_global = self._comparar("FUENTE vs CRM", fuente["global"], db["global"])
        ok = comparacion_global or fuente_cambio_post_sync
        if not comparacion_global and fuente_cambio_post_sync:
            self.stdout.write(self.style.WARNING(
                "  [EVOLUCIÓN] Diferencia esperable porque la matriz cambió después del último sync; "
                "no se marca como fallo del importador."
            ))

        # La igualdad global no basta: dos diferencias opuestas podrían
        # compensarse. Auditamos también supervisor y Ejecutivo sobre la unión
        # completa del universo vivo.
        fuente_sup_all = {_norm(k): (k, v) for k, v in fuente["supervisores"].items()}
        db_sup_all = {_norm(k): (k, v) for k, v in db["supervisores"].items()}
        diferencias_db = 0
        self.stdout.write("\nALINEACIÓN FUENTE ↔ CRM · DETALLE VIVO")
        for sup_key in sorted(set(fuente_sup_all) | set(db_sup_all)):
            f_nombre, f_bucket = fuente_sup_all.get(sup_key, (sup_key, _bucket()))
            d_nombre, d_bucket = db_sup_all.get(sup_key, (f_nombre, _bucket()))
            _cerrar(f_bucket)
            _cerrar(d_bucket)
            if _campos(f_bucket) != _campos(d_bucket):
                if fuente_cambio_post_sync:
                    self.stdout.write(self.style.WARNING(
                        f"  SUP {f_nombre}: FUENTE F{f_bucket['fija']['completadas']}/{f_bucket['fija']['pendiente_instalacion']} "
                        f"M{f_bucket['movil']['principal']}/{f_bucket['movil']['adicional']}/{f_bucket['movil']['ppm']} · "
                        f"CRM F{d_bucket['fija']['completadas']}/{d_bucket['fija']['pendiente_instalacion']} "
                        f"M{d_bucket['movil']['principal']}/{d_bucket['movil']['adicional']}/{d_bucket['movil']['ppm']} [EVOL POST-SYNC]"
                    ))
                else:
                    diferencias_db += 1
                    ok = False
                    self.stdout.write(self.style.ERROR(
                        f"  SUP {f_nombre}: FUENTE F{f_bucket['fija']['completadas']}/{f_bucket['fija']['pendiente_instalacion']} "
                        f"M{f_bucket['movil']['principal']}/{f_bucket['movil']['adicional']}/{f_bucket['movil']['ppm']} · "
                        f"CRM F{d_bucket['fija']['completadas']}/{d_bucket['fija']['pendiente_instalacion']} "
                        f"M{d_bucket['movil']['principal']}/{d_bucket['movil']['adicional']}/{d_bucket['movil']['ppm']} [ERROR]"
                    ))

            f_evts = fuente["ejecutivos_por_supervisor"].get(f_nombre, {})
            d_evts = db["ejecutivos_por_supervisor"].get(d_nombre, {})
            f_evts_n = {_norm(k): (k, v) for k, v in f_evts.items()}
            d_evts_n = {_norm(k): (k, v) for k, v in d_evts.items()}
            for evt_key in sorted(set(f_evts_n) | set(d_evts_n)):
                fe_nombre, fe = f_evts_n.get(evt_key, (evt_key, _bucket()))
                _, de = d_evts_n.get(evt_key, (fe_nombre, _bucket()))
                _cerrar(fe)
                _cerrar(de)
                if _campos(fe) != _campos(de):
                    if fuente_cambio_post_sync:
                        self.stdout.write(self.style.WARNING(
                            f"    EVT {f_nombre} · {fe_nombre}: "
                            f"FUENTE F{fe['fija']['completadas']}/{fe['fija']['pendiente_instalacion']} "
                            f"M{fe['movil']['principal']}/{fe['movil']['adicional']}/{fe['movil']['ppm']} · "
                            f"CRM F{de['fija']['completadas']}/{de['fija']['pendiente_instalacion']} "
                            f"M{de['movil']['principal']}/{de['movil']['adicional']}/{de['movil']['ppm']} [EVOL POST-SYNC]"
                        ))
                    else:
                        diferencias_db += 1
                        ok = False
                        self.stdout.write(self.style.ERROR(
                            f"    EVT {f_nombre} · {fe_nombre}: "
                            f"FUENTE F{fe['fija']['completadas']}/{fe['fija']['pendiente_instalacion']} "
                            f"M{fe['movil']['principal']}/{fe['movil']['adicional']}/{fe['movil']['ppm']} · "
                            f"CRM F{de['fija']['completadas']}/{de['fija']['pendiente_instalacion']} "
                            f"M{de['movil']['principal']}/{de['movil']['adicional']}/{de['movil']['ppm']} [ERROR]"
                        ))
        if diferencias_db == 0:
            self.stdout.write(self.style.SUCCESS("  [OK] Fuente y CRM coinciden global, supervisor y Ejecutivo."))

        if options.get("control_2508"):
            manual = _manual_2508()
            self._resumen("CONTROL MANUAL GERENCIA · 25/08 (SNAPSHOT HISTÓRICO)", manual["global"])
            manual_global_ok = _campos(fuente["global"]) == _campos(manual["global"])
            self._comparar("FUENTE vs MANUAL", fuente["global"], manual["global"])
            if not manual_global_ok:
                self.stdout.write(self.style.WARNING(
                    "  [EVOLUCIÓN] El control manual es una foto anterior del día. "
                    "No se fuerza el vivo a 837; la condición crítica es FUENTE = CRM."
                ))
                if options.get("exigir_control_2508"):
                    ok = False

            fuente_sup = {_norm(k): (k, v) for k, v in fuente["ejecutivos_por_supervisor"].items()}
            db_sup = {_norm(k): (k, v) for k, v in db["ejecutivos_por_supervisor"].items()}
            evoluciones = 0
            errores_crm = 0
            comparados = 0
            self.stdout.write("\nDETALLE 25/08 · 48 FILAS GERENCIA")
            for sup, esperados in manual["ejecutivos_por_supervisor"].items():
                f_sup = fuente_sup.get(_norm(sup), (sup, {}))[1]
                d_sup = db_sup.get(_norm(sup), (sup, {}))[1]
                f_norm = {_norm(k): (k, v) for k, v in f_sup.items()}
                d_norm = {_norm(k): (k, v) for k, v in d_sup.items()}
                for evt, esperado in esperados.items():
                    actual_fuente = f_norm.get(_norm(evt), (evt, _bucket()))[1]
                    actual_db = d_norm.get(_norm(evt), (evt, _bucket()))[1]
                    _cerrar(actual_fuente)
                    _cerrar(actual_db)
                    fuente_db_ok = _campos(actual_fuente) == _campos(actual_db)
                    manual_ok = _campos(actual_fuente) == _campos(esperado)
                    comparados += 1
                    if not fuente_db_ok and not fuente_cambio_post_sync:
                        errores_crm += 1
                        ok = False
                    if not manual_ok:
                        evoluciones += 1
                        if options.get("exigir_control_2508"):
                            ok = False
                    if options.get("solo_diferencias") and fuente_db_ok and manual_ok:
                        continue
                    marca = (
                        "OK" if (fuente_db_ok and manual_ok)
                        else "EVOL-SYNC" if (not fuente_db_ok and fuente_cambio_post_sync)
                        else "ERROR" if not fuente_db_ok
                        else "EVOL"
                    )
                    texto = (
                        f"  {sup} · {evt}: "
                        f"FUENTE F{actual_fuente['fija']['completadas']}/{actual_fuente['fija']['pendiente_instalacion']} "
                        f"M{actual_fuente['movil']['principal']}/{actual_fuente['movil']['adicional']}/{actual_fuente['movil']['ppm']} · "
                        f"CRM F{actual_db['fija']['completadas']}/{actual_db['fija']['pendiente_instalacion']} "
                        f"M{actual_db['movil']['principal']}/{actual_db['movil']['adicional']}/{actual_db['movil']['ppm']} · "
                        f"MANUAL F{esperado['fija']['completadas']}/{esperado['fija']['pendiente_instalacion']} "
                        f"M{esperado['movil']['principal']}/{esperado['movil']['adicional']}/{esperado['movil']['ppm']} [{marca}]"
                    )
                    if not fuente_db_ok and fuente_cambio_post_sync:
                        self.stdout.write(self.style.WARNING(texto))
                    elif not fuente_db_ok:
                        self.stdout.write(self.style.ERROR(texto))
                    elif not manual_ok:
                        self.stdout.write(self.style.WARNING(texto))
                    else:
                        self.stdout.write(self.style.SUCCESS(texto))
            if errores_crm:
                self.stdout.write(self.style.ERROR(
                    f"  [ERROR] {errores_crm} filas tienen FUENTE != CRM. No cerrar UAT."
                ))
            if evoluciones:
                self.stdout.write(self.style.WARNING(
                    f"  [EVOLUCIÓN] {evoluciones} de {comparados} filas cambiaron respecto del snapshot manual; "
                    "esto no es error si FUENTE = CRM."
                ))
            if errores_crm == 0 and evoluciones == 0:
                self.stdout.write(self.style.SUCCESS(f"  [OK] Las {comparados} filas coinciden FUENTE = CRM = MANUAL."))

        if ok:
            if fuente_cambio_post_sync and not comparacion_global:
                self.stdout.write(self.style.WARNING(
                    "\n[EVOLUCIÓN POST-SYNC] La fuente viva avanzó después de la última importación. "
                    "La validación crítica debe hacerse con auditar_ultimo_sync_esacom."
                ))
            else:
                self.stdout.write(self.style.SUCCESS(
                    "\n[OK] FUENTE ESACOM = CRM. La producción viva queda validada para el momento de la descarga."
                ))
        else:
            self.stdout.write(self.style.ERROR("\n[DIFERENCIAS] No cerrar UAT todavía. Revisar las filas indicadas."))
