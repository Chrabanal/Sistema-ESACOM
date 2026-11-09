"""
Importador del Excel matriz (Ingreso_de_Ventas.xlsx y similares).

Uso:
    python manage.py importar_excel /ruta/al/archivo.xlsx
    python manage.py importar_excel /ruta/al/archivo.xlsx --solo dotacion,comunas
    python manage.py importar_excel /ruta/al/archivo.xlsx --dry-run

Notas sobre el archivo real (41 pestañas, ver análisis previo):
- 'Dotación' y 'Base de Ventas' son tablas normales con fila de encabezado.
- 'Comunas' es una tabla horizontal para listas desplegables de Excel:
  columna A = región, columnas B en adelante = comunas de esa región,
  repetida cientos de veces (una fila por cada celda del rango de
  validación). Hay que deduplicar por región.
- 'Apoyo' son varias mini-tablas independientes una al lado de la otra
  (SUPERVISOR, PROMOCIÓN, ESTADO INST, regiones, motivos...). Solo nos
  interesan las columnas C:I (catálogo de promociones).
- 'Base Claro' es el export crudo de Claro: 128 columnas de datos +
  3 columnas locales de cruce al final (Cruce, RGU, Código) que NO se
  importan porque se recalculan en el sistema.
- Los encabezados del archivo real tienen espacios de más
  ('RUT CLIENTE ', 'FECHA VENTA ') — por eso todo el matching de
  columnas se hace por nombre normalizado (strip + upper), nunca por
  posición fija ni por el string exacto.
"""
from __future__ import annotations

import datetime
import hashlib
import unicodedata
from decimal import Decimal, InvalidOperation

import openpyxl
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalogos.models import Comuna, Promocion
from integraciones.models import CargaExcel, ClaroImport
from usuarios.models import Ejecutivo, EjecutivoManager
from ventas.models import Corte, Venta, VentaFijaFuente, VentaMovil


def normalizar(texto) -> str:
    """
    Nombre de columna a una forma comparable: sin tildes, sin guiones
    bajos, sin espacios de más. El archivo real mezcla convenciones
    ('RUT CLIENTE ', 'NUM_PEDIDO', 'Fecha_Creacion', 'PROMOCIÓN') así
    que el matching nunca debe depender del string exacto.
    """
    texto = str(texto) if texto is not None else ""
    texto = texto.strip().upper().replace("_", " ").replace("°", "")
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return " ".join(texto.split())


def mapa_encabezados(ws) -> dict[str, int]:
    """{nombre_normalizado: número_de_columna(1-indexed)} de la fila 1."""
    mapa = {}
    for cell in ws[1]:
        if cell.value:
            mapa[normalizar(cell.value)] = cell.column
    return mapa


def valor(row_cells, mapa, nombre) -> object:
    col = mapa.get(normalizar(nombre))
    if col is None:
        return None
    return row_cells[col - 1].value


def a_decimal(v):
    if v in (None, "", "N/A", "No cruza"):
        return None
    try:
        return Decimal(str(v))
    except InvalidOperation:
        return None


def a_fecha(v):
    if isinstance(v, datetime.datetime):
        return v.date()
    if isinstance(v, datetime.date):
        return v
    return None


def a_bool_estado(v) -> bool:
    return normalizar(v) not in ("", "NO CRUZA", "NONE", "N/A")


def _limpiar_telefono(v) -> str:
    """El Excel trae el teléfono como float (929694256.0) -> '929694256'."""
    if v is None:
        return ""
    if isinstance(v, float):
        return str(int(v))
    return str(v).strip()


def _normalizar_rut_valor(v) -> str:
    if v in (None, ""):
        return ""
    texto = str(v).strip()
    if texto.endswith(".0") and texto[:-2].isdigit():
        texto = texto[:-2]
    return EjecutivoManager.normalize_rut(texto)


def _a_entero_positivo(v):
    if v in (None, ""):
        return None
    try:
        n = int(float(v))
        return n if n >= 0 else None
    except (TypeError, ValueError):
        return None


def _limpiar_pcs(v) -> str:
    """Normaliza el número/PCS sin convertirlo a notación científica."""
    if v in (None, ""):
        return ""
    if isinstance(v, float):
        return str(int(v))
    texto = str(v).strip()
    if texto.endswith(".0") and texto[:-2].isdigit():
        texto = texto[:-2]
    try:
        # XLSX puede entregar un número como texto científico.
        if "E" in texto.upper():
            return str(int(float(texto)))
    except (TypeError, ValueError, OverflowError):
        pass
    return texto


def _tipo_linea_movil(v) -> str:
    txt = normalizar(v)
    if "PRINCIPAL" in txt:
        return VentaMovil.TipoLinea.PRINCIPAL
    if "ADICIONAL" in txt:
        return VentaMovil.TipoLinea.ADICIONAL
    if txt == "PPM" or "PPM" in txt:
        return VentaMovil.TipoLinea.PPM
    return VentaMovil.TipoLinea.OTRO


