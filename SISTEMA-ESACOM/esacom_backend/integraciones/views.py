import datetime
import os
import tempfile
from decimal import Decimal, InvalidOperation

from django.db.models import Count, Q
from rest_framework import mixins, viewsets
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.decorators import action, api_view, parser_classes, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from core.permissions import EsGerencia, PuedeCargarDatos, PuedeAuditoriaKPI, PuedeHistorico, EsSoporte

from .models import CargaExcel, ClaroImport, KPIRegistro, MetaKPICalidad
from .locks import adquirir_lock_operacion_datos, liberar_lock_operacion_datos
from .serializers import CargaExcelSerializer, ClaroImportSerializer, KPIRegistroSerializer, MetaKPICalidadSerializer


class ClaroImportViewSet(viewsets.ReadOnlyModelViewSet):
    """Solo Gerencia -- módulo Admin / auditoría del cruce con Claro."""

    queryset = ClaroImport.objects.select_related("carga").all()
    serializer_class = ClaroImportSerializer
    permission_classes = [PuedeAuditoriaKPI]
    filterset_fields = ["cruce_ok"]


class KPIRegistroPagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 500


class KPIRegistroViewSet(viewsets.ReadOnlyModelViewSet):
    """Historial de snapshots KPI de lunes/miércoles, incluido lo que no cruzó."""

    queryset = KPIRegistro.objects.select_related(
        "carga", "venta", "venta__ejecutivo_ce", "venta__ejecutivo"
    ).all()
    serializer_class = KPIRegistroSerializer
    permission_classes = [PuedeAuditoriaKPI]
    pagination_class = KPIRegistroPagination
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["num_pedido", "rut_cliente", "propietario_final", "bill_no"]
    ordering_fields = ["importado_en", "camada", "num_pedido", "boleta"]
    ordering = ["-importado_en"]
    filterset_fields = [
        "carga",
        "camada",
        "boleta",
        "cruce_ok",
        "diferencia_rut",
        "diferencia_rgu",
        "diferencia_propietario",
        "diferencia_estado",
        "es_medible",
        "ejecutivo_kpi_no_resuelto",
    ]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("alerta") in ("1", "true", "True"):
            qs = qs.filter(
                Q(cruce_ok=False)
                | Q(diferencia_rut=True)
                | Q(diferencia_rgu=True)
                | Q(diferencia_propietario=True)
                | Q(diferencia_estado=True)
                | Q(es_medible=False)
                | Q(ejecutivo_kpi_no_resuelto=True)
            )
        # Como reemplazamos filter_backends para habilitar búsqueda/orden,
        # aplicamos aquí los filtros simples usados por la auditoría.
        for campo in (
            "carga", "camada", "boleta", "cruce_ok", "diferencia_rut",
            "diferencia_rgu", "diferencia_propietario", "diferencia_estado", "es_medible",
            "ejecutivo_kpi_no_resuelto",
        ):
            valor = self.request.query_params.get(campo)
            if valor is not None and valor != "":
                if campo.startswith("diferencia_") or campo in ("cruce_ok", "es_medible", "ejecutivo_kpi_no_resuelto"):
                    valor = valor in ("1", "true", "True")
                qs = qs.filter(**{campo: valor})
        return qs


    @action(detail=False, methods=["get"], url_path="resumen")
    def resumen(self, request):
        """
        Resumen de auditoría para una carga KPI. Cuenta filas (no suma
        banderas), y separa inconsistencias reales de casos informativos
        como ``FUERA DE MEDICIÓN``.
        """
        qs = self.get_queryset()
        carga = request.query_params.get("carga")
        if carga:
            qs = qs.filter(carga_id=carga)

        inconsistentes = qs.filter(
            Q(cruce_ok=False)
            | Q(diferencia_rut=True)
            | Q(diferencia_rgu=True)
            | Q(diferencia_propietario=True)
            | Q(diferencia_estado=True)
            | Q(ejecutivo_kpi_no_resuelto=True)
        ).distinct()

        por_estado = {
            fila["estado_normalizado"] or "SIN_ESTADO": fila["total"]
            for fila in qs.values("estado_normalizado").annotate(total=Count("id"))
        }
        por_boleta = {
            fila["boleta"]: fila["total"]
            for fila in qs.values("boleta").annotate(total=Count("id"))
        }

        return Response({
            "total": qs.count(),
            "cruzados": qs.filter(cruce_ok=True).count(),
            "sin_cruce": qs.filter(cruce_ok=False).count(),
            "filas_con_inconsistencia": inconsistentes.count(),
            "diferencia_rut": qs.filter(diferencia_rut=True).count(),
            "diferencia_rgu": qs.filter(diferencia_rgu=True).count(),
            "diferencia_propietario": qs.filter(diferencia_propietario=True).count(),
            "diferencia_estado": qs.filter(diferencia_estado=True).count(),
            "ejecutivo_no_resuelto": qs.filter(ejecutivo_kpi_no_resuelto=True).count(),
            "fuera_medicion": qs.filter(es_medible=False).count(),
            "medibles": qs.filter(es_medible=True).count(),
            "por_estado": por_estado,
            "por_boleta": por_boleta,
        })




class MetaKPICalidadViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """Vigencias de metas ESACOM. Solo Soporte puede crear nuevas vigencias.

    No se exponen PATCH/PUT/DELETE: cambiar una meta crea una nueva vigencia y
    preserva el histórico de meses ya cerrados.
    """

    permission_classes = [EsSoporte]
    serializer_class = MetaKPICalidadSerializer
    queryset = MetaKPICalidad.objects.select_related("creado_por").all()
    pagination_class = None

    def perform_create(self, serializer):
        serializer.save(creado_por=self.request.user)


class CargaExcelViewSet(viewsets.ReadOnlyModelViewSet):
    """Historial de cargas -- snapshots persistidos de lunes/miércoles."""

    queryset = CargaExcel.objects.select_related("creado_por").all()
    serializer_class = CargaExcelSerializer
    permission_classes = [PuedeHistorico]
    pagination_class = KPIRegistroPagination
    filterset_fields = ["origen", "tipo_base", "dia_reporte", "estado_reporte", "formato_kpi", "fecha_corte"]


def _normalizar_camada_reporte(valor):
    """Convierte 202607 / '202607' / '2026-07' a '2026-07'."""
    if valor is None:
        return ""
    txt = str(valor).strip().replace(".0", "")
    if len(txt) == 6 and txt.isdigit():
        return f"{txt[:4]}-{txt[4:]}"
    if len(txt) == 7 and txt[4] == "-":
        return txt
    return ""


def _porcentaje_reporte(valor):
    if valor is None or valor == "":
        return None
    if isinstance(valor, (int, float, Decimal)):
        numero = Decimal(str(valor))
        return numero * 100 if numero <= 1 else numero
    txt = str(valor).strip().replace("%", "").replace(",", ".")
    try:
        return Decimal(txt)
    except InvalidOperation:
        return None


