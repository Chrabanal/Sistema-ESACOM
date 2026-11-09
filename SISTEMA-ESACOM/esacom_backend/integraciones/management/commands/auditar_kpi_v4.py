from __future__ import annotations

import datetime
import os
from collections import Counter
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP

import openpyxl
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from integraciones.models import CargaExcel, KPIRegistro
from integraciones.kpi_population import diferencias_poblacion
from integraciones.views import _extraer_focos_y_metas_kpi
from integraciones.management.commands.importar_kpi import (
    Command as ImportarKpiCommand,
    KPI_A_ESTADO,
    N_BOLETA_A_CORTE,
    a_entero,
    camada_a_mes_ano,
    normalizar,
)
from ventas.models import Corte, Venta
from ventas.services import resumen_kpi, filtrar_cortes_kpi_operativos


CONTROL_2408 = {
    "B1": {
        "mes": "2026-07",
        "meta": Decimal("85"),
        "pago": 682,
        "no_pago": 51,
        "fuera_plazo": 19,
        "pendiente": 77,
        "sin_boleta": 0,
        "total": 829,
        "kpi": Decimal("82.27"),
        "proyeccion": Decimal("89.91"),
        "q_meta": 23,
    },
    "B2": {
        "mes": "2026-06",
        "meta": Decimal("83"),
        "pago": 694,
        "no_pago": 146,
        "fuera_plazo": 19,
        "pendiente": 37,
        "sin_boleta": 18,
        "total": 896,
        "kpi": Decimal("77.46"),
        "proyeccion": Decimal("80.65"),
        "q_meta": 50,
    },
    "B3": {
        "mes": "2026-05",
        "meta": Decimal("78"),
        "pago": 528,
        "no_pago": 163,
        "fuera_plazo": 9,
        "pendiente": 38,
        "sin_boleta": 16,
        "total": 738,
        "kpi": Decimal("71.54"),
        "proyeccion": Decimal("75.23"),
        "q_meta": 48,
    },
}


