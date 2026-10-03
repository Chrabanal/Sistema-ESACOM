import unicodedata

from django.core.management.base import BaseCommand, CommandError

from usuarios.models import Ejecutivo, EjecutivoManager
from ventas.models import VentaMovil
from ventas.controles_manual import CONTROL_2508_DETALLE
from ventas.produccion import (
    clasificar_movil_produccion,
    detalle_produccion_actual,
    resumen_produccion_actual,
)


# Controles manuales preservados como referencias de auditoría. No se usan
# para calcular producción: solo comparan la salida CRM contra una fotografía
# manual conocida.
CONTROL_2408 = {
    "nombre": "24-08-2026",
    "global": {
        "fija": {"completadas": 517, "pendiente_instalacion": 126, "total_control": 643},
        "movil": {"adicional": 36, "ppm": 2, "principal": 96, "total": 134},
        "total_produccion": 777,
    },
    "supervisores": {
        "CHARLY ESTAY": {"fija": {"completadas": 309, "pendiente_instalacion": 69, "total_control": 378}, "movil": {"total": 69}, "total_produccion": 447},
        "JORGE HERNANDEZ": {"fija": {"completadas": 114, "pendiente_instalacion": 29, "total_control": 143}, "movil": {"total": 36}, "total_produccion": 179},
        "PATRICIO GUERRA": {"fija": {"completadas": 61, "pendiente_instalacion": 25, "total_control": 86}, "movil": {"total": 23}, "total_produccion": 109},
        "VICENTE MORALES": {"fija": {"completadas": 33, "pendiente_instalacion": 3, "total_control": 36}, "movil": {"total": 6}, "total_produccion": 42},
    },
    "ejecutivos": {
        "19665650-2": {"nombre": "SERGIO AGUSTIN OSSES LABRA", "fija": {"completadas": 26, "pendiente_instalacion": 15, "total_control": 41}, "movil": {"total": 9}, "total_produccion": 50},
        "19776727-8": {"nombre": "CAMILO IGNACIO BASCUÑAN PEÑALOZA", "fija": {"completadas": 10, "pendiente_instalacion": 2, "total_control": 12}, "movil": {"total": 2}, "total_produccion": 14},
    },
}


CONTROL_2508 = {
    "nombre": "25-08-2026",
    "global": {
        "fija": {"completadas": 558, "pendiente_instalacion": 135, "total_control": 693},
        "movil": {"principal": 105, "adicional": 37, "ppm": 2, "total": 144},
        "total_produccion": 837,
    },
    "supervisores": {
        "CHARLY ESTAY": {"fija": {"completadas": 331, "pendiente_instalacion": 70, "total_control": 401}, "movil": {"total": 77}, "total_produccion": 478},
        "JORGE HERNANDEZ": {"fija": {"completadas": 123, "pendiente_instalacion": 40, "total_control": 163}, "movil": {"total": 38}, "total_produccion": 201},
        "PATRICIO GUERRA": {"fija": {"completadas": 71, "pendiente_instalacion": 23, "total_control": 94}, "movil": {"total": 23}, "total_produccion": 117},
        "VICENTE MORALES": {"fija": {"completadas": 33, "pendiente_instalacion": 2, "total_control": 35}, "movil": {"total": 6}, "total_produccion": 41},
    },
    "ejecutivos": {
        "19665650-2": {"nombre": "SERGIO AGUSTIN OSSES LABRA", "fija": {"completadas": 34, "pendiente_instalacion": 8, "total_control": 42}, "movil": {"total": 9}, "total_produccion": 51},
        "19776727-8": {"nombre": "CAMILO IGNACIO BASCUÑAN PEÑALOZA", "fija": {"completadas": 10, "pendiente_instalacion": 5, "total_control": 15}, "movil": {"total": 2}, "total_produccion": 17},
    },
    # Fotografía completa de las dos tablas entregadas por Gerencia el 25/08.
    # Se usa solo como control de aceptación, nunca para calcular producción.
    "detalle_ejecutivos": CONTROL_2508_DETALLE,
}


def _norm(texto):
    texto = str(texto or "").strip().upper()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return " ".join(texto.split())