def _extraer_focos_y_metas_kpi(path):
    """
    Lee la tabla oficial 'RESUMEN GESTION RGU' del KPI de Claro.
    No usa Claro como maestro de ventas: solo extrae metadata de medición
    (foco B1/B2/B3 y meta oficial) para el snapshot.
    """
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
        if "RESUMEN GESTION RGU" not in wb.sheetnames:
            return {}
        ws = wb["RESUMEN GESTION RGU"]
        titulos = []
        for cell in ws[1]:
            val = str(cell.value or "").strip().upper()
            if "PRIMERA BOLETA" in val:
                titulos.append((cell.column, "B1"))
            elif "SEGUNDA BOLETA" in val:
                titulos.append((cell.column, "B2"))
            elif "TERCERA BOLETA" in val:
                titulos.append((cell.column, "B3"))
        titulos.sort()
        resultado = {}
        for idx, (inicio, boleta) in enumerate(titulos):
            fin = (titulos[idx + 1][0] - 1) if idx + 1 < len(titulos) else ws.max_column
            camada = ""
            meta_col = None
            # La cabecera CAMADA/META puede moverse; se busca dentro del bloque.
            for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 40), min_col=inicio, max_col=fin):
                for cell in row:
                    txt = str(cell.value or "").strip().upper()
                    if txt == "CAMADA" and cell.column + 1 <= fin:
                        camada = _normalizar_camada_reporte(ws.cell(cell.row, cell.column + 1).value)
                    if txt == "META":
                        meta_col = cell.column
            meta = None
            if meta_col:
                # Preferimos Total general; si no existe usamos el primer valor de meta.
                primer_meta = None
                for r in range(1, ws.max_row + 1):
                    valor = _porcentaje_reporte(ws.cell(r, meta_col).value)
                    if valor is not None and str(ws.cell(r, meta_col).value).strip().upper() != "META":
                        if primer_meta is None:
                            primer_meta = valor
                        etiqueta = str(ws.cell(r, inicio).value or "").strip().upper()
                        if etiqueta == "TOTAL GENERAL":
                            meta = valor
                            break
                meta = meta if meta is not None else primer_meta
            resultado[f"foco_{boleta.lower()}"] = camada
            resultado[f"meta_{boleta.lower()}"] = meta
        return resultado
    except Exception:
        # La carga del KPI no debe fallar solo porque la hoja resumen cambió;
        # el importador BASE seguirá funcionando y el usuario puede indicar metas manualmente.
        return {}


def _contar_filas_afectadas(resumen: dict) -> int:
    """Cuenta filas tocadas por el importador de base matriz."""
    if not resumen:
        return 0
    if "filas_leidas" in resumen:
        return resumen["filas_leidas"]
    claves_positivas = {
        "creados",
        "creadas",
        "actualizados",
        "actualizadas",
        "ventas_creadas",
        "ventas_actualizadas",
        "comunas_creadas",
        "filas_importadas",
    }
    total = 0
    for v in resumen.values():
        if isinstance(v, dict):
            for clave in claves_positivas:
                total += v.get(clave, 0)
    return total