def _pct(n, d):
    if not d:
        return Decimal("0.00")
    return (Decimal(n) / Decimal(d) * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _proyeccion(pago, pendiente, total):
    if not total:
        return Decimal("0.00")
    tasa = Decimal(pago) / Decimal(total)
    pago_proyectado = Decimal(pago) + (tasa * Decimal(pendiente))
    return _pct(pago_proyectado, total)


def _q_meta(pago, total, meta):
    faltan = (Decimal(meta) / 100 * Decimal(total)) - Decimal(pago)
    if faltan <= 0:
        return 0
    return int(faltan.to_integral_value(rounding=ROUND_CEILING))


def _resumen_desde_contador(contador: Counter, meta: Decimal):
    pago = int(contador.get(Corte.EstadoPago.PAGADO, 0))
    pendiente = int(contador.get(Corte.EstadoPago.PENDIENTE, 0))
    no_pago = int(contador.get(Corte.EstadoPago.NO_PAGO, 0))
    fuera = int(contador.get(Corte.EstadoPago.FUERA_PLAZO, 0))
    sb = int(contador.get(Corte.EstadoPago.SIN_BOLETA, 0))
    total = pago + pendiente + no_pago + fuera
    return {
        "pago": pago,
        "pendiente": pendiente,
        "no_pago": no_pago,
        "fuera_plazo": fuera,
        "sin_boleta": sb,
        "total": total,
        "kpi": _pct(pago, total),
        "proyeccion": _proyeccion(pago, pendiente, total),
        "q_meta": _q_meta(pago, total, meta),
    }


def _igual_control(real: dict, esperado: dict) -> bool:
    campos = ("pago", "pendiente", "no_pago", "fuera_plazo", "sin_boleta", "total", "q_meta")
    if any(real.get(c) != esperado.get(c) for c in campos):
        return False
    return real.get("kpi") == esperado.get("kpi") and real.get("proyeccion") == esperado.get("proyeccion")


def _resumen_registros_kpi(qs, meta: Decimal) -> dict:
    """Resumen del snapshot normalizado sin depender de Corte.

    Se usa para construir el esperado de la población que sí cruzó con ESACOM.
    De esta forma un Corte residual de una carga anterior jamás puede quedar
    oculto detrás de un gate relajado.
    """
    contador = Counter()
    for reg in qs:
        if not reg.es_medible or reg.rgu is None:
            continue
        contador[reg.estado_normalizado] += int(reg.rgu)
    return _resumen_desde_contador(contador, meta)


class Command(BaseCommand):
    help = (
        "Audita KPI V4 contra el XLSX oficial. Puede probar la importación completa dentro de una "
        "transacción que se revierte por defecto para no ensuciar el histórico UAT."
    )

    def add_arguments(self, parser):
        parser.add_argument("archivo", type=str)
        parser.add_argument("--fecha-corte", type=str, default="2026-08-24")
        parser.add_argument("--dia-reporte", type=str, default="LUNES")
        parser.add_argument("--control-2408", action="store_true")
        parser.add_argument("--probar-importacion", action="store_true")
        parser.add_argument(
            "--persistir",
            action="store_true",
            help="Con --probar-importacion, conserva la carga. Sin esta bandera la prueba hace rollback.",
        )

    def handle(self, *args, **opts):
        path = opts["archivo"]
        if not os.path.exists(path):
            raise CommandError(f"No existe el archivo: {path}")

        try:
            fecha_corte = datetime.date.fromisoformat(opts["fecha_corte"])
        except ValueError as exc:
            raise CommandError("--fecha-corte debe ser AAAA-MM-DD") from exc
        dia = str(opts["dia_reporte"] or "OTRO").upper()
        if dia not in CargaExcel.DiaReporte.values:
            raise CommandError("--dia-reporte debe ser LUNES, MIERCOLES, JUEVES u OTRO")

        metadata = _extraer_focos_y_metas_kpi(path)
        focos = {
            "B1": metadata.get("foco_b1") or "",
            "B2": metadata.get("foco_b2") or "",
            "B3": metadata.get("foco_b3") or "",
        }
        metas = {
            "B1": Decimal(str(metadata.get("meta_b1") or 0)),
            "B2": Decimal(str(metadata.get("meta_b2") or 0)),
            "B3": Decimal(str(metadata.get("meta_b3") or 0)),
        }

        self.stdout.write("ESACOM · AUDITORÍA KPI V4.2")
        self.stdout.write(f"Archivo: {os.path.basename(path)}")
        self.stdout.write(
            "Focos: " + " · ".join(f"{b} {focos[b] or '-'}" for b in ("B1", "B2", "B3"))
        )
        self.stdout.write(
            "Metas: " + " · ".join(f"{b} {metas[b]}%" for b in ("B1", "B2", "B3"))
        )

        directo, info_archivo = self._leer_xlsx(path, focos, metas)
        self.stdout.write("\nXLSX OFICIAL · CÁLCULO DIRECTO")
        for b in ("B1", "B2", "B3"):
            r = directo[b]
            self.stdout.write(
                f"  {b} {focos[b]} · Pago {r['pago']} · No Pago {r['no_pago']} · "
                f"Fuera {r['fuera_plazo']} · Pend {r['pendiente']} · S/B {r['sin_boleta']} · "
                f"Total {r['total']} · KPI {r['kpi']}% · Proy {r['proyeccion']}% · Q meta {r['q_meta']}"
            )
        self.stdout.write(
            f"  Filas negocio {info_archivo['filas_negocio']} · claves únicas {info_archivo['claves_unicas']} · "
            f"duplicados {info_archivo['duplicados']} · MarcaMes 1/0/otro "
            f"{info_archivo['marca_mes_1']}/{info_archivo['marca_mes_0']}/{info_archivo['marca_mes_otro']}"
        )

        if opts["control_2408"]:
            errores = []
            for b in ("B1", "B2", "B3"):
                esperado = CONTROL_2408[b]
                if focos[b] != esperado["mes"] or metas[b] != esperado["meta"] or not _igual_control(directo[b], esperado):
                    errores.append(b)
            if errores:
                raise CommandError(
                    "El XLSX no coincide con el control oficial 24/08 en: " + ", ".join(errores)
                )
            self.stdout.write(self.style.SUCCESS("[OK] XLSX = CONTROL OFICIAL 24/08 para B1/B2/B3."))

        if not opts["probar_importacion"]:
            return

        self._probar_importacion(
            path=path,
            fecha_corte=fecha_corte,
            dia=dia,
            focos=focos,
            metas=metas,
            directo=directo,
            persistir=bool(opts["persistir"]),
        )

    def _leer_xlsx(self, path, focos, metas):
        try:
            wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
        except Exception as exc:
            raise CommandError(f"No se pudo abrir el XLSX: {exc}") from exc
        try:
            if "BASE" not in wb.sheetnames:
                raise CommandError("El archivo no contiene la hoja BASE.")
            ws = wb["BASE"]
            headers = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
            idx = {normalizar(h): i for i, h in enumerate(headers) if h}
            requeridas = ["NUM PEDIDO", "CAMADA", "N BOLETA", "KPI", "RGU", "MARCA DE MES"]
            faltan = [h for h in requeridas if h not in idx]
            if faltan:
                raise CommandError("Faltan columnas BASE: " + ", ".join(faltan))

            def campo(row, nombre):
                i = idx.get(normalizar(nombre))
                return row[i] if i is not None and i < len(row) else None

            contadores = {"B1": Counter(), "B2": Counter(), "B3": Counter()}
            filas_negocio = 0
            vistos = set()
            duplicados = 0
            marca_uno = 0
            marca_cero = 0
            marca_otro = 0
            for row in ws.iter_rows(min_row=2, values_only=True):
                pedido = str(campo(row, "NUM_PEDIDO") or "").strip()
                if not pedido:
                    continue
                filas_negocio += 1
                camada = camada_a_mes_ano(campo(row, "CAMADA"))
                boleta = N_BOLETA_A_CORTE.get(a_entero(campo(row, "N_BOLETA")))
                clave = (pedido, camada, boleta)
                if clave in vistos:
                    duplicados += 1
                vistos.add(clave)
                if not camada or not boleta or camada != focos.get(boleta):
                    continue
                marca_mes = a_entero(campo(row, "Marca de mes"))
                if marca_mes == 1:
                    marca_uno += 1
                elif marca_mes == 0:
                    marca_cero += 1
                else:
                    marca_otro += 1
                if marca_mes != 1:
                    continue
                estado = KPI_A_ESTADO.get(normalizar(campo(row, "kpi")))
                if estado is None:
                    raise CommandError(f"Estado KPI desconocido en pedido {pedido}: {campo(row, 'kpi')}")
                rgu = a_entero(campo(row, "RGU"))
                if rgu is None:
                    raise CommandError(f"Fila KPI sin RGU en pedido {pedido}")
                contadores[boleta][estado] += int(rgu)

            resumen = {
                b: _resumen_desde_contador(contadores[b], metas[b]) for b in ("B1", "B2", "B3")
            }
            return resumen, {
                "filas_negocio": filas_negocio,
                "claves_unicas": len(vistos),
                "duplicados": duplicados,
                "marca_mes_1": marca_uno,
                "marca_mes_0": marca_cero,
                "marca_mes_otro": marca_otro,
            }
        finally:
            wb.close()

    def _probar_importacion(self, *, path, fecha_corte, dia, focos, metas, directo, persistir):
        self.stdout.write("\nIMPORTACIÓN V4 · PRUEBA TRANSACCIONAL")
        with transaction.atomic():
            carga = CargaExcel.objects.create(
                origen=CargaExcel.Origen.MANUAL,
                tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
                archivo_nombre=os.path.basename(path),
                fecha_corte=fecha_corte,
                dia_reporte=dia,
                foco_b1=focos["B1"], foco_b2=focos["B2"], foco_b3=focos["B3"],
                meta_b1=metas["B1"], meta_b2=metas["B2"], meta_b3=metas["B3"],
            )
            cmd = ImportarKpiCommand()
            cmd.stdout = self.stdout
            cmd.stderr = self.stderr
            cmd.handle(
                archivo=path,
                dry_run=False,
                limite=None,
                hoja="BASE",
                carga_id=carga.id,
                usuario_rut="",
                archivo_nombre=os.path.basename(path),
                fecha_corte=fecha_corte.isoformat(),
                dia_reporte=dia,
            )

            self.stdout.write(
                f"  Importador: filas {cmd.resumen['filas_leidas']} · cruces {cmd.resumen['coincidencias']} · "
                f"sin venta {cmd.resumen['sin_venta_propia']} · conflictos ESACOM {cmd.resumen.get('pedidos_conflicto_fuente', 0)} · "
                f"MarcaMes 1/0/ausente {cmd.resumen.get('marca_mes_1', 0)}/{cmd.resumen.get('marca_mes_0', 0)}/{cmd.resumen.get('marca_mes_ausente', 0)}"
            )

            errores_snapshot = []
            for b in ("B1", "B2", "B3"):
                qs = KPIRegistro.objects.filter(carga=carga, camada=focos[b], boleta=b)
                contador = Counter()
                fuera = 0
                for reg in qs:
                    rgu = int(reg.rgu or 0)
                    if not reg.es_medible:
                        fuera += rgu
                        continue
                    contador[reg.estado_normalizado] += rgu
                r = _resumen_desde_contador(contador, metas[b])
                ok = _igual_control(r, directo[b])
                self.stdout.write(
                    f"  Snapshot {b}: KPI {r['kpi']}% · Proy {r['proyeccion']}% · Total {r['total']} · "
                    f"S/B {r['sin_boleta']} · fuera medición {fuera} [{'OK' if ok else 'DIF'}]"
                )
                if not ok:
                    errores_snapshot.append(b)

            if errores_snapshot:
                raise CommandError(
                    "KPIRegistro no reproduce el XLSX en: " + ", ".join(errores_snapshot)
                )
            self.stdout.write(self.style.SUCCESS("[OK] XLSX = KPIRegistro normalizado."))

            # CAPA OPERATIVA VIGENTE (Corte)
            # --------------------------------
            # Corte es una tabla de "último estado" por venta/camada/boleta.
            # La comparación se hace contra las filas del mismo KPIRegistro que sí cruzaron.
            errores_backend = []
            for b in ("B1", "B2", "B3"):
                registros_foco = KPIRegistro.objects.filter(
                    carga=carga, camada=focos[b], boleta=b
                )
                registros_cruzados = registros_foco.filter(cruce_ok=True)
                esperado_cruzado = _resumen_registros_kpi(registros_cruzados, metas[b])

                qs = Corte.objects.filter(
                    carga_kpi=carga, mes_ano=focos[b], boleta=b
                )
                r = resumen_kpi(qs)
                self.stdout.write(
                    f"  Corte vigente {b}: Pago {r['pagadas']} · Pend {r['pendientes']} · NoPago {r['no_pago']} · "
                    f"Fuera {r['fuera_plazo']} · S/B {r['sin_boleta']} · Total {r['total']} · "
                    f"KPI {r['pct_cumplimiento']:.2f}% · Proy {r['pct_proyectado']:.2f}%"
                )

                # La identidad entre KPIRegistro y Corte NO es el texto de
                # NUM_PEDIDO. Ambos objetos internos quedan relacionados con
                # la Venta ESACOM, y Corte además posee una restricción única
                # por (venta, camada, boleta). Comparar strings de pedido aquí
                # puede producir un falso 1x1 si el identificador textual de la
                # Venta fue canonizado/corregido después de un histórico.
                #
                # El gate correcto usa la misma clave relacional que protege la
                # tabla Corte: venta_id + camada + boleta. NUM_PEDIDO se conserva
                # únicamente como trazabilidad y se informa como aviso si difiere.
                claves_esperadas = set(
                    registros_cruzados.values_list("venta_id", "camada", "boleta")
                )
                claves_corte = set(
                    qs.values_list("venta_id", "mes_ano", "boleta")
                )
                faltantes_set, sobrantes_set = diferencias_poblacion(claves_esperadas, claves_corte)
                faltantes_corte = sorted(faltantes_set)
                sobrantes_corte = sorted(sobrantes_set)
                if faltantes_corte or sobrantes_corte:
                    errores_backend.append(b)
                    self.stdout.write(self.style.ERROR(
                        f"    [ERROR POBLACIÓN] {b}: faltan {len(faltantes_corte)} · sobran {len(sobrantes_corte)} "
                        f"claves Venta+camada+boleta respecto del snapshot cruzado."
                    ))
                    if faltantes_corte:
                        self.stdout.write(self.style.ERROR(
                            f"      faltantes muestra: {faltantes_corte[:5]}"
                        ))
                    if sobrantes_corte:
                        self.stdout.write(self.style.ERROR(
                            f"      sobrantes muestra: {sobrantes_corte[:5]}"
                        ))

                # Diagnóstico no bloqueante de NUM_PEDIDO. Si una misma Venta
                # está correctamente enlazada pero su texto de pedido cambió,
                # queremos verlo sin confundirlo con una pérdida de población.
                pedido_por_venta_snapshot = {
                    venta_id: pedido
                    for venta_id, pedido in registros_cruzados.values_list("venta_id", "num_pedido")
                    if venta_id is not None
                }
                pedido_por_venta_corte = {
                    venta_id: pedido
                    for venta_id, pedido in qs.values_list("venta_id", "venta__n_pedido")
                    if venta_id is not None
                }
                drift_pedido = [
                    (venta_id, pedido_por_venta_snapshot[venta_id], pedido_por_venta_corte.get(venta_id))
                    for venta_id in sorted(set(pedido_por_venta_snapshot) & set(pedido_por_venta_corte))
                    if pedido_por_venta_snapshot[venta_id] != pedido_por_venta_corte.get(venta_id)
                ]
                if drift_pedido:
                    self.stdout.write(self.style.WARNING(
                        f"    [TRAZABILIDAD N° PEDIDO] {b}: {len(drift_pedido)} Venta(s) tienen texto de pedido distinto "
                        f"entre snapshot y maestro ESACOM; la relación por venta_id sigue íntegra. Muestra: {drift_pedido[:3]}"
                    ))

                verificados_foco = qs.filter(verificado_en_andes=True).count()
                if verificados_foco == 0:
                    real_cmp = {
                        "pago": r["pagadas"], "pendiente": r["pendientes"],
                        "no_pago": r["no_pago"], "fuera_plazo": r["fuera_plazo"],
                        "sin_boleta": r["sin_boleta"], "total": r["total"],
                        "kpi": Decimal(str(r["pct_cumplimiento"])),
                        "proyeccion": Decimal(str(r["pct_proyectado"])),
                        "q_meta": r["faltan_para_meta"],
                    }
                    if not _igual_control(real_cmp, esperado_cruzado):
                        errores_backend.append(b)
                        self.stdout.write(self.style.ERROR(
                            f"    [ERROR ESTADO/RGU] {b}: Corte vigente no reproduce KPIRegistro cruzado del mismo snapshot."
                        ))
                else:
                    self.stdout.write(self.style.WARNING(
                        f"    [AVISO] {b}: {verificados_foco} cortes tienen corrección manual Andes; "
                        "la población debe coincidir, pero estado_pago operativo puede diferir de Claro."
                    ))

                sin_cruce = registros_foco.filter(cruce_ok=False)
                sin_cruce_count = sin_cruce.count()
                sin_cruce_rgu = sum(int(x or 0) for x in sin_cruce.values_list("rgu", flat=True))
                if sin_cruce_count:
                    self.stdout.write(self.style.WARNING(
                        f"    [SIN CRUCE ESACOM] {b}: {sin_cruce_count} filas · {sin_cruce_rgu} RGU. "
                        "Permanecen en el snapshot oficial, pero no se atribuyen a un Ejecutivo."
                    ))

                # El Portal aplica además la regla operacional ESACOM: solo ventas
                # instaladas. Esta capa puede diferir legítimamente del total Claro,
                # pero nunca debe incluir filas de otra carga KPI.
                portal_qs = filtrar_cortes_kpi_operativos(qs)
                portal = resumen_kpi(portal_qs)
                excluidos_no_instalados = qs.exclude(
                    venta__estado_instalacion=Venta.EstadoInstalacion.INSTALADO
                ).count()
                self.stdout.write(
                    f"    Portal operativo {b}: Total {portal['total']} RGU · KPI {portal['pct_cumplimiento']:.2f}% "
                    f"· excluidos ESACOM no instalados {excluidos_no_instalados}"
                )

            if errores_backend:
                raise CommandError(
                    "Corte vigente no reproduce la población cruzada del snapshot en: "
                    + ", ".join(sorted(set(errores_backend)))
                )
            self.stdout.write(self.style.SUCCESS(
                "[OK] Corte vigente = KPIRegistro cruzado del MISMO snapshot; sin contaminación de cargas anteriores."
            ))
            self.stdout.write(self.style.SUCCESS(
                "[OK] KPI oficial queda en KPIRegistro; Portal aplica atribución/instalación ESACOM sin inventar cruces."
            ))

            if not persistir:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING(
                    "[ROLLBACK] Prueba completada: no se guardó una carga KPI de laboratorio."
                ))
            else:
                self.stdout.write(self.style.SUCCESS(f"[PERSISTIDO] Carga KPI #{carga.id}."))