class Command(BaseCommand):
    help = "Importa el Excel matriz (Dotación, Honorarios, Comunas, Apoyo, Base Claro, Base de Ventas)."

    def add_arguments(self, parser):
        parser.add_argument("archivo", type=str, help="Ruta al .xlsx")
        parser.add_argument(
            "--solo", type=str, default="",
            help="Lista separada por comas: dotacion,honorarios,comunas,apoyo,claro,ventas,movil. Vacío = todo.",
        )
        parser.add_argument("--dry-run", action="store_true", help="No guarda nada, solo reporta.")
        parser.add_argument("--usuario-rut", type=str, default="", help="RUT de quien ejecuta la carga (para CargaExcel).")

    def handle(self, *args, **options):
        path = options["archivo"]
        dry_run = options["dry_run"]
        pasos = [s.strip() for s in options["solo"].split(",") if s.strip()] or [
            "dotacion", "comunas", "apoyo", "honorarios", "claro", "ventas", "movil",
        ]

        try:
            wb = openpyxl.load_workbook(path, data_only=True)
        except FileNotFoundError:
            raise CommandError(f"No existe el archivo: {path}")

        creado_por = None
        if options["usuario_rut"]:
            creado_por = Ejecutivo.objects.filter(rut=options["usuario_rut"]).first()

        resumen = {}
        with transaction.atomic():
            if "dotacion" in pasos:
                resumen["dotacion"] = self._importar_dotacion(wb)
            if "comunas" in pasos:
                resumen["comunas"] = self._importar_comunas(wb)
            if "apoyo" in pasos:
                resumen["promociones"] = self._importar_apoyo(wb)
            if "honorarios" in pasos:
                resumen["honorarios"] = self._importar_honorarios(wb)
            if "claro" in pasos:
                resumen["base_claro"] = self._importar_base_claro(wb, creado_por)
            if "ventas" in pasos:
                resumen["base_ventas"] = self._importar_base_ventas(wb)
            if "movil" in pasos:
                resumen["ventas_movil"] = self._importar_base_movil(wb)

            if dry_run:
                self.stdout.write(self.style.WARNING("DRY-RUN: se revierte la transacción, no se guardó nada."))
                transaction.set_rollback(True)

        wb.close()

        self.stdout.write(self.style.SUCCESS("Resumen de importación:"))
        for hoja, r in resumen.items():
            self.stdout.write(f"  {hoja}: {r}")
        # OJO: no usar `return resumen` acá -- BaseCommand.execute() hace
        # self.stdout.write(output) con lo que retorne handle(), y eso
        # revienta si output es un dict (rompe el uso normal por consola
        # y call_command). Se guarda en self.resumen para que quien llame
        # a Command().handle(...) directamente (ver integraciones/views.py)
        # pueda leerlo sin pasar por execute().
        self.resumen = resumen

    # ------------------------------------------------------------------
    # Dotación -> Ejecutivo
    # ------------------------------------------------------------------
    def _importar_dotacion(self, wb):
        """Sincroniza Dotación sin confundir cargo laboral con rol CRM.

        Reglas UAT 2026-08-23:
        - RUT es la identidad.
        - ``cargo`` es rol de acceso CRM y NO se sobreescribe desde la columna Cargo.
        - ``ESTADO DE CONTRATO`` define vigencia.
        - Supervisor se resuelve por catálogo explícito alias -> RUT; nunca por substring.
        - Si un alias no está resuelto, la relación se limpia para no conservar asignaciones obsoletas.
        """
        from django.utils import timezone
        from usuarios.models import AuditoriaUsuario

        if "Dotación" not in wb.sheetnames:
            self.stdout.write(self.style.WARNING("Hoja 'Dotación' no encontrada, se omite."))
            return {"omitido": True}

        ws = wb["Dotación"]
        mapa = mapa_encabezados(ws)
        creados, actualizados = 0, 0
        pendientes_supervisor = []
        ruts_en_archivo = set()

        # Catálogo controlado confirmado con la base ESACOM auditada.
        # Importante: Cargo fuente NO determina rol CRM.
        from usuarios.dotacion import SUPERVISOR_ALIAS_A_RUT, SUPERVISOR_RUTS_CONFIRMADOS
        supervisor_por_alias = SUPERVISOR_ALIAS_A_RUT
        ruts_supervisores = SUPERVISOR_RUTS_CONFIRMADOS
        estado_activo = {"CONTRATADO", "CONTRATADO S", "HONORARIO", "ACTIVO", "LICENCIA"}
        estado_inactivo = {"FINIQUITADO", "INACTIVO"}
        ahora = timezone.now()

        for row in ws.iter_rows(min_row=2):
            rut = valor(row, mapa, "RUT")
            if not rut:
                continue
            rut_normalizado = EjecutivoManager.normalize_rut(str(rut))
            ruts_en_archivo.add(rut_normalizado)
            nombre = str(valor(row, mapa, "Nombre") or "").strip()
            cargo_fuente = str(valor(row, mapa, "Cargo") or "").strip()
            supervisor_fuente = str(valor(row, mapa, "SUPERVISOR") or "").strip()
            estado_fuente = str(valor(row, mapa, "Estado de Contrato") or valor(row, mapa, "Estado") or "").strip()
            estado_norm = normalizar(estado_fuente)
            tipo_contrato = str(valor(row, mapa, "Tipo Contrato") or "").strip()
            tipo_kpi = Ejecutivo.TipoKPI.HONORARIOS if ("HONORARIO" in normalizar(tipo_contrato) or estado_norm == "HONORARIO") else Ejecutivo.TipoKPI.REGULAR

            existente = Ejecutivo.objects.filter(rut=rut_normalizado).first()
            if estado_norm in estado_inactivo:
                estado_crm, activo = Ejecutivo.EstadoContrato.INACTIVO, False
            elif estado_norm == "LICENCIA":
                estado_crm, activo = Ejecutivo.EstadoContrato.LICENCIA, True
            else:
                estado_crm, activo = Ejecutivo.EstadoContrato.ACTIVO, True

            defaults = {
                "nombre": nombre,
                "equipo": str(valor(row, mapa, "Equipo") or ""),
                "tipo_contrato": tipo_contrato,
                "tipo_kpi": tipo_kpi,
                "fecha_ingreso": a_fecha(valor(row, mapa, "Fecha de Ingreso")),
                "codigo_movil": str(valor(row, mapa, "CODIGO MOVIL") or ""),
                "codigo_fijo": str(valor(row, mapa, "CODIGO FIJO") or ""),
                "codigo_andes": str(valor(row, mapa, "CODIGO ANDES") or ""),
                "telefono": str(valor(row, mapa, "FONO EJECUTIVOS") or ""),
                "cargo_fuente_esacom": cargo_fuente,
                "supervisor_fuente": supervisor_fuente,
                "estado_contrato_fuente": estado_fuente,
                "ultima_sync_dotacion": ahora,
            }

            # Estado contractual sí viene de ESACOM. Protegemos cuentas técnicas
            # que no forman parte de la dotación comercial.
            rol_protegido = existente and (existente.cargo in {Ejecutivo.Cargo.SOPORTE, Ejecutivo.Cargo.GERENCIA, Ejecutivo.Cargo.OPERACIONES, Ejecutivo.Cargo.CONTABILIDAD} or existente.is_superuser)
            if not rol_protegido:
                defaults.update(estado_contrato=estado_crm, is_active=activo)

            # El rol CRM se reconcilia de forma determinista para la dotación
            # comercial: sólo los RUT confirmados son SUPERVISOR. Todo otro
            # integrante de dotación es EJECUTIVO aunque Cargo fuente diga
            # "Supervisor". Las cuentas administrativas/técnicas se preservan.
            if not rol_protegido:
                defaults["cargo"] = (
                    Ejecutivo.Cargo.SUPERVISOR
                    if rut_normalizado in ruts_supervisores
                    else Ejecutivo.Cargo.EJECUTIVO
                )

            ejecutivo, creado = Ejecutivo.objects.update_or_create(rut=rut_normalizado, defaults=defaults)
            if not ejecutivo.has_usable_password():
                ejecutivo.set_unusable_password()
                ejecutivo.save(update_fields=["password"])
            creados += int(creado)
            actualizados += int(not creado)
            pendientes_supervisor.append((ejecutivo, normalizar(supervisor_fuente)))

        # Reconciliación completa de asignaciones. Cero substring matching.
        sin_match = 0
        cambios_supervisor = 0
        for ejecutivo, alias in pendientes_supervisor:
            anterior_id = ejecutivo.supervisor_id
            nuevo = None
            if ejecutivo.cargo != Ejecutivo.Cargo.SUPERVISOR and alias:
                rut_sup = supervisor_por_alias.get(alias)
                if rut_sup:
                    nuevo = Ejecutivo.objects.filter(rut=EjecutivoManager.normalize_rut(rut_sup), cargo=Ejecutivo.Cargo.SUPERVISOR).first()
                if not nuevo:
                    sin_match += 1
            if anterior_id != (nuevo.id if nuevo else None):
                anterior = Ejecutivo.objects.filter(pk=anterior_id).first() if anterior_id else None
                ejecutivo.supervisor = nuevo
                ejecutivo.save(update_fields=["supervisor", "actualizado_en"])
                cambios_supervisor += 1
                AuditoriaUsuario.objects.create(
                    actor=None, usuario_objetivo=ejecutivo,
                    accion=AuditoriaUsuario.Accion.ASIGNACION_SUPERVISOR,
                    detalle={
                        "origen": "Dotación ESACOM",
                        "supervisor_fuente": ejecutivo.supervisor_fuente,
                        "antes": {"id": anterior_id, "rut": getattr(anterior, "rut", None), "nombre": getattr(anterior, "nombre", None)},
                        "despues": {"id": getattr(nuevo, "id", None), "rut": getattr(nuevo, "rut", None), "nombre": getattr(nuevo, "nombre", None)},
                    },
                )

        activos_no_en_archivo = list(Ejecutivo.objects.filter(is_active=True).exclude(rut__in=ruts_en_archivo).values_list("rut", "nombre"))
        alias_no_resueltos = sorted({alias for _, alias in pendientes_supervisor if alias and alias not in supervisor_por_alias})
        return {
            "creados": creados, "actualizados": actualizados,
            "supervisor_sin_match": sin_match, "cambios_supervisor": cambios_supervisor,
            "alias_supervisor_no_resueltos": alias_no_resueltos,
            "activos_no_en_archivo": [f"{rut} {nombre}" for rut, nombre in activos_no_en_archivo],
        }

    # ------------------------------------------------------------------
    # Honorarios -> Venta ESACOM + identificación de ejecutivo
    # ------------------------------------------------------------------
    def _importar_honorarios(self, wb):
        """Importa la hoja Honorarios usando RUT EVT y nombre como fallback.

        El código Andes/CE nunca define de quién es la venta. La fórmula de
        KPI Honorarios se mantiene separada del KPI regular de Claro.
        """
        if "Honorarios" not in wb.sheetnames:
            self.stdout.write(self.style.WARNING("Hoja 'Honorarios' no encontrada, se omite."))
            return {"omitido": True}

        ws = wb["Honorarios"]
        mapa = mapa_encabezados(ws)
        ejecutivos_por_rut = {EjecutivoManager.normalize_rut(e.rut): e for e in Ejecutivo.objects.all()}
        por_nombre = {}
        for e in Ejecutivo.objects.all():
            clave = normalizar(e.nombre)
            if clave:
                por_nombre.setdefault(clave, []).append(e)

        promos_por_nombre = {p.nombre: p for p in Promocion.objects.all()}
        creadas = actualizadas = resueltos_rut = resueltos_nombre = creados_honorarios = sin_ejecutivo = sin_promocion = 0

        for row in ws.iter_rows(min_row=2):
            n_pedido = valor(row, mapa, "N° PEDIDO")
            if not n_pedido:
                continue

            rut_evt = _normalizar_rut_valor(valor(row, mapa, "RUT EVT"))
            nombre_evt = str(valor(row, mapa, "NOMBRE EVT") or "").strip()
            ejecutivo = ejecutivos_por_rut.get(rut_evt) if rut_evt else None
            if ejecutivo:
                resueltos_rut += 1
            elif rut_evt:
                # Honorarios puede no existir en Dotación. Si ESACOM trae RUT
                # EVT, podemos crear el registro de identidad de forma segura;
                # queda sin acceso hasta que Soporte lo active/asigne clave.
                ejecutivo = Ejecutivo.objects.create(
                    rut=rut_evt,
                    nombre=nombre_evt or "Vendedor Honorarios",
                    cargo=Ejecutivo.Cargo.EJECUTIVO,
                    tipo_kpi=Ejecutivo.TipoKPI.HONORARIOS,
                    tipo_contrato="Honorarios",
                    estado_contrato=Ejecutivo.EstadoContrato.INACTIVO,
                    is_active=False,
                )
                ejecutivo.set_unusable_password()
                ejecutivo.save(update_fields=["password"])
                ejecutivos_por_rut[rut_evt] = ejecutivo
                por_nombre.setdefault(normalizar(ejecutivo.nombre), []).append(ejecutivo)
                creados_honorarios += 1
                resueltos_rut += 1
            elif nombre_evt:
                candidatos = por_nombre.get(normalizar(nombre_evt), [])
                if len(candidatos) == 1:
                    ejecutivo = candidatos[0]
                    resueltos_nombre += 1

            if ejecutivo:
                # La Dotación ESACOM vigente manda sobre REGULAR/HONORARIOS.
                # La hoja Honorarios puede contener ventas históricas de personas
                # que hoy tienen contrato regular; no debe reclasificarlas.
                # Solo identidades que NO provienen de Dotación se marcan como
                # Honorarios por esta hoja.
                if ejecutivo.ultima_sync_dotacion is None:
                    cambios = []
                    if ejecutivo.tipo_kpi != Ejecutivo.TipoKPI.HONORARIOS:
                        ejecutivo.tipo_kpi = Ejecutivo.TipoKPI.HONORARIOS
                        cambios.append("tipo_kpi")
                    if not ejecutivo.tipo_contrato:
                        ejecutivo.tipo_contrato = "Honorarios"
                        cambios.append("tipo_contrato")
                    if cambios:
                        cambios.append("actualizado_en")
                        ejecutivo.save(update_fields=cambios)
            else:
                sin_ejecutivo += 1

            promo_nombre = str(valor(row, mapa, "PROMOCION") or "").strip()
            promocion = promos_por_nombre.get(promo_nombre)
            if not promocion:
                sin_promocion += 1
                continue

            fecha_venta = a_fecha(valor(row, mapa, "FECHA VENTA")) or datetime.date.today()
            camada = f"{fecha_venta.year:04d}-{fecha_venta.month:02d}"
            _, creado = Venta.objects.update_or_create(
                n_pedido=str(n_pedido),
                defaults=dict(
                    rut_cliente=_normalizar_rut_valor(valor(row, mapa, "RUT CLIENTE")),
                    nombre_cliente=str(valor(row, mapa, "NOMBRE CLIENTE") or "").strip(),
                    telefono_cliente=_limpiar_telefono(valor(row, mapa, "NUMERO CLIENTE")),
                    rut_evt=rut_evt,
                    nombre_evt=nombre_evt,
                    origen_venta=Venta.OrigenVenta.HONORARIOS,
                    fecha_pago_honorarios=a_fecha(valor(row, mapa, "FECHA DE PAGO")),
                    rut_ce=_normalizar_rut_valor(valor(row, mapa, "RUT CE")),
                    codigo_ce=str(valor(row, mapa, "CODIGO CE") or "").strip(),
                    rgu_base=_a_entero_positivo(valor(row, mapa, "RGU")),
                    ejecutivo=ejecutivo,
                    ejecutivo_ce=None,
                    promocion=promocion,
                    comuna=None,
                    tipo_cliente="B2C",
                    estado_instalacion=self._mapear_estado_instalacion(valor(row, mapa, "ESTADO DE INSTALACION")),
                    motivo_pendiente="",
                    fecha_venta=fecha_venta,
                    primera_agenda=a_fecha(valor(row, mapa, "1a Agenda")),
                    segunda_agenda=None,
                    fecha_cierre=a_fecha(valor(row, mapa, "FECHA CIERRE")),
                    precio_venta=None,
                    honorarios=None,
                    ingresador="",
                    camada=camada,
                ),
            )
            creadas += int(creado)
            actualizadas += int(not creado)

        return {
            "ventas_creadas": creadas,
            "ventas_actualizadas": actualizadas,
            "resueltos_por_rut": resueltos_rut,
            "resueltos_por_nombre": resueltos_nombre,
            "usuarios_honorarios_creados": creados_honorarios,
            "sin_ejecutivo": sin_ejecutivo,
            "sin_promocion_valida": sin_promocion,
        }

    # ------------------------------------------------------------------
    # Comunas -> Comuna (tabla horizontal de dropdown, hay que deduplicar)
    # ------------------------------------------------------------------
    def _importar_comunas(self, wb):
        if "Comunas" not in wb.sheetnames:
            self.stdout.write(self.style.WARNING("Hoja 'Comunas' no encontrada, se omite."))
            return {"omitido": True}

        ws = wb["Comunas"]
        vistas = set()
        creadas = 0
        for row in ws.iter_rows(min_row=2, values_only=True):
            region = row[0]
            if not region or region in vistas:
                continue
            vistas.add(region)
            for comuna in row[1:]:
                if not comuna:
                    continue
                _, creado = Comuna.objects.update_or_create(
                    nombre=str(comuna).strip(), defaults={"region": str(region).strip()}
                )
                creadas += int(creado)
        return {"regiones": len(vistas), "comunas_creadas": creadas}

    # ------------------------------------------------------------------
    # Apoyo (columnas C:I) -> Promocion
    # ------------------------------------------------------------------
    def _importar_apoyo(self, wb):
        if "Apoyo" not in wb.sheetnames:
            self.stdout.write(self.style.WARNING("Hoja 'Apoyo' no encontrada, se omite."))
            return {"omitido": True}

        ws = wb["Apoyo"]
        creadas, actualizadas = 0, 0
        vistas = set()
        # Columnas fijas por posición: C=PROMOCIÓN, D=RGU, E=Internet, F=TV, G=Fono, H=Empresa, I=Canal
        for row in ws.iter_rows(min_row=2, values_only=True):
            nombre = row[2]
            if not nombre or nombre in vistas:
                continue
            vistas.add(nombre)
            _, creado = Promocion.objects.update_or_create(
                nombre=str(nombre).strip(),
                defaults=dict(
                    rgu=int(row[3] or 1),
                    tiene_internet=bool(row[4]),
                    tiene_tv=bool(row[5]),
                    tiene_fono=bool(row[6]),
                    empresa=str(row[7] or "CLARO").strip().upper()[:10],
                    canal=str(row[8] or ""),
                ),
            )
            creadas += int(creado)
            actualizadas += int(not creado)
        return {"creadas": creadas, "actualizadas": actualizadas}

    # ------------------------------------------------------------------
    # Base Claro -> ClaroImport (raw + campos promovidos)
    # ------------------------------------------------------------------
    def _importar_base_claro(self, wb, creado_por):
        nombre_hoja = "Base Claro" if "Base Claro" in wb.sheetnames else None
        if not nombre_hoja:
            self.stdout.write(self.style.WARNING("Hoja 'Base Claro' no encontrada, se omite."))
            return {"omitido": True}

        ws = wb[nombre_hoja]
        headers_originales = [c.value for c in ws[1]]
        # las últimas columnas (Cruce/RGU/Código/Horizontales) son fórmulas
        # locales agregadas para el cruce, no vienen del export de Claro.
        columnas_locales = {"CRUCE", "RGU", "CODIGO", "HORIZONTALES"}
        # ...pero 'RGU' también podría ser un campo real más arriba en el
        # export; por eso cortamos por POSICIÓN (las últimas 4 columnas),
        # no por nombre, y buscamos los campos promovidos solo en el resto.
        idx_fin_export = len(headers_originales)
        while idx_fin_export > 0 and normalizar(headers_originales[idx_fin_export - 1]) in columnas_locales:
            idx_fin_export -= 1

        norm_idx = {
            normalizar(h): i for i, h in enumerate(headers_originales[:idx_fin_export]) if h
        }

        def campo(row, *nombres_posibles):
            for n in nombres_posibles:
                i = norm_idx.get(normalizar(n))
                if i is not None:
                    return row[i]
            return None

        carga = CargaExcel.objects.create(
            origen=CargaExcel.Origen.MANUAL,
            tipo_base=CargaExcel.TipoBase.REPORTE_CLARO,
            archivo_nombre=nombre_hoja,
            creado_por=creado_por,
        )

        total, con_pedido = 0, 0
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0] is None and row[3] is None:
                continue
            total += 1
            num_pedido = campo(row, "NUM_PEDIDO", "N PEDIDO", "PEDIDO")
            raw = {
                headers_originales[i]: row[i]
                for i in range(min(len(headers_originales), len(row)))
                if headers_originales[i]
            }

            ClaroImport.objects.create(
                num_pedido=str(num_pedido) if num_pedido else "",
                rgu=campo(row, "RGU") if isinstance(campo(row, "RGU"), (int, float)) else None,
                codigo_claro=str(campo(row, "CODIGO") or ""),
                ingresador=str(campo(row, "INGRESADOR") or ""),
                estado_pedido=str(campo(row, "ESTADO PEDIDO", "ESTADO") or ""),
                fecha_creacion=a_fecha(campo(row, "FECHA CREACION", "FECHA_CREACION")),
                raw_data={
                    k: (v.isoformat() if isinstance(v, (datetime.date, datetime.datetime)) else v)
                    for k, v in raw.items()
                },
                cruce_ok=bool(num_pedido),
                carga=carga,
            )
            con_pedido += int(bool(num_pedido))

        carga.filas_totales = total
        carga.filas_sin_cruce = total - con_pedido
        carga.save(update_fields=["filas_totales", "filas_sin_cruce"])
        return {"filas_importadas": total, "con_num_pedido": con_pedido}

    # ------------------------------------------------------------------
    # Base de Ventas -> Venta + Corte (B1, a partir de Vencimiento 1ra Boleta)
    # ------------------------------------------------------------------
    def _importar_base_ventas(self, wb):
        """
        Importa la base fija vigente + respaldos históricos BVYYYYMM / BDVentasMMYYYY.

        El KPI de Claro es acumulativo y puede traer camadas anteriores. Si
        solo cargáramos la hoja "Base de Ventas" actual, pedidos archivados
        en BV 202601...BV202606 o "BDVentas 072026" quedarían falsamente sin cruce.
        Los históricos se procesan primero y la base vigente al final, para
        que ante un pedido repetido prevalezca la información más reciente.
        """
        historicas = []
        for nombre in wb.sheetnames:
            clave = normalizar(nombre).replace(" ", "")

            # Históricos fijos reales encontrados en la matriz ESACOM:
            #   BV 202601, BV 202602, ... BV202606
            #   BDVentas 072026
            # Se excluyen expresamente las hojas móviles (BV Móvil ...).
            es_bdventas = clave.startswith("BDVENTAS") and any(ch.isdigit() for ch in clave)
            es_bv_fijo = (
                clave.startswith("BV")
                and not clave.startswith("BVMOVIL")
                and not clave.startswith("BDVENTAS")
                and any(ch.isdigit() for ch in clave)
            )
            if es_bdventas or es_bv_fijo:
                historicas.append(nombre)

        def periodo_hoja(nombre):
            """Orden cronológico tolerante a BVYYYYMM y BDVentasMMYYYY."""
            digitos = "".join(ch for ch in normalizar(nombre) if ch.isdigit())
            if len(digitos) < 6:
                return "000000"
            d = digitos[-6:]
            # YYYYMM
            if d[:4].isdigit() and 2000 <= int(d[:4]) <= 2099 and 1 <= int(d[4:]) <= 12:
                return d
            # MMYYYY
            if 1 <= int(d[:2]) <= 12 and 2000 <= int(d[2:]) <= 2099:
                return f"{d[2:]}{d[:2]}"
            return "000000"

        hojas = sorted(historicas, key=lambda n: (periodo_hoja(n), n))
        tiene_vigente = "Base de Ventas" in wb.sheetnames
        if tiene_vigente:
            hojas.append("Base de Ventas")

        if not hojas:
            self.stdout.write(self.style.WARNING("No se encontraron hojas de ventas fijas, se omite."))
            return {"omitido": True}

        # Solo reseteamos la marca de vigencia cuando el archivo realmente
        # contiene la hoja actual. Así una carga histórica aislada no borra el
        # corte operacional vigente.
        lineas_fuente_vigente = None
        if tiene_vigente:
            lineas_fuente_vigente = self._reconstruir_lineas_fijas_vigentes(wb["Base de Ventas"])
            Venta.objects.filter(origen_venta=Venta.OrigenVenta.BASE_VENTAS).update(en_base_vigente=False)

        total = {
            "ventas_creadas": 0,
            "ventas_actualizadas": 0,
            "sin_ejecutivo_valido": 0,
            "sin_promocion_valida": 0,
            "ejecutivos_historicos_creados": 0,
            "hojas_importadas": hojas,
            "detalle_por_hoja": {},
        }

        for nombre_hoja in hojas:
            r = self._importar_hoja_ventas(
                wb[nombre_hoja],
                es_vigente=(nombre_hoja == "Base de Ventas"),
            )
            total["detalle_por_hoja"][nombre_hoja] = r
            for clave in (
                "ventas_creadas", "ventas_actualizadas",
                "sin_ejecutivo_valido", "sin_promocion_valida",
                "ejecutivos_historicos_creados",
            ):
                total[clave] += r.get(clave, 0)

            # Estos contadores son de trazabilidad por hoja. Se agregan al
            # resumen global sin alterar las métricas históricas existentes.
            total.setdefault("filas_procesadas", 0)
            total.setdefault("pedidos_unicos", 0)
            total.setdefault("duplicados_consolidados", 0)
            total.setdefault("duplicados_conflictivos", [])
            total["filas_procesadas"] += r.get("filas_procesadas", 0)
            total["pedidos_unicos"] += r.get("pedidos_unicos", 0)
            total["duplicados_consolidados"] += r.get("duplicados_consolidados", 0)
            total["duplicados_conflictivos"].extend(r.get("duplicados_conflictivos", []))

        if lineas_fuente_vigente is not None:
            lineas_fuente_vigente["lineas_vinculadas_a_venta"] = self._vincular_lineas_fijas_vigentes()
            total["lineas_fuente_vigente"] = lineas_fuente_vigente

        return total

    def _reconstruir_lineas_fijas_vigentes(self, ws):
        """Replica fila-a-fila la hoja vigente ``Base de Ventas``.

        Esta capa NO colapsa por N° PEDIDO. Es la fuente de producción
        operacional y debe conservar la misma granularidad que el pivot de
        Gerencia, incluso cuando un pedido aparece más de una vez.
        """
        mapa = mapa_encabezados(ws)
        ejecutivos_por_rut = {EjecutivoManager.normalize_rut(e.rut): e for e in Ejecutivo.objects.all()}

        # Reemplazo atómico del corte vigente. Si cualquier etapa posterior de
        # la importación falla, el transaction.atomic() del comando revierte
        # también este borrado y mantiene el último corte válido.
        VentaFijaFuente.objects.filter(en_base_vigente=True).delete()

        filas = []
        duplicados = {}
        total_rgu = 0
        for numero_fila, row in enumerate(ws.iter_rows(min_row=2), start=2):
            n_pedido = str(valor(row, mapa, "N° PEDIDO") or "").strip()
            rut_evt = _normalizar_rut_valor(valor(row, mapa, "RUT EVT"))
            nombre_evt = str(valor(row, mapa, "NOMBRE EVT") or "").strip()
            supervisor = str(valor(row, mapa, "SUPERVISOR") or "").strip()
            estado = str(valor(row, mapa, "ESTADO DE INSTALACION") or "").strip()
            promo = str(valor(row, mapa, "PROMOCION") or "").strip()
            rgu = _a_entero_positivo(valor(row, mapa, "RGU"))
            fecha_venta = a_fecha(valor(row, mapa, "FECHA VENTA"))

            # Descarta solo filas realmente vacías. No exigimos N° PEDIDO ni
            # promoción porque el pivot fuente tampoco los exige para sumar RGU.
            if not any((n_pedido, rut_evt, nombre_evt, supervisor, estado, promo, rgu, fecha_venta)):
                continue

            ejecutivo = ejecutivos_por_rut.get(rut_evt) if rut_evt else None
            filas.append(VentaFijaFuente(
                fila_fuente=numero_fila,
                hoja_fuente=ws.title,
                en_base_vigente=True,
                n_pedido=n_pedido,
                rut_evt=rut_evt,
                nombre_evt=nombre_evt,
                supervisor_fuente=supervisor,
                estado_instalacion_fuente=estado,
                rgu_base=rgu,
                fecha_venta=fecha_venta,
                promocion_fuente=promo,
                ejecutivo=ejecutivo,
            ))
            total_rgu += int(rgu or 0)
            if n_pedido:
                duplicados.setdefault(n_pedido, []).append(numero_fila)

        VentaFijaFuente.objects.bulk_create(filas, batch_size=500)
        duplicados_reales = {p: fs for p, fs in duplicados.items() if len(fs) > 1}
        return {
            "filas_fuente": len(filas),
            "rgu_fuente_total": total_rgu,
            "pedidos_duplicados": len(duplicados_reales),
            "detalle_pedidos_duplicados": duplicados_reales,
        }

    def _vincular_lineas_fijas_vigentes(self):
        """Vincula cada fila operacional después de terminar el import maestro.

        La reconstrucción de ``VentaFijaFuente`` ocurre antes de importar las
        ventas para preservar exactamente el XLSX. Durante ese import pueden
        crearse Ejecutivos históricos que todavía no existían al reconstruir
        las filas. Por eso al final resolvemos de nuevo tanto ``venta`` como
        ``ejecutivo`` sin alterar la atribución fuente de la fila.
        """
        ventas_por_pedido = {
            str(p).strip(): vid
            for vid, p in Venta.objects.exclude(n_pedido="").values_list("id", "n_pedido")
        }
        ejecutivos_por_rut = {
            EjecutivoManager.normalize_rut(rut): eid
            for eid, rut in Ejecutivo.objects.exclude(rut="").values_list("id", "rut")
        }
        lineas = list(VentaFijaFuente.objects.filter(en_base_vigente=True))
        cambios = []
        vinculadas_venta = 0
        vinculadas_ejecutivo = 0
        for linea in lineas:
            cambio = False
            venta_id = ventas_por_pedido.get(str(linea.n_pedido or "").strip())
            if linea.venta_id != venta_id:
                linea.venta_id = venta_id
                vinculadas_venta += 1
                cambio = True

            ejecutivo_id = None
            if linea.rut_evt:
                ejecutivo_id = ejecutivos_por_rut.get(EjecutivoManager.normalize_rut(linea.rut_evt))
            if linea.ejecutivo_id != ejecutivo_id:
                linea.ejecutivo_id = ejecutivo_id
                vinculadas_ejecutivo += 1
                cambio = True

            if cambio:
                cambios.append(linea)
        if cambios:
            VentaFijaFuente.objects.bulk_update(cambios, ["venta", "ejecutivo"], batch_size=500)
        return {
            "filas_actualizadas": len(cambios),
            "vinculadas_venta": vinculadas_venta,
            "vinculadas_ejecutivo": vinculadas_ejecutivo,
        }

    def _importar_hoja_ventas(self, ws, *, es_vigente=False):
        mapa = mapa_encabezados(ws)
        ejecutivos_por_rut = {EjecutivoManager.normalize_rut(e.rut): e for e in Ejecutivo.objects.all()}
        ejecutivos_por_codigo_andes = {
            normalizar(e.codigo_andes): e for e in Ejecutivo.objects.exclude(codigo_andes="")
        }
        promos_por_nombre = {p.nombre: p for p in Promocion.objects.all()}
        comunas_por_nombre = {c.nombre: c for c in Comuna.objects.all()}

        creadas, actualizadas, sin_ejecutivo, sin_promocion = 0, 0, 0, 0
        ejecutivos_historicos_creados = 0

        # ``N° PEDIDO`` es la llave maestra para el cruce KPI y por eso el
        # modelo Venta sigue siendo único por pedido. Sin embargo, la hoja
        # operacional puede traer más de una fila para el mismo pedido y la
        # tabla dinámica de Gerencia suma el RGU de TODAS esas filas. Si
        # hiciéramos update_or_create() sin consolidar, la última fila pisaría
        # el RGU de la anterior y producción quedaría corta.
        #
        # ``Venta`` conserva una llave maestra única por N° PEDIDO. Si la hoja
        # repite el pedido, el RGU maestro se consolida para no perder servicios.
        # Cuando EVT/supervisor/estado difieren, el pedido se marca como
        # conflictivo y NO se usa esa fila maestra para inventar atribuciones;
        # la granularidad operacional exacta permanece en ``VentaFijaFuente``.
        pedidos_vistos_en_hoja = {}
        filas_procesadas = 0
        duplicados_consolidados = 0
        duplicados_conflictivos = []

        for numero_fila, row in enumerate(ws.iter_rows(min_row=2), start=2):
            n_pedido = valor(row, mapa, "N° PEDIDO")
            if not n_pedido:
                continue
            filas_procesadas += 1

            rut_evt = _normalizar_rut_valor(valor(row, mapa, "RUT EVT"))
            ejecutivo = ejecutivos_por_rut.get(rut_evt)
            if not ejecutivo and rut_evt:
                # Los KPI acumulativos incluyen camadas antiguas. Muchos EVT
                # históricos ya no aparecen en la Dotación vigente, pero la
                # venta debe conservarse para poder cruzar el pedido. Creamos
                # un usuario histórico INACTIVO, sin contraseña de acceso.
                nombre_evt_historico = str(valor(row, mapa, "NOMBRE EVT") or "Ejecutivo histórico").strip()
                ejecutivo, creado_hist = Ejecutivo.objects.get_or_create(
                    rut=rut_evt,
                    defaults=dict(
                        nombre=nombre_evt_historico or "Ejecutivo histórico",
                        cargo=Ejecutivo.Cargo.EJECUTIVO,
                        estado_contrato=Ejecutivo.EstadoContrato.INACTIVO,
                        is_active=False,
                    ),
                )
                if creado_hist:
                    ejecutivo.set_unusable_password()
                    ejecutivo.save(update_fields=["password"])
                    ejecutivos_historicos_creados += 1
                ejecutivos_por_rut[rut_evt] = ejecutivo

            if not ejecutivo:
                # Algunos respaldos antiguos traen pedido/cliente/CE pero no
                # RUT EVT. No inventamos una persona: la venta se conserva con
                # EVT nulo para que el cruce KPI por N° PEDIDO no se pierda.
                sin_ejecutivo += 1

            # CE = propietario final utilizado por Claro para atribuir el KPI.
            rut_ce = _normalizar_rut_valor(valor(row, mapa, "RUT CE"))
            codigo_ce = str(valor(row, mapa, "CODIGO CE") or "").strip()
            ejecutivo_ce = ejecutivos_por_rut.get(rut_ce) if rut_ce else None
            if not ejecutivo_ce and codigo_ce:
                ejecutivo_ce = ejecutivos_por_codigo_andes.get(normalizar(codigo_ce))
            if not ejecutivo_ce and rut_ce:
                # El propietario final también puede ser una persona que ya
                # salió de la Dotación vigente. El RUT CE sigue siendo una
                # clave confiable para mantener la atribución histórica.
                ejecutivo_ce, creado_hist_ce = Ejecutivo.objects.get_or_create(
                    rut=rut_ce,
                    defaults=dict(
                        nombre=f"CE histórico {codigo_ce}".strip() if codigo_ce else "CE histórico",
                        cargo=Ejecutivo.Cargo.EJECUTIVO,
                        estado_contrato=Ejecutivo.EstadoContrato.INACTIVO,
                        is_active=False,
                    ),
                )
                if creado_hist_ce:
                    ejecutivo_ce.set_unusable_password()
                    ejecutivo_ce.save(update_fields=["password"])
                    ejecutivos_historicos_creados += 1
                ejecutivos_por_rut[rut_ce] = ejecutivo_ce

            promo_nombre = str(valor(row, mapa, "PROMOCION") or "").strip()
            promocion = promos_por_nombre.get(promo_nombre)
            if not promocion:
                sin_promocion += 1
                continue

            comuna_nombre = str(valor(row, mapa, "COMUNA") or "").strip()
            comuna = comunas_por_nombre.get(comuna_nombre)

            fecha_venta = a_fecha(valor(row, mapa, "FECHA VENTA")) or datetime.date.today()
            camada = f"{fecha_venta.year:04d}-{fecha_venta.month:02d}"

            pedido_key = str(n_pedido).strip()
            supervisor_fuente = str(valor(row, mapa, "SUPERVISOR") or "").strip()
            estado_fuente = str(valor(row, mapa, "ESTADO DE INSTALACION") or "").strip()
            nombre_evt_fuente = str(valor(row, mapa, "NOMBRE EVT") or "").strip()
            rgu_fila = _a_entero_positivo(valor(row, mapa, "RGU"))
            firma_operacional = (
                rut_evt,
                normalizar(nombre_evt_fuente),
                normalizar(supervisor_fuente),
                normalizar(estado_fuente),
            )

            previo = pedidos_vistos_en_hoja.get(pedido_key)
            if previo is None:
                rgu_consolidado = rgu_fila
                pedidos_vistos_en_hoja[pedido_key] = {
                    "firma": firma_operacional,
                    "rgu": int(rgu_fila or 0),
                    "primera_fila": numero_fila,
                }
            else:
                # La producción NO se colapsa aquí: cada fila vigente ya quedó
                # preservada en VentaFijaFuente. Para el pedido maestro solo
                # consolidamos el RGU y registramos si la atribución/estado es
                # ambiguo. Así KPI mantiene una llave N° PEDIDO única sin
                # borrar información operacional de ESACOM.
                rgu_total = int(previo.get("rgu") or 0) + int(rgu_fila or 0)
                previo["rgu"] = rgu_total
                rgu_consolidado = rgu_total
                conflicto = previo["firma"] != firma_operacional
                if conflicto:
                    detalle = {
                        "n_pedido": pedido_key,
                        "primera_fila": previo["primera_fila"],
                        "fila_conflicto": numero_fila,
                        "firma_primera": previo["firma"],
                        "firma_conflicto": firma_operacional,
                    }
                    duplicados_conflictivos.append(detalle)
                else:
                    duplicados_consolidados += 1

                existente = Venta.objects.filter(n_pedido=pedido_key).first()
                if existente is not None:
                    existente.rgu_base = rgu_total
                    existente.en_base_vigente = bool(es_vigente) or existente.en_base_vigente
                    existente.hoja_fuente = ws.title
                    campos_update = ["rgu_base", "en_base_vigente", "hoja_fuente", "actualizado_en"]
                    if conflicto:
                        existente.conflicto_fuente = True
                        existente.detalle_conflicto_fuente = detalle
                        campos_update += ["conflicto_fuente", "detalle_conflicto_fuente"]

                        rut_primero, nombre_primero, sup_primero, estado_primero = previo["firma"]
                        rut_actual, nombre_actual, sup_actual, estado_actual = firma_operacional
                        if rut_primero != rut_actual or nombre_primero != nombre_actual:
                            # No adjudicamos un pedido ambiguo a una persona.
                            # Las filas operacionales sí conservan cada EVT.
                            existente.ejecutivo = None
                            existente.rut_evt = ""
                            existente.nombre_evt = ""
                            campos_update += ["ejecutivo", "rut_evt", "nombre_evt"]
                        if sup_primero != sup_actual:
                            existente.supervisor_fuente = ""
                            campos_update.append("supervisor_fuente")
                        if estado_primero != estado_actual:
                            existente.estado_instalacion_fuente = "CONFLICTO MULTILINEA"
                            # Estado conservador para que un pedido ambiguo no
                            # entre accidentalmente a Accionables como instalado.
                            existente.estado_instalacion = Venta.EstadoInstalacion.PENDIENTE_COMERCIAL
                            campos_update += ["estado_instalacion_fuente", "estado_instalacion"]
                    existente.save(update_fields=list(dict.fromkeys(campos_update)))
                    actualizadas += 1
                # La primera fila ya creó/actualizó el pedido maestro. La fila
                # adicional vive en VentaFijaFuente; no hacemos un segundo
                # update_or_create que vuelva a pisar campos del pedido.
                continue

            venta, creado = Venta.objects.update_or_create(
                n_pedido=pedido_key,
                defaults=dict(
                    rut_cliente=str(valor(row, mapa, "RUT CLIENTE") or ""),
                    nombre_cliente=str(valor(row, mapa, "NOMBRE CLIENTE") or "").strip(),
                    telefono_cliente=_limpiar_telefono(valor(row, mapa, "NUMERO CLIENTE")),
                    rut_evt=rut_evt,
                    nombre_evt=nombre_evt_fuente,
                    origen_venta=Venta.OrigenVenta.BASE_VENTAS,
                    supervisor_fuente=supervisor_fuente,
                    estado_instalacion_fuente=estado_fuente,
                    hoja_fuente=ws.title,
                    en_base_vigente=bool(es_vigente),
                    conflicto_fuente=False,
                    detalle_conflicto_fuente={},
                    fecha_pago_honorarios=None,
                    rut_ce=rut_ce,
                    codigo_ce=codigo_ce,
                    rgu_base=rgu_consolidado,
                    ejecutivo=ejecutivo,
                    ejecutivo_ce=ejecutivo_ce,
                    promocion=promocion,
                    comuna=comuna,
                    tipo_cliente=str(valor(row, mapa, "B2C/B2B") or "B2C")[:3],
                    estado_instalacion=self._mapear_estado_instalacion(valor(row, mapa, "ESTADO DE INSTALACION")),
                    motivo_pendiente=str(valor(row, mapa, "MOTIVO PENDIENTE") or ""),
                    fecha_venta=fecha_venta,
                    primera_agenda=a_fecha(valor(row, mapa, "1a Agenda")),
                    segunda_agenda=a_fecha(valor(row, mapa, "2a Agenda")),
                    fecha_cierre=a_fecha(valor(row, mapa, "FECHA CIERRE")),
                    precio_venta=a_decimal(valor(row, mapa, "Precio Venta")),
                    honorarios=None,
                    ingresador=str(valor(row, mapa, "INGRESADOR") or ""),
                    camada=camada,
                ),
            )
            creadas += int(creado)
            actualizadas += int(not creado)

            vencimiento = a_fecha(valor(row, mapa, "VENCIMIENTO 1ra BOLETA"))
            if vencimiento:
                Corte.objects.update_or_create(
                    venta=venta,
                    mes_ano=camada,
                    boleta=Corte.Boleta.B1,
                    defaults=dict(
                        meta_pct=Decimal("0"),
                        fecha_vencimiento=vencimiento,
                        fecha_pago=a_fecha(valor(row, mapa, "Fecha Pago H")),
                    ),
                )

        return {
            "ventas_creadas": creadas,
            "ventas_actualizadas": actualizadas,
            "filas_procesadas": filas_procesadas,
            "pedidos_unicos": len(pedidos_vistos_en_hoja),
            "duplicados_consolidados": duplicados_consolidados,
            "duplicados_conflictivos": duplicados_conflictivos,
            "sin_ejecutivo_valido": sin_ejecutivo,
            "sin_promocion_valida": sin_promocion,
            "ejecutivos_historicos_creados": ejecutivos_historicos_creados,
        }

    # ------------------------------------------------------------------
    # Ventas Móvil -> VentaMovil
    # ------------------------------------------------------------------
    def _importar_base_movil(self, wb):
        """Importa la hoja móvil vigente y sus respaldos históricos.

        La hoja móvil no usa N° de pedido. Cada fila representa una línea
        (Principal/Adicional/PPM), por eso se mantiene en un modelo separado.
        La marca ``en_base_vigente`` reproduce exactamente el universo de la
        hoja "Ventas Móvil" actual usado por los pivots operacionales.
        """
        historicas = []
        for nombre in wb.sheetnames:
            clave = normalizar(nombre).replace(" ", "")
            if nombre == "Ventas Móvil":
                continue
            es_bv_movil = clave.startswith("BVMOVIL") and any(ch.isdigit() for ch in clave)
            es_movil = clave.startswith("MOVIL") and any(ch.isdigit() for ch in clave)
            if es_bv_movil or es_movil:
                historicas.append(nombre)

        def periodo_hoja(nombre):
            digitos = "".join(ch for ch in normalizar(nombre) if ch.isdigit())
            if len(digitos) < 6:
                return "000000"
            d = digitos[-6:]
            if 2000 <= int(d[:4]) <= 2099 and 1 <= int(d[4:]) <= 12:
                return d
            if 1 <= int(d[:2]) <= 12 and 2000 <= int(d[2:]) <= 2099:
                return f"{d[2:]}{d[:2]}"
            return "000000"

        hojas = sorted(historicas, key=lambda n: (periodo_hoja(n), n))
        tiene_vigente = "Ventas Móvil" in wb.sheetnames
        if tiene_vigente:
            hojas.append("Ventas Móvil")

        if not hojas:
            self.stdout.write(self.style.WARNING("No se encontraron hojas de ventas móviles, se omite."))
            return {"omitido": True}

        if tiene_vigente:
            VentaMovil.objects.all().update(en_base_vigente=False)

        total = {
            "moviles_creadas": 0,
            "moviles_actualizadas": 0,
            "sin_ejecutivo_valido": 0,
            "hojas_importadas": hojas,
            "detalle_por_hoja": {},
        }
        for nombre_hoja in hojas:
            r = self._importar_hoja_movil(
                wb[nombre_hoja],
                es_vigente=(nombre_hoja == "Ventas Móvil"),
            )
            total["detalle_por_hoja"][nombre_hoja] = r
            for clave in ("moviles_creadas", "moviles_actualizadas", "sin_ejecutivo_valido"):
                total[clave] += r.get(clave, 0)
        return total

    def _importar_hoja_movil(self, ws, *, es_vigente=False):
        mapa = mapa_encabezados(ws)
        ejecutivos_por_rut = {EjecutivoManager.normalize_rut(e.rut): e for e in Ejecutivo.objects.all()}
        por_nombre = {}
        for e in Ejecutivo.objects.all():
            por_nombre.setdefault(normalizar(e.nombre), []).append(e)

        creadas = actualizadas = sin_ejecutivo = 0
        for row in ws.iter_rows(min_row=2):
            rut_cliente = _normalizar_rut_valor(valor(row, mapa, "RUT CLIENTE"))
            nombre_evt = str(
                valor(row, mapa, "NOMBRE EVT")
                or valor(row, mapa, "NOMBRE EJECUTIVO")
                or ""
            ).strip()
            rut_evt = _normalizar_rut_valor(valor(row, mapa, "RUT EVT"))
            pcs = _limpiar_pcs(valor(row, mapa, "PCS"))
            fecha_venta = a_fecha(valor(row, mapa, "FECHA VENTA"))
            tipo_linea = _tipo_linea_movil(valor(row, mapa, "PPAL/ADICI."))

            # Filas vacías/de fórmula no forman parte del universo móvil.
            if not any((rut_cliente, nombre_evt, rut_evt, pcs, fecha_venta)):
                continue

            ejecutivo = ejecutivos_por_rut.get(rut_evt) if rut_evt else None
            if not ejecutivo and nombre_evt:
                candidatos = por_nombre.get(normalizar(nombre_evt), [])
                if len(candidatos) == 1:
                    ejecutivo = candidatos[0]
            if not ejecutivo:
                sin_ejecutivo += 1

            camada = f"{fecha_venta.year:04d}-{fecha_venta.month:02d}" if fecha_venta else ""
            identidad = "|".join([
                pcs,
                fecha_venta.isoformat() if fecha_venta else "",
                rut_cliente,
                rut_evt,
                tipo_linea,
                str(valor(row, mapa, "PLAN") or "").strip(),
            ])
            clave_origen = hashlib.sha256(identidad.encode("utf-8")).hexdigest()

            _, creado = VentaMovil.objects.update_or_create(
                clave_origen=clave_origen,
                defaults=dict(
                    rut_cliente=rut_cliente,
                    supervisor_fuente=str(valor(row, mapa, "SUPERVISOR") or "").strip(),
                    nombre_evt=nombre_evt,
                    rut_evt_ingreso=_normalizar_rut_valor(valor(row, mapa, "RUT EVT INGRESO")),
                    codigo_ingreso=str(valor(row, mapa, "CODIGO A INGRESO") or "").strip(),
                    rut_evt=rut_evt,
                    ejecutivo=ejecutivo,
                    migracion=str(valor(row, mapa, "MIGRACIÓN") or "").strip(),
                    tipo_linea=tipo_linea,
                    plan=str(valor(row, mapa, "PLAN") or "").strip(),
                    pcs=pcs,
                    fecha_venta=fecha_venta,
                    fecha_activacion=a_fecha(valor(row, mapa, "FECHA ACTIVACIÓN")),
                    donante=str(valor(row, mapa, "DONANTE") or "").strip(),
                    estado=str(valor(row, mapa, "ESTADO") or "").strip(),
                    observacion=str(valor(row, mapa, "OBSERVACION") or "").strip(),
                    fecha_cc=a_fecha(valor(row, mapa, "FECHA CC")),
                    camada=camada,
                    hoja_fuente=ws.title,
                    en_base_vigente=bool(es_vigente),
                ),
            )
            creadas += int(creado)
            actualizadas += int(not creado)

        return {
            "moviles_creadas": creadas,
            "moviles_actualizadas": actualizadas,
            "sin_ejecutivo_valido": sin_ejecutivo,
        }

    @staticmethod
    def _mapear_estado_instalacion(v) -> str:
        txt = normalizar(v)
        if "ANULADO" in txt:
            return Venta.EstadoInstalacion.ANULADO
        if "PENDIENTE" in txt and "COMERCIAL" in txt:
            return Venta.EstadoInstalacion.PENDIENTE_COMERCIAL
        if "INSTALADO" in txt or "COMPLETAD" in txt:
            return Venta.EstadoInstalacion.INSTALADO
        return Venta.EstadoInstalacion.PENDIENTE_INSTALACION