@api_view(["POST"])
@parser_classes([MultiPartParser])
@permission_classes([EsSoporte])
def cargar_excel_view(request):
    """
    POST /api/integraciones/cargar-excel/  (multipart/form-data)
    Campos: archivo (.xlsx), tipo ('BASE_MATRIZ' | 'REPORTE_KPI')

    Los imports pesados (openpyxl) se cargan *dentro* de esta función y
    no al importar urls.py. Así `python manage.py migrate/check` ya no
    necesita cargar openpyxl para arrancar Django.
    """
    archivo = request.FILES.get("archivo")
    tipo = request.data.get("tipo", "BASE_MATRIZ")

    fecha_corte = None
    dia_reporte = ""
    estado_reporte = CargaExcel.EstadoReporte.AVANCE
    formato_kpi = CargaExcel.FormatoKPI.DETALLADO
    avances = {"avance_b1": None, "avance_b2": None, "avance_b3": None}
    metas = {"meta_b1": None, "meta_b2": None, "meta_b3": None}
    focos = {"foco_b1": "", "foco_b2": "", "foco_b3": ""}
    if tipo == "REPORTE_KPI":
        fecha_corte_txt = str(request.data.get("fecha_corte") or "").strip()
        if fecha_corte_txt:
            try:
                fecha_corte = datetime.date.fromisoformat(fecha_corte_txt)
            except ValueError:
                return Response({"detail": "fecha_corte debe tener formato AAAA-MM-DD."}, status=400)
        else:
            return Response({"detail": "Para un REPORTE_KPI debes indicar la fecha de corte informada por Claro."}, status=400)

        dia_reporte = str(request.data.get("dia_reporte") or "OTRO").upper()
        if dia_reporte not in CargaExcel.DiaReporte.values:
            return Response({"detail": "dia_reporte debe ser LUNES, MIERCOLES, JUEVES u OTRO."}, status=400)

        estado_reporte = str(request.data.get("estado_reporte") or "AVANCE").upper()
        if estado_reporte not in CargaExcel.EstadoReporte.values:
            return Response({"detail": "estado_reporte debe ser AVANCE o CIERRE."}, status=400)

        formato_kpi = str(request.data.get("formato_kpi") or CargaExcel.FormatoKPI.DETALLADO).upper()
        if formato_kpi not in CargaExcel.FormatoKPI.values:
            return Response({
                "detail": "formato_kpi debe ser DETALLADO, AVANCE_MOVIL, CIERRE_FIJO o CIERRE_MOVIL."
            }, status=400)

        formatos_cierre = {CargaExcel.FormatoKPI.CIERRE_FIJO, CargaExcel.FormatoKPI.CIERRE_MOVIL}
        if formato_kpi in formatos_cierre and estado_reporte != CargaExcel.EstadoReporte.CIERRE:
            return Response({
                "detail": f"El formato {formato_kpi} solo se puede cargar como CIERRE oficial."
            }, status=400)
        if formato_kpi in {CargaExcel.FormatoKPI.DETALLADO, CargaExcel.FormatoKPI.AVANCE_MOVIL} and estado_reporte != CargaExcel.EstadoReporte.AVANCE:
            return Response({
                "detail": f"El formato {formato_kpi} debe cargarse como AVANCE."
            }, status=400)

        for campo in {**avances, **metas}:
            valor = str(request.data.get(campo) or "").strip().replace(",", ".")
            if valor:
                try:
                    if campo in avances:
                        avances[campo] = Decimal(valor)
                    else:
                        metas[campo] = Decimal(valor)
                except InvalidOperation:
                    return Response({"detail": f"{campo} debe ser un porcentaje válido."}, status=400)

    if not archivo:
        return Response({"detail": "Falta el archivo."}, status=400)
    if not archivo.name.lower().endswith(".xlsx"):
        return Response({"detail": "El archivo debe ser un .xlsx."}, status=400)
    if tipo not in ("BASE_MATRIZ", "REPORTE_KPI"):
        return Response({"detail": "tipo debe ser BASE_MATRIZ o REPORTE_KPI."}, status=400)

    try:
        lock_operacion = adquirir_lock_operacion_datos()
    except Exception as exc:
        return Response({"detail": f"No se pudo verificar el lock de operaciones: {exc}"}, status=503)
    if lock_operacion is False:
        return Response({
            "detail": "Hay una sincronización ESACOM o una carga KPI en curso. Espera a que termine y vuelve a intentar."
        }, status=409)

    tmp_path = None
    carga = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            for chunk in archivo.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        if tipo == "REPORTE_KPI" and formato_kpi in {
            CargaExcel.FormatoKPI.DETALLADO, CargaExcel.FormatoKPI.CIERRE_FIJO
        }:
            metadata_reporte = _extraer_focos_y_metas_kpi(tmp_path)
            for campo in focos:
                focos[campo] = metadata_reporte.get(campo) or ""
            # Si el usuario indicó una meta manual, prevalece. Si la dejó vacía,
            # usamos la meta oficial que viene en RESUMEN GESTION RGU.
            for campo in metas:
                if metas[campo] is None and metadata_reporte.get(campo) is not None:
                    metas[campo] = metadata_reporte[campo]

        if tipo == "BASE_MATRIZ":
            from integraciones.management.commands.importar_excel import Command as ImportarExcelCommand

            cmd = ImportarExcelCommand()
            cmd.handle(archivo=tmp_path, solo="", dry_run=False, usuario_rut=request.user.rut)
            resumen = cmd.resumen

            carga = CargaExcel.objects.create(
                origen=CargaExcel.Origen.MANUAL,
                tipo_base=CargaExcel.TipoBase.BASE_MATRIZ,
                archivo_nombre=archivo.name,
                creado_por=request.user,
                filas_totales=_contar_filas_afectadas(resumen),
            )
        else:
            from integraciones.management.commands.importar_kpi import Command as ImportarKpiCommand

            # Se crea antes para que cada KPIRegistro quede ligado al archivo
            # exacto que lo originó. Si el procesamiento falla, se elimina.
            carga = CargaExcel.objects.create(
                origen=CargaExcel.Origen.MANUAL,
                tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
                archivo_nombre=archivo.name,
                creado_por=request.user,
                fecha_corte=fecha_corte,
                dia_reporte=dia_reporte,
                estado_reporte=estado_reporte,
                formato_kpi=formato_kpi,
                **avances,
                **metas,
                **focos,
            )
            if formato_kpi in {CargaExcel.FormatoKPI.AVANCE_MOVIL, CargaExcel.FormatoKPI.CIERRE_MOVIL}:
                from integraciones.management.commands.importar_kpi_movil_cierre import Command as ImportarMovilCommand
                cmd = ImportarMovilCommand()
                cmd.handle(
                    archivo=tmp_path,
                    carga_id=carga.id,
                    fecha_corte=fecha_corte.isoformat(),
                )
            else:
                cmd = ImportarKpiCommand()
                cmd.handle(
                    archivo=tmp_path,
                    dry_run=False,
                    limite=None,
                    hoja="BASE",
                    carga_id=carga.id,
                    usuario_rut=request.user.rut,
                    archivo_nombre=archivo.name,
                    fecha_corte=fecha_corte.isoformat() if fecha_corte else "",
                    dia_reporte=dia_reporte,
                )
            resumen = cmd.resumen
            carga.refresh_from_db()
            if isinstance(resumen, dict):
                resumen.setdefault("formato", formato_kpi)
                resumen.setdefault("estado_reporte", estado_reporte)
                resumen.setdefault("canal_calidad", "MOVIL" if formato_kpi in {CargaExcel.FormatoKPI.AVANCE_MOVIL, CargaExcel.FormatoKPI.CIERRE_MOVIL} else "FIJO")
    except Exception as exc:
        if carga is not None and carga.tipo_base == CargaExcel.TipoBase.REPORTE_KPI:
            carga.delete()
        return Response({"detail": f"No se pudo procesar el archivo: {exc}"}, status=400)
    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        liberar_lock_operacion_datos(lock_operacion)

    return Response(
        {
            "carga_id": carga.id if carga else None,
            "resumen": resumen,
        }
    )


@api_view(["POST"])
def sincronizar_google_sheets_view(request):
    """Sincronización manual de la fuente maestra ESACOM desde Google Sheets.

    Permitida a quien tenga Carga de Datos, además de Soporte técnico.
    La Sheet aporta únicamente datos ESACOM; los KPI Claro siguen entrando por REPORTE_KPI.
    """
    u = request.user
    if not (u and u.is_authenticated and (u.is_superuser or getattr(u, "es_soporte", False))):
        return Response({"detail": "Solo Soporte puede sincronizar Google Sheets."}, status=403)
    try:
        lock_operacion = adquirir_lock_operacion_datos()
    except Exception as exc:
        return Response({"detail": f"No se pudo verificar el lock de operaciones: {exc}"}, status=503)
    if lock_operacion is False:
        return Response({
            "detail": "Hay una carga KPI o sincronización ESACOM en curso. Espera a que termine y vuelve a intentar."
        }, status=409)
    try:
        from integraciones.services.google_sheets import sincronizar_base_matriz
        resultado = sincronizar_base_matriz(creado_por=u)
        return Response(resultado)
    except Exception as exc:
        return Response({"detail": str(exc)}, status=400)
    finally:
        liberar_lock_operacion_datos(lock_operacion)