def _vacio():
    return {
        "fija": {
            "completadas": 0, "pendiente_instalacion": 0, "pendiente_comercial": 0,
            "anuladas": 0, "derivado_redes": 0, "otros": 0, "total_control": 0,
            "rgu_total_base_vigente": 0, "total_base_vigente": 0,
            "ventas_completadas": 0, "ventas_pendiente_instalacion": 0,
            "ventas_pendiente_comercial": 0, "ventas_anuladas": 0,
            "ventas_derivado_redes": 0, "ventas_otros": 0,
            "total_control_ventas": 0, "ventas_sin_rgu": 0,
        },
        "movil": {
            "principal": 0, "adicional": 0, "ppm": 0, "otros": 0, "total": 0,
            "total_base_vigente": 0, "pendiente_activacion": 0,
            "pendiente_principal": 0, "pendiente_adicional": 0,
            "pendiente_ppm": 0, "pendiente_otros": 0,
            "pendiente_sin_evidencia": 0, "pendiente_estado_bloqueado": 0,
        },
        "total_produccion": 0,
    }


class Command(BaseCommand):
    help = (
        "Audita producción vigente ESACOM. Fija se mide en RGU y móvil en "
        "líneas efectivamente activadas/portadas. Claro no participa."
    )

    def add_arguments(self, parser):
        parser.add_argument("--rut", default="", help="Muestra únicamente un Ejecutivo por RUT.")
        grupo = parser.add_mutually_exclusive_group()
        grupo.add_argument("--control-2408", action="store_true", help="Compara contra control manual del 24-08-2026.")
        grupo.add_argument("--control-2508", action="store_true", help="Compara contra control manual actualizado del 25-08-2026.")
        parser.add_argument(
            "--solo-diferencias", action="store_true",
            help="Con un control manual, reduce la salida a diferencias relevantes.",
        )
        parser.add_argument(
            "--pendientes-movil", action="store_true",
            help="Lista líneas móviles vigentes excluidas de producción efectiva y su motivo.",
        )
        parser.add_argument(
            "--detalle-control", action="store_true",
            help=(
                "Con --control-2508 compara también cada Ejecutivo dentro del "
                "Supervisor, reproduciendo la jerarquía de la tabla dinámica manual."
            ),
        )

    def _linea(self, etiqueta, actual, esperado=None):
        if esperado is None:
            self.stdout.write(f"  {etiqueta:<31} {actual:>6}")
            return True
        dif = actual - esperado
        ok = dif == 0
        marca = "OK" if ok else "DIF"
        texto = f"  {etiqueta:<31} CRM {actual:>6} · Manual {esperado:>6} · Δ {dif:+d} [{marca}]"
        self.stdout.write(self.style.SUCCESS(texto) if ok else self.style.ERROR(texto))
        return ok

    @staticmethod
    def _esperado(dic, *ruta):
        actual = dic
        for clave in ruta:
            if not isinstance(actual, dict) or clave not in actual:
                return None
            actual = actual[clave]
        return actual

    def _imprimir_bloque(self, titulo, datos, esperado=None, solo_diferencias=False):
        # El control manual puede tener solo totales para ciertos niveles. No
        # inventamos desgloses que no fueron entregados.
        lineas = [
            ("Fija completadas (RGU)", datos["fija"]["completadas"], self._esperado(esperado, "fija", "completadas") if esperado else None),
            ("Fija pend. instalación (RGU)", datos["fija"]["pendiente_instalacion"], self._esperado(esperado, "fija", "pendiente_instalacion") if esperado else None),
            ("Total fija control (RGU)", datos["fija"]["total_control"], self._esperado(esperado, "fija", "total_control") if esperado else None),
            ("Móvil principal", datos["movil"]["principal"], self._esperado(esperado, "movil", "principal") if esperado else None),
            ("Móvil adicional", datos["movil"]["adicional"], self._esperado(esperado, "movil", "adicional") if esperado else None),
            ("Móvil PPM", datos["movil"]["ppm"], self._esperado(esperado, "movil", "ppm") if esperado else None),
            ("Total móvil efectivo", datos["movil"]["total"], self._esperado(esperado, "movil", "total") if esperado else None),
            ("TOTAL PRODUCCIÓN", datos["total_produccion"], self._esperado(esperado, "total_produccion") if esperado else None),
        ]
        comparables = [(a, e) for _, a, e in lineas if e is not None]
        if solo_diferencias and esperado and comparables and all(a == e for a, e in comparables):
            return True

        self.stdout.write(f"\n{titulo}")
        ok = True
        for etiqueta, actual, esp in lineas:
            if solo_diferencias and esp is not None and actual == esp:
                continue
            if solo_diferencias and esperado and esp is None:
                continue
            ok = self._linea(etiqueta, actual, esp) and ok

        self.stdout.write(
            "  Trazabilidad fija             "
            f"{datos['fija']['total_base_vigente']} ventas vigentes · "
            f"{datos['fija']['rgu_total_base_vigente']} RGU total · "
            f"{datos['fija']['total_control_ventas']} ventas en control"
        )
        if datos["fija"].get("ventas_sin_rgu"):
            self.stdout.write(self.style.WARNING(
                f"  [ALERTA] Ventas vigentes sin RGU: {datos['fija']['ventas_sin_rgu']}"
            ))

        if any(datos["fija"].get(k) for k in ("pendiente_comercial", "anuladas", "derivado_redes", "otros")):
            self.stdout.write(
                "  Fuera fija control (RGU)      "
                f"Pend.Com {datos['fija']['pendiente_comercial']} · "
                f"Anuladas {datos['fija']['anuladas']} · "
                f"Derivado {datos['fija']['derivado_redes']} · Otros {datos['fija']['otros']}"
            )

        self.stdout.write(
            "  Trazabilidad móvil            "
            f"{datos['movil']['total_base_vigente']} líneas vigentes · "
            f"{datos['movil']['total']} efectivas · "
            f"{datos['movil']['pendiente_activacion']} pendientes"
        )
        if datos["movil"].get("pendiente_activacion"):
            self.stdout.write(
                "  Pendientes móvil              "
                f"Princ {datos['movil']['pendiente_principal']} · "
                f"Adic {datos['movil']['pendiente_adicional']} · "
                f"PPM {datos['movil']['pendiente_ppm']} · "
                f"Otros {datos['movil']['pendiente_otros']}"
            )
        return ok

    def _comparar_detalle_control(self, detalle, esperado_detalle, *, solo_diferencias=False):
        """Compara Supervisor -> Ejecutivo contra la fotografía manual.

        La comparación se hace con los campos fuente de cada fila. Esto evita
        perder casos donde el mismo nombre aparece bajo más de un Supervisor
        dentro del corte (situación presente en el control del 25/08).
        """
        actual_por_sup = detalle.get("ejecutivos_por_supervisor", {})
        actual_sup_norm = {_norm(k): (k, v) for k, v in actual_por_sup.items()}
        ok = True
        comparados = 0
        self.stdout.write("\nDETALLE CONTROL GERENCIA · SUPERVISOR -> EJECUTIVO")

        for sup_esperado, ejecutivos_esperados in esperado_detalle.items():
            sup_real = actual_sup_norm.get(_norm(sup_esperado))
            actuales = sup_real[1] if sup_real else {}
            actuales_norm = {_norm(k): (k, v) for k, v in actuales.items()}
            esperados_norm = {_norm(k) for k in ejecutivos_esperados}

            for nombre_esperado, esperado in ejecutivos_esperados.items():
                real = actuales_norm.get(_norm(nombre_esperado))
                datos = real[1] if real else _vacio()
                nombre_real = real[0] if real else nombre_esperado
                campos = [
                    ("comp", datos["fija"]["completadas"], esperado["fija"]["completadas"]),
                    ("pend", datos["fija"]["pendiente_instalacion"], esperado["fija"]["pendiente_instalacion"]),
                    ("princ", datos["movil"]["principal"], esperado["movil"]["principal"]),
                    ("adic", datos["movil"]["adicional"], esperado["movil"]["adicional"]),
                    ("ppm", datos["movil"]["ppm"], esperado["movil"]["ppm"]),
                ]
                fila_ok = all(actual == esperado_val for _, actual, esperado_val in campos)
                comparados += 1
                ok = fila_ok and ok
                if solo_diferencias and fila_ok:
                    continue
                marca = "OK" if fila_ok else "DIF"
                texto = (
                    f"  {sup_real[0] if sup_real else sup_esperado} · {nombre_real}: "
                    f"fija {datos['fija']['completadas']}/{datos['fija']['pendiente_instalacion']} "
                    f"vs {esperado['fija']['completadas']}/{esperado['fija']['pendiente_instalacion']} · "
                    f"móvil A{datos['movil']['adicional']} PPM{datos['movil']['ppm']} "
                    f"Pr{datos['movil']['principal']} vs "
                    f"A{esperado['movil']['adicional']} PPM{esperado['movil']['ppm']} "
                    f"Pr{esperado['movil']['principal']} [{marca}]"
                )
                self.stdout.write(self.style.SUCCESS(texto) if fila_ok else self.style.ERROR(texto))

            # Si el CRM tiene producción efectiva para un Ejecutivo que no aparece
            # en la fotografía manual del Supervisor, también debe investigarse.
            for nombre_real, datos in actuales.items():
                if _norm(nombre_real) in esperados_norm:
                    continue
                if datos["fija"]["total_control"] == 0 and datos["movil"]["total"] == 0:
                    continue
                ok = False
                texto = (
                    f"  {sup_real[0] if sup_real else sup_esperado} · {nombre_real}: "
                    f"EXTRA CRM · fija {datos['fija']['total_control']} RGU · "
                    f"móvil {datos['movil']['total']} líneas [DIF]"
                )
                self.stdout.write(self.style.ERROR(texto))

        # Supervisores con producción que no existen en la fotografía manual.
        esperados_sup_norm = {_norm(k) for k in esperado_detalle}
        for sup_real, ejecutivos in actual_por_sup.items():
            if _norm(sup_real) in esperados_sup_norm:
                continue
            total = sum(
                d["fija"]["total_control"] + d["movil"]["total"]
                for d in ejecutivos.values()
            )
            if total:
                ok = False
                self.stdout.write(self.style.ERROR(
                    f"  SUPERVISOR EXTRA · {sup_real} · producción {total} [DIF]"
                ))

        if ok:
            self.stdout.write(self.style.SUCCESS(
                f"  [OK] {comparados} filas de Ejecutivo coinciden con las tablas manuales del 25/08."
            ))
        return ok

    def _listar_pendientes_movil(self, *, ejecutivo=None):
        qs = VentaMovil.objects.filter(en_base_vigente=True).select_related("ejecutivo")
        if ejecutivo is not None:
            qs = qs.filter(ejecutivo=ejecutivo)
        pendientes = []
        for venta in qs.iterator():
            efectiva, motivo = clasificar_movil_produccion(venta)
            if not efectiva:
                pendientes.append((venta, motivo))

        self.stdout.write(f"\nLÍNEAS MÓVILES PENDIENTES · {len(pendientes)}")
        if not pendientes:
            self.stdout.write("  Sin líneas excluidas de producción efectiva.")
            return
        for venta, motivo in pendientes:
            self.stdout.write(
                f"  {venta.nombre_evt or 'SIN EJECUTIVO'} · {venta.tipo_linea} · "
                f"PCS {venta.pcs or '-'} · estado {venta.estado or '-'} · "
                f"activación {venta.fecha_activacion or '-'} · {motivo}"
            )

    def handle(self, *args, **options):
        rut = EjecutivoManager.normalize_rut(options.get("rut") or "")
        control = CONTROL_2408 if options.get("control_2408") else CONTROL_2508 if options.get("control_2508") else None
        solo_dif = bool(options.get("solo_diferencias"))

        self.stdout.write(self.style.SUCCESS("ESACOM · AUDITORÍA PRODUCCIÓN OPERACIONAL"))
        self.stdout.write("Fuente fija: hoja vigente 'Base de Ventas' · unidad = RGU")
        self.stdout.write("Fuente móvil: hoja vigente 'Ventas Móvil' · unidad = línea efectiva")
        self.stdout.write("KPI Claro: NO participa en este cálculo")
        if control:
            self.stdout.write(f"Control manual de comparación: {control['nombre']} · snapshot histórico")
            if options.get("control_2508"):
                self.stdout.write(
                    "Nota: 837 corresponde al control manual recibido durante la mañana; "
                    "la matriz viva puede evolucionar durante el día."
                )

        if rut:
            ejecutivo = Ejecutivo.objects.filter(rut=rut).first()
            if not ejecutivo:
                raise CommandError(f"No existe Ejecutivo con RUT {rut}")
            datos = resumen_produccion_actual(ejecutivo=ejecutivo)
            esperado = control["ejecutivos"].get(rut) if control else None
            self._imprimir_bloque(
                f"EJECUTIVO · {ejecutivo.nombre} · {ejecutivo.rut}",
                datos,
                esperado,
                solo_dif,
            )
            if options.get("pendientes_movil"):
                self._listar_pendientes_movil(ejecutivo=ejecutivo)
            if not datos["disponible"]:
                self.stdout.write(self.style.WARNING(
                    "[ALERTA] No hay filas marcadas como base vigente para este Ejecutivo. "
                    "Ejecuta primero la sincronización ESACOM con esta versión."
                ))
            return

        detalle = detalle_produccion_actual()
        global_esperado = control["global"] if control else None
        ok = self._imprimir_bloque("TOTAL ESACOM", detalle["global"], global_esperado, solo_dif)

        por_sup_norm = {_norm(k): (k, v) for k, v in detalle["supervisores"].items()}
        nombres = sorted(detalle["supervisores"].keys())
        if control:
            vistos = set()
            for nombre_control, esperado in control["supervisores"].items():
                real = por_sup_norm.get(_norm(nombre_control))
                datos = real[1] if real else _vacio()
                titulo = f"SUPERVISOR · {real[0] if real else nombre_control}"
                ok = self._imprimir_bloque(titulo, datos, esperado, solo_dif) and ok
                vistos.add(_norm(nombre_control))
            for nombre in nombres:
                if _norm(nombre) not in vistos:
                    self._imprimir_bloque(f"SUPERVISOR EXTRA · {nombre}", detalle["supervisores"][nombre], None, solo_dif)
        else:
            for nombre in nombres:
                self._imprimir_bloque(f"SUPERVISOR · {nombre}", detalle["supervisores"][nombre])

        if control and options.get("detalle_control") and control.get("detalle_ejecutivos"):
            ok = self._comparar_detalle_control(
                detalle, control["detalle_ejecutivos"], solo_diferencias=solo_dif
            ) and ok

        if not solo_dif:
            self.stdout.write("\nDETALLE POR EJECUTIVO")
            for nombre in sorted(detalle["ejecutivos"].keys(), key=_norm):
                d = detalle["ejecutivos"][nombre]
                self.stdout.write(
                    f"  {nombre}: fija {d['fija']['total_control']} RGU "
                    f"({d['fija']['completadas']} comp + {d['fija']['pendiente_instalacion']} pend) · "
                    f"móvil {d['movil']['total']} efectiva "
                    f"({d['movil']['principal']} princ + {d['movil']['adicional']} adic + {d['movil']['ppm']} ppm) · "
                    f"pend. móvil {d['movil']['pendiente_activacion']} · total {d['total_produccion']}"
                )

        if options.get("pendientes_movil"):
            self._listar_pendientes_movil()

        if control:
            if ok:
                self.stdout.write(self.style.SUCCESS(
                    f"\n[OK] Producción CRM coincide con el control manual del {control['nombre']} en todos los campos disponibles."
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    "\n[EVOLUCIÓN VS SNAPSHOT] El CRM difiere del control manual histórico. "
                    "Primero valida FUENTE = CRM; no fuerces la matriz viva a cifras antiguas."
                ))
        if detalle["global"]["fija"]["total_base_vigente"] == 0 and detalle["global"]["movil"]["total_base_vigente"] == 0:
            self.stdout.write(self.style.WARNING(
                "[ALERTA] La BD aún no tiene marcas de base vigente. Ejecuta: "
                "python manage.py verificar_sync_esacom --sincronizar"
            ))
