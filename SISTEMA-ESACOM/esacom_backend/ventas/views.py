import csv
import logging
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from django.db import models
from django.db.models import Sum
from django.http import HttpResponse
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.mixins import RoleScopedMixin
from core.permissions import EsEjecutivo, EsGerencia, EsSupervisorOGerencia, EsSupervisorOModifica, EsOperacionesOGerencia, PuedeAccionables, PuedeCobranza, PuedeHistorico, PuedeMiEquipo, PuedeDashboardGerencia, PuedeApelaciones, PuedeDashboardOAnalisis, PuedeMiEquipoOAnalisis

from .apelaciones import detectar_apelaciones
from .emails import enviar_apelacion_por_correo
from .models import Apelacion, Corte, Gestion, Venta
from usuarios.models import Ejecutivo
from integraciones.services.metas_kpi import meta_calidad_para, metas_calidad_para_focos, serializar_meta
from integraciones.report_dates import fecha_reporte_desde_nombre
from .serializers import ApelacionSerializer, CorteSerializer, GestionSerializer, VentaSerializer
from .services import (
    resumen_accionables,
    resumen_cortes_actuales,
    resumen_historico_camadas,
    resumen_por_corte,
    resumen_por_ejecutivo,
    resumen_por_ejecutivo_actual,
    resumen_por_supervisor_actual,
    resumen_equipo,
    resumen_honorarios,
    filtrar_cortes_kpi_operativos,
    aplicar_meta_resumen,
    resumen_kpi_registros,
    resumen_kpi_honorarios_registros,
)

logger = logging.getLogger(__name__)




def _restar_meses(fecha, cantidad):
    """Devuelve AAAA-MM restando meses a una fecha de corte."""
    if not fecha:
        return ""
    total = fecha.year * 12 + (fecha.month - 1) - cantidad
    anio, mes0 = divmod(total, 12)
    return f"{anio:04d}-{mes0 + 1:02d}"



def _scope_ventas_qs(qs, user):
    """Alcance comercial segÃºn la fuente maestra ESACOM.

    La venta pertenece al vendedor identificado por RUT EVT de ESACOM.
    CODIGO ANDES, CODIGO CE y PROPIETARIO_FINAL de Claro quedan solo como
    datos de apoyo/auditorÃ­a y nunca cambian el dueÃ±o de la venta.
    """
    if user.tiene_alcance_global:
        return qs
    if user.es_supervisor:
        # Supervisor ve exclusivamente ventas de los ejecutivos asignados a su equipo.
        return qs.filter(ejecutivo__supervisor=user, ejecutivo__is_active=True).distinct()
    return qs.filter(ejecutivo=user).distinct()


def _scope_cortes_qs(qs, user):
    """KPI operativo basado exclusivamente en ventas vÃ¡lidas de ESACOM.

    El dueÃ±o se resuelve por RUT EVT (``Venta.ejecutivo``). Una venta ANULADA
    puede seguir existiendo en los archivos histÃ³ricos de Claro para auditorÃ­a,
    pero no forma parte del KPI/cartera operativa del vendedor.
    """
    qs = filtrar_cortes_kpi_operativos(qs)
    if user.tiene_alcance_global:
        # Gerencia conserva el total KPI global aunque exista un pedido cuya
        # propiedad individual estÃ© en conflicto en ESACOM. Ese pedido se
        # muestra como ambigÃ¼edad de atribuciÃ³n, no se borra del total Claro.
        return qs

    # Un pedido ESACOM con dos propietarios incompatibles nunca se adjudica
    # a un vendedor/supervisor por accidente.
    qs = qs.exclude(venta__conflicto_fuente=True)
    if user.es_supervisor:
        # KPI de equipo: propiedad ESACOM por RUT EVT de cada vendedor supervisado.
        return qs.filter(venta__ejecutivo__supervisor=user, venta__ejecutivo__is_active=True).distinct()
    return qs.filter(venta__ejecutivo=user).distinct()


class VentaPagination(PageNumberPagination):
    """
    Igual que la paginaciÃ³n por defecto (50), pero permite pedir mÃ¡s
    con ?page_size=... -- lo usa la pantalla 'Base de Datos' para traer
    todo de una vez al exportar a CSV, sin recorrer pÃ¡gina por pÃ¡gina.
    """

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 1000


class VentaViewSet(RoleScopedMixin, viewsets.ModelViewSet):
    """
    Gerencia: todas las ventas.
    Supervisor: las de su equipo.
    Ejecutivo: solo las propias (de solo lectura).
    """

    queryset = (
        Venta.objects
        .select_related("ejecutivo", "ejecutivo_ce", "promocion", "comuna")
        .prefetch_related("cortes")
        .all()
    )
    serializer_class = VentaSerializer
    permission_classes = [EsSupervisorOModifica]
    pagination_class = VentaPagination
    ejecutivo_lookup = "ejecutivo"
    supervisor_lookup = "ejecutivo__supervisor"
    filterset_fields = ["camada", "estado_instalacion", "tipo_cliente", "origen_venta", "ejecutivo", "comuna", "promocion"]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    # Pantalla 'Base de Datos' (consulta centralizada, como pidiÃ³ Gerencia):
    # buscar por cliente, pedido o ejecutivo sin tener que saber el filtro exacto.
    search_fields = ["rut_cliente", "n_pedido", "nombre_cliente", "nombre_evt", "rut_evt", "rut_ce", "codigo_ce"]
    ordering_fields = ["fecha_venta", "precio_venta", "camada", "rut_cliente"]
    ordering = ["-fecha_venta"]

    def get_queryset(self):
        qs = self.queryset
        if not self.request.user.is_authenticated:
            return qs.none()
        qs = _scope_ventas_qs(qs, self.request.user)

        # Cliente activo por mes = cliente con al menos una boleta PAGADA en
        # la camada mensual consultada. Este filtro no cambia la propiedad de
        # la venta: el alcance sigue viniendo exclusivamente de ESACOM.
        activo_pago_mes = (self.request.query_params.get("activo_pago_mes") or "").strip()
        activo_pago_boleta = (self.request.query_params.get("activo_pago_boleta") or "").strip().upper()
        if activo_pago_mes:
            if len(activo_pago_mes) != 7 or activo_pago_mes[4:5] != "-" or not activo_pago_mes.replace("-", "").isdigit():
                return qs.none()
            filtros_pago = {
                "cortes__mes_ano": activo_pago_mes,
                "cortes__estado_pago": Corte.EstadoPago.PAGADO,
            }
            if activo_pago_boleta:
                if activo_pago_boleta not in Corte.Boleta.values:
                    return qs.none()
                filtros_pago["cortes__boleta"] = activo_pago_boleta
            qs = qs.filter(**filtros_pago).distinct()
        return qs

    @action(detail=True, methods=["get"])
    def detalle(self, request, pk=None):
        """Detalle operativo del cliente: venta + boletas + gestiones.

        Respeta el alcance por rol del propio ViewSet, por lo que un ejecutivo
        nunca puede abrir la cartera de otro usuario y un supervisor solo puede
        consultar clientes de su equipo.
        """
        venta = self.get_object()
        cortes = venta.cortes.select_related("ejecutivo_kpi", "verificado_por").order_by("mes_ano", "boleta")
        gestiones = venta.gestiones.select_related("ejecutivo").order_by("-creado_en")[:100]
        return Response({
            "venta": VentaSerializer(venta).data,
            "cortes": CorteSerializer(cortes, many=True).data,
            "gestiones": GestionSerializer(gestiones, many=True).data,
        })


class CorteViewSet(RoleScopedMixin, viewsets.ModelViewSet):
    """Igual alcance que Venta, pero medido a nivel de cada boleta (B1/B2/B3)."""

    queryset = Corte.objects.select_related("venta", "venta__ejecutivo", "venta__ejecutivo_ce", "ejecutivo_kpi").all()
    serializer_class = CorteSerializer
    permission_classes = [EsSupervisorOModifica]
    ejecutivo_lookup = "venta__ejecutivo"
    supervisor_lookup = "venta__ejecutivo__supervisor"
    filterset_fields = ["boleta", "mes_ano", "estado_pago", "ejecutivo_kpi"]

    def get_queryset(self):
        qs = self.queryset
        if not self.request.user.is_authenticated:
            return qs.none()
        return _scope_cortes_qs(qs, self.request.user)

    @action(detail=True, methods=["post"])
    def verificar(self, request, pk=None):
        """
        POST /api/cortes/{id}/verificar/  { "estado_pago": "PAGADO" }

        Lo usa Cobranza despuÃ©s de comparar la base de Claro contra la
        de ESACOM y confirmar el estado real en el portal de pago o la
        app Andes -- deja registrado quiÃ©n lo verificÃ³ y cuÃ¡ndo, y
        protege ese estado para que el prÃ³ximo import del KPI de Claro
        no lo pise (ver integraciones/management/commands/importar_kpi.py).
        """
        if not request.user.tiene_permiso("cobranza"):
            raise PermissionDenied("No tienes permiso para gestionar Cobranza.")
        corte = self.get_object()
        nuevo_estado = request.data.get("estado_pago")
        if nuevo_estado not in Corte.EstadoPago.values:
            return Response(
                {"detail": f"estado_pago debe ser uno de: {Corte.EstadoPago.values}"}, status=400
            )
        corte.estado_pago = nuevo_estado
        corte.verificado_en_andes = True
        corte.fecha_verificacion_andes = timezone.now()
        corte.verificado_por = request.user
        corte.save(update_fields=["estado_pago", "verificado_en_andes", "fecha_verificacion_andes", "verificado_por"])
        logger.info(
            "cobranza_verificada actor=%s corte=%s pedido=%s estado=%s",
            request.user.rut, corte.pk, corte.venta.n_pedido, nuevo_estado,
        )
        return Response(CorteSerializer(corte).data)


class ApelacionViewSet(RoleScopedMixin, viewsets.ModelViewSet):
    queryset = Apelacion.objects.select_related("corte", "corte__venta", "corte__venta__ejecutivo").all()
    serializer_class = ApelacionSerializer
    permission_classes = [EsSupervisorOModifica]

    def get_permissions(self):
        # Principio de mÃ­nimo privilegio:
        # - lectura/detecciÃ³n/exclusiÃ³n: Supervisor o Gerencia, siempre scoped.
        # - envÃ­o externo a Claro: solo Gerencia/superusuario.
        # - no existe CRUD libre desde la API para fabricar/editar/borrar
        #   apelaciones fuera del motor de negocio.
        if self.action == "enviar":
            return [EsOperacionesOGerencia()]
        return [PuedeApelaciones()]

    def create(self, request, *args, **kwargs):
        return Response({"detail": "Las apelaciones se crean mediante detecciÃ³n automÃ¡tica."}, status=405)

    def update(self, request, *args, **kwargs):
        return Response({"detail": "EdiciÃ³n directa de apelaciones no permitida."}, status=405)

    def partial_update(self, request, *args, **kwargs):
        return Response({"detail": "EdiciÃ³n directa de apelaciones no permitida."}, status=405)

    def destroy(self, request, *args, **kwargs):
        return Response({"detail": "Las apelaciones no se eliminan; se excluyen para preservar trazabilidad."}, status=405)
    ejecutivo_lookup = "corte__venta__ejecutivo"
    supervisor_lookup = "corte__venta__ejecutivo__supervisor"
    filterset_fields = ["motivo", "estado"]

    def get_queryset(self):
        qs = self.queryset
        if not self.request.user.is_authenticated:
            return qs.none()
        cortes = _scope_cortes_qs(Corte.objects.all(), self.request.user).values("pk")
        return qs.filter(corte_id__in=cortes)

    @action(detail=False, methods=["post"])
    def detectar(self, request):
        """
        Corre el motor de detecciÃ³n sobre los Corte visibles para este
        usuario (mismo alcance por rol que el resto del ViewSet) --
        botÃ³n 'DetecciÃ³n automÃ¡tica' de los mockups.
        """
        # Reutilizamos el mismo alcance centralizado que el resto de la API:
        # Operaciones/Gerencia ven global; Supervisor su equipo; Ejecutivo lo propio.
        cortes_visibles = _scope_cortes_qs(Corte.objects.all(), request.user)

        resultado = detectar_apelaciones(cortes_visibles)
        return Response({
            "cortes_revisados": resultado.revisadas,
            "apelaciones_nuevas": resultado.creadas,
            "ya_tenian_apelacion": resultado.ya_existian,
        })

    @action(detail=True, methods=["post"])
    def excluir(self, request, pk=None):
        """ExclusiÃ³n manual -- 'Permite descartar casos puntuales que no correspondan'."""
        apelacion = self.get_object()
        apelacion.estado = Apelacion.Estado.EXCLUIDA
        apelacion.excluida_por = request.user
        apelacion.save(update_fields=["estado", "excluida_por"])
        logger.info("apelacion_excluida actor=%s apelacion=%s", request.user.rut, apelacion.pk)
        return Response(ApelacionSerializer(apelacion).data)

    @action(detail=True, methods=["post"])
    def enviar(self, request, pk=None):
        """
        EnvÃ­a la apelaciÃ³n por correo a Claro (con el Excel adjunto) y
        marca el estado. La tarea automÃ¡tica de Celery (DÃ­a 11) llama
        a la misma funciÃ³n `enviar_apelacion_por_correo`, asÃ­ que el
        botÃ³n manual y el envÃ­o automÃ¡tico nunca pueden desalinearse.
        """
        apelacion = self.get_object()
        try:
            enviar_apelacion_por_correo(apelacion)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        apelacion.estado = Apelacion.Estado.ENVIADA
        apelacion.fecha_envio = timezone.now()
        apelacion.save(update_fields=["estado", "fecha_envio"])
        logger.info("apelacion_enviada actor=%s apelacion=%s", request.user.rut, apelacion.pk)
        return Response(ApelacionSerializer(apelacion).data)


    @action(detail=False, methods=["get"])
    def exportar(self, request):
        """Exporta las apelaciones visibles a Excel para revisiÃ³n/radicaciÃ³n."""
        import openpyxl
        from openpyxl.styles import Font

        qs = self.filter_queryset(self.get_queryset())
        # Reutilizar el alcance por rol de RoleScopedMixin.
        qs = self.get_queryset() if request.user.es_gerencia or request.user.is_superuser else self.filter_queryset(self.get_queryset())
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Apelaciones ESACOM"
        headers = [
            "CONDICION", "PEDIDO", "RUT", "EVT", "CAMADA", "BOLETA", "ESTADO_CLARO",
            "ESTADO_ESACOM", "FECHA_PAGO", "VENCIMIENTO", "LIMITE_8D", "DIAS_DIF",
            "MOTIVO", "OBSERVACION", "BILL_NO", "ESTADO_APELACION",
        ]
        ws.append(headers)
        for cell in ws[1]:
            cell.font = Font(bold=True)
        for a in qs.select_related("corte", "corte__venta", "corte__venta__ejecutivo"):
            c = a.corte
            ws.append([
                a.get_motivo_display(), c.venta.n_pedido, c.venta.rut_cliente,
                c.venta.nombre_evt or (c.venta.ejecutivo.nombre if c.venta.ejecutivo else ""),
                c.mes_ano, c.boleta, c.estado_claro, c.estado_pago,
                c.fecha_pago.isoformat() if c.fecha_pago else "",
                c.fecha_vencimiento.isoformat() if c.fecha_vencimiento else "",
                c.fecha_limite_medicion.isoformat() if c.fecha_limite_medicion else "",
                c.dias_diferencia, a.get_motivo_display(), a.observacion, a.bill_no or c.bill_no,
                a.get_estado_display(),
            ])
        response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = 'attachment; filename="APELACIONES_ESACOM.xlsx"'
        wb.save(response)
        return response


class GestionViewSet(RoleScopedMixin, viewsets.ModelViewSet):
    """
    Registro de llamadas/WhatsApp del Portal Ejecutivo. Un Ejecutivo
    crea sus propias gestiones, Ãºnicamente sobre ventas de su propia
    cartera; Supervisor y Gerencia las ven (no las crean) para
    trazabilidad del equipo.
    """

    queryset = Gestion.objects.select_related("venta", "ejecutivo").all()
    serializer_class = GestionSerializer
    ejecutivo_lookup = "ejecutivo"
    supervisor_lookup = "ejecutivo__supervisor"
    filterset_fields = ["venta", "tipo"]

    def get_permissions(self):
        if self.request.method not in ("GET", "HEAD", "OPTIONS"):
            # Solo un Ejecutivo raso registra gestiones -- Supervisor y
            # Gerencia solo consultan, para no mezclar "quiÃ©n gestionÃ³"
            # con "quiÃ©n supervisa".
            return [EsEjecutivo()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        venta = serializer.validated_data["venta"]
        propietario_id = venta.ejecutivo_id
        if propietario_id != self.request.user.id:
            raise PermissionDenied("No puedes registrar una gestiÃ³n sobre un cliente que no pertenece a tu cartera.")
        serializer.save(ejecutivo=self.request.user)


def _cortes_visibles(user, carga_kpi=None):
    """Alcance KPI derivado de la venta ESACOM y del snapshot activo.

    ``Corte`` conserva el Ãºltimo estado conocido por venta/camada/boleta. Una
    fila puede desaparecer de un snapshot posterior de Claro; por eso el
    dashboard vigente debe filtrar por ``carga_kpi`` y nunca mezclar cortes
    residuales de cargas antiguas. El dueÃ±o comercial sigue viniendo de
    ``Venta.ejecutivo`` (RUT EVT ESACOM).
    """
    cortes = Corte.objects.select_related(
        "venta", "venta__ejecutivo", "venta__ejecutivo_ce", "ejecutivo_kpi", "carga_kpi"
    )
    if carga_kpi is not None:
        cortes = cortes.filter(carga_kpi=carga_kpi)
    return _scope_cortes_qs(cortes, user)



def _ultima_carga_kpi_activa():
    """Ãšltimo AVANCE Fijo por fecha del reporte Claro, no por momento de carga CRM."""
    from integraciones.models import CargaExcel

    qs = CargaExcel.objects.filter(
        tipo_base=CargaExcel.TipoBase.REPORTE_KPI
    ).exclude(
        formato_kpi__in=[CargaExcel.FormatoKPI.AVANCE_MOVIL, CargaExcel.FormatoKPI.CIERRE_MOVIL]
    )
    avance = _mas_reciente(qs.filter(estado_reporte=CargaExcel.EstadoReporte.AVANCE))
    return avance or _mas_reciente(qs)


def _focos_carga(carga) -> dict[str, str]:
    if not carga:
        return {"B1": "", "B2": "", "B3": ""}
    return {
        "B1": carga.foco_b1 or (_restar_meses(carga.fecha_corte, 1) if carga.fecha_corte else ""),
        "B2": carga.foco_b2 or (_restar_meses(carga.fecha_corte, 2) if carga.fecha_corte else ""),
        "B3": carga.foco_b3 or (_restar_meses(carga.fecha_corte, 3) if carga.fecha_corte else ""),
    }


def _metas_reporte_carga(carga) -> dict[str, float | None]:
    if not carga:
        return {"B1": None, "B2": None, "B3": None}
    return {
        "B1": float(carga.meta_b1) if carga.meta_b1 is not None else None,
        "B2": float(carga.meta_b2) if carga.meta_b2 is not None else None,
        "B3": float(carga.meta_b3) if carga.meta_b3 is not None else None,
    }


def _metas_efectivas_carga(carga, focos=None) -> dict[str, float | None]:
    focos = focos or _focos_carga(carga)
    metas = metas_calidad_para_focos(focos, fallback=_metas_reporte_carga(carga))
    return {boleta: serializar_meta(valor) for boleta, valor in metas.items()}


def _resumen_ventas_mes(ventas_scope, mes: str) -> dict:
    qs = ventas_scope.filter(camada=mes)
    total = qs.count()
    instaladas = qs.filter(estado_instalacion=Venta.EstadoInstalacion.INSTALADO).count()
    pendiente_instalacion = qs.filter(estado_instalacion=Venta.EstadoInstalacion.PENDIENTE_INSTALACION).count()
    pendiente_comercial = qs.filter(estado_instalacion=Venta.EstadoInstalacion.PENDIENTE_COMERCIAL).count()
    anuladas = qs.filter(estado_instalacion=Venta.EstadoInstalacion.ANULADO).count()
    gestionables = max(total - anuladas, 0)
    return {
        "mes": mes,
        "total": total,
        "gestionables": gestionables,
        "instaladas": instaladas,
        "pendiente_instalacion": pendiente_instalacion,
        "pendiente_comercial": pendiente_comercial,
        "anuladas": anuladas,
        "clientes": qs.values("rut_cliente").distinct().count(),
        "avance_instalacion_pct": round((instaladas / gestionables) * 100, 1) if gestionables else 0.0,
    }


def _mes_anterior(mes: str) -> str:
    anio, numero = [int(x) for x in mes.split("-")]
    numero -= 1
    if numero == 0:
        anio -= 1
        numero = 12
    return f"{anio:04d}-{numero:02d}"



def _scope_registros_kpi_qs(qs, user):
    """Aplica el alcance usando el snapshot ESACOM sin recorrer filas en Python.

    R2.17.1: el primer R2.17 filtraba cada queryset registro por registro, lo
    que obligaba a materializar miles de KPIRegistro y sus relaciones varias
    veces por request de Gerencia/Supervisor. Con ~80 mil snapshots SQLite
    podÃ­a tardar decenas de segundos.

    La ruta normal ahora filtra directamente en SQL sobre ``snapshot_esacom``.
    Solo si existen filas legacy sin snapshot se materializa ese subconjunto
    pequeÃ±o con la lÃ³gica anterior.
    """
    perfil = Ejecutivo.TipoKPI.REGULAR
    if (
        getattr(user, "cargo", None) == Ejecutivo.Cargo.EJECUTIVO
        and getattr(user, "tipo_kpi", Ejecutivo.TipoKPI.REGULAR) == Ejecutivo.TipoKPI.HONORARIOS
        and not getattr(user, "es_supervisor", False)
        and not getattr(user, "es_gerencia", False)
    ):
        perfil = Ejecutivo.TipoKPI.HONORARIOS

    if not hasattr(qs, "filter"):
        return qs

    snapshot_qs = qs.filter(
        cruce_ok=True,
        snapshot_esacom__isnull=False,
        snapshot_esacom__estado_instalacion=Venta.EstadoInstalacion.INSTALADO,
        snapshot_esacom__tipo_kpi=perfil,
        snapshot_esacom__cargo=Ejecutivo.Cargo.EJECUTIVO,
        snapshot_esacom__ejecutivo_activo=True,
    )

    if not user.tiene_alcance_global:
        snapshot_qs = snapshot_qs.filter(snapshot_esacom__conflicto_fuente=False)
        if user.es_supervisor:
            snapshot_qs = snapshot_qs.filter(snapshot_esacom__supervisor_id=user.id)
        else:
            snapshot_qs = snapshot_qs.filter(snapshot_esacom__ejecutivo_id=user.id)

    # Fast path: despuÃ©s de sembrar R2.17 todas las filas usan snapshot y el
    # caller recibe un QuerySet todavÃ­a perezoso, ya reducido por SQLite.
    legacy_qs = qs.filter(snapshot_esacom__isnull=True)
    if not legacy_qs.exists():
        return snapshot_qs

    # Compatibilidad Ãºnicamente para cargas antiguas aÃºn no sembradas.
    legacy_qs = legacy_qs.filter(
        cruce_ok=True,
        venta__estado_instalacion=Venta.EstadoInstalacion.INSTALADO,
        venta__ejecutivo__tipo_kpi=perfil,
        venta__ejecutivo__cargo=Ejecutivo.Cargo.EJECUTIVO,
        venta__ejecutivo__is_active=True,
    )
    if not user.tiene_alcance_global:
        legacy_qs = legacy_qs.filter(venta__conflicto_fuente=False)
        if user.es_supervisor:
            legacy_qs = legacy_qs.filter(venta__ejecutivo__supervisor_id=user.id)
        else:
            legacy_qs = legacy_qs.filter(venta__ejecutivo_id=user.id)

    return list(snapshot_qs) + list(legacy_qs.select_related("venta", "venta__promocion"))


def _resumen_cierre_fijo_snapshot_usuario(user, carga, camada: str, boleta: str):
    """Resume el CIERRE_FIJO desde su poblaciÃ³n congelada, nunca desde Venta actual."""
    from integraciones.models import KPICierreFijoFila

    qs = KPICierreFijoFila.objects.filter(carga=carga, camada=camada, boleta=boleta)
    if not user.tiene_alcance_global:
        if user.es_supervisor:
            qs = qs.filter(supervisor_fuente__iexact=user.nombre)
        else:
            rut = str(getattr(user, "rut", "") or "").replace(".", "").strip().upper()
            qs = qs.filter(rut_evt__iexact=rut)
    # Portal Regular nunca mezcla Honorarios.
    qs = qs.filter(models.Q(tipo_kpi=Ejecutivo.TipoKPI.REGULAR) | models.Q(tipo_kpi=""))
    filas = list(qs)
    if not filas:
        return None

    categorias = {
        "PAGO": "pagadas",
        "PENDIENTE": "pendientes",
        "NO_PAGO": "no_pago",
        "FUERA_PLAZO": "fuera_plazo",
        "SIN_BOLETA": "sin_boleta",
        "N_D": "fuera_medicion",
    }
    datos = {"pagadas": 0, "pendientes": 0, "no_pago": 0, "fuera_plazo": 0, "sin_boleta": 0, "fuera_medicion": 0}
    for fila in filas:
        bucket = categorias.get(fila.categoria, "fuera_medicion")
        datos[bucket] += int(fila.rgu or 0)

    total = datos["pagadas"] + datos["pendientes"] + datos["no_pago"] + datos["fuera_plazo"]
    meta = meta_calidad_para(boleta=boleta, camada=camada, fallback=getattr(carga, f"meta_{boleta.lower()}", None))
    meta_pct = Decimal(str(serializar_meta(meta) or 0))
    pct_exacto = (Decimal(datos["pagadas"]) / Decimal(total) * 100) if total else Decimal("0")
    pct = float(pct_exacto.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    if total and meta_pct:
        objetivo = (Decimal(total) * meta_pct / Decimal("100")).to_integral_value(rounding=ROUND_CEILING)
        faltan = max(0, int(objetivo) - datos["pagadas"])
    else:
        faltan = 0
    return {
        **datos,
        "total": total,
        "total_con_sin_boleta": total + datos["sin_boleta"],
        "unidad": "RGU",
        "meta_pct": float(meta_pct),
        "pct_cumplimiento": pct,
        "pct_proyectado": pct,
        "cumplimiento_meta_pct": float((pct_exacto / meta_pct * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)) if meta_pct else 0.0,
        "faltan_para_meta": faltan,
        "gestion": {"pago": datos["pagadas"], "vencido_mas_8": 0, "vencido_0_8": 0, "gestionar_0_7": 0, "gestionar_8_mas": 0, "otros": 0},
        "semaforo": "verde" if meta_pct and pct_exacto >= meta_pct else ("amarillo" if meta_pct and pct_exacto >= meta_pct - 10 else "rojo"),
        "boleta": boleta,
        "mes_ano": camada,
        "tiene_datos": bool(total or datos["sin_boleta"] or datos["fuera_medicion"]),
        "snapshot_id": carga.id,
        "fecha_reporte": (fecha_reporte_desde_nombre(carga.archivo_nombre).isoformat() if fecha_reporte_desde_nombre(carga.archivo_nombre) else None),
        "fecha_corte": carga.fecha_corte.isoformat() if carga.fecha_corte else None,
        "dia_reporte": carga.dia_reporte,
        "estado_medicion": carga.estado_reporte,
        "cerrado": True,
        "fuente_formato": getattr(carga, "formato_kpi", "CIERRE_FIJO"),
        "perfil_kpi": "REGULAR",
        "meta_definida": bool(meta_pct),
        "valor_informado_claro": _valor_informado_claro_par(carga, boleta, camada),
        "meta_reporte_claro": float(getattr(carga, f"meta_{boleta.lower()}") or 0) if getattr(carga, f"meta_{boleta.lower()}") is not None else None,
        "kpi_anterior_pct": None,
        "tendencia_pp": None,
        "reporte_anterior": None,
    }

def _clave_temporal_carga(carga):
    """Prioridad temporal: fecha reporte Claro > fecha corte > carga CRM."""
    import datetime

    fecha_reporte = fecha_reporte_desde_nombre(getattr(carga, "archivo_nombre", ""))
    fecha_corte = getattr(carga, "fecha_corte", None)
    creado = getattr(carga, "creado_en", None)
    if creado is not None:
        creado_clave = creado.timestamp()
    else:
        creado_clave = 0
    return (
        fecha_reporte or fecha_corte or datetime.date.min,
        fecha_corte or datetime.date.min,
        creado_clave,
        int(getattr(carga, "id", 0) or 0),
    )


def _mas_reciente(qs):
    cargas = list(qs)
    return max(cargas, key=_clave_temporal_carga) if cargas else None


def _mas_antigua(qs):
    cargas = list(qs)
    return min(cargas, key=_clave_temporal_carga) if cargas else None


def _cargas_kpi_para_par(boleta: str, camada: str):
    """Snapshots Fijo que contienen una camada/boleta sin JOIN DISTINCT masivo.

    R2.17.2: primero identifica los ``carga_id`` presentes en KPIRegistro y
    luego filtra CargaExcel por PK. Evita repetir el JOIN + DISTINCT sobre las
    ~80 mil filas KPI cada vez que Gerencia resuelve una camada.
    """
    from django.db.models import Subquery
    from integraciones.models import CargaExcel, KPIRegistro

    campo = {"B1": "foco_b1", "B2": "foco_b2", "B3": "foco_b3"}.get(boleta)
    if not campo or not camada:
        return CargaExcel.objects.none()

    ids_con_par = KPIRegistro.objects.filter(
        camada=camada, boleta=boleta
    ).values("carga_id")
    return CargaExcel.objects.filter(
        tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
    ).exclude(
        formato_kpi__in=[CargaExcel.FormatoKPI.AVANCE_MOVIL, CargaExcel.FormatoKPI.CIERRE_MOVIL]
    ).filter(
        models.Q(**{campo: camada}) | models.Q(id__in=Subquery(ids_con_par))
    )


def _carga_efectiva_par(boleta: str, camada: str):
    """CIERRE_FIJO oficial congela; sin cierre usa el AVANCE Fijo mÃ¡s reciente."""
    from integraciones.models import CargaExcel

    qs = _cargas_kpi_para_par(boleta, camada)
    cierre = _mas_antigua(qs.filter(
        estado_reporte=CargaExcel.EstadoReporte.CIERRE,
        formato_kpi=CargaExcel.FormatoKPI.CIERRE_FIJO,
    ))
    if cierre:
        return cierre
    return _mas_reciente(qs.filter(
        estado_reporte=CargaExcel.EstadoReporte.AVANCE,
        formato_kpi=CargaExcel.FormatoKPI.DETALLADO,
    ))


def _valor_informado_claro_par(carga, boleta: str, camada: str):
    """La referencia del correo solo aplica al foco exacto CAMADA+BOLETA.

    Evita mostrar en Septiembre el 97,81% que el RESUMEN informÃ³ para Agosto.
    """
    if not carga or not camada:
        return None
    campo_foco = {"B1": "foco_b1", "B2": "foco_b2", "B3": "foco_b3"}.get(boleta)
    campo_valor = {"B1": "avance_b1", "B2": "avance_b2", "B3": "avance_b3"}.get(boleta)
    if not campo_foco or not campo_valor:
        return None
    if str(getattr(carga, campo_foco, "") or "").strip() != camada:
        return None
    valor = getattr(carga, campo_valor, None)
    return float(valor) if valor is not None else None


def _resumen_par_snapshot_usuario(user, boleta: str, camada: str, carga=None) -> dict | None:
    """KPI de un vendedor/equipo en un snapshot concreto, preservando avances y cierres."""
    from integraciones.models import KPIRegistro, CargaExcel, KPICierreResumen

    carga = carga or _carga_efectiva_par(boleta, camada)
    if not carga:
        return None

    formato_carga = getattr(carga, "formato_kpi", CargaExcel.FormatoKPI.DETALLADO)
    if formato_carga in {CargaExcel.FormatoKPI.AVANCE_MOVIL, CargaExcel.FormatoKPI.CIERRE_MOVIL}:
        qs = KPICierreResumen.objects.filter(carga=carga, camada=camada, boleta=boleta)
        if user.tiene_alcance_global:
            global_row = qs.filter(rut_vendedor_fuente="GLOBAL").first()
            if global_row:
                datos = {
                    "pagadas": global_row.pagadas, "pendientes": global_row.pendientes,
                    "no_pago": global_row.no_pago, "fuera_plazo": global_row.fuera_plazo,
                    "sin_boleta": global_row.sin_boleta, "total": global_row.total_medible,
                }
            else:
                datos = qs.exclude(rut_vendedor_fuente="GLOBAL").aggregate(
                    pagadas=Sum("pagadas"), pendientes=Sum("pendientes"), no_pago=Sum("no_pago"),
                    fuera_plazo=Sum("fuera_plazo"), sin_boleta=Sum("sin_boleta"), total=Sum("total_medible"),
                )
        else:
            qs = qs.exclude(rut_vendedor_fuente="GLOBAL")
            if user.es_supervisor:
                qs = qs.filter(ejecutivo__supervisor=user, ejecutivo__is_active=True)
            else:
                qs = qs.filter(ejecutivo=user)
            datos = qs.aggregate(
                pagadas=Sum("pagadas"), pendientes=Sum("pendientes"), no_pago=Sum("no_pago"),
                fuera_plazo=Sum("fuera_plazo"), sin_boleta=Sum("sin_boleta"), total=Sum("total_medible"),
            )
        pagadas = int(datos.get("pagadas") or 0)
        pendientes = int(datos.get("pendientes") or 0)
        no_pago = int(datos.get("no_pago") or 0)
        fuera_plazo = int(datos.get("fuera_plazo") or 0)
        sin_boleta = int(datos.get("sin_boleta") or 0)
        total = int(datos.get("total") or 0)
        pct_exacto = (Decimal(pagadas) / Decimal(total) * 100) if total else Decimal("0")
        pct = float(pct_exacto.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        # MÃ³vil usa su propia meta informada en el reporte (ej. 87/84/78).
        # Nunca reutiliza automÃ¡ticamente las metas Fijo 85/83/78.
        meta_reporte = getattr(carga, f"meta_{boleta.lower()}")
        meta = Decimal(str(meta_reporte or 0))
        cumplimiento = float((pct_exacto / meta * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)) if meta else 0.0
        faltan = 0
        if total and meta:
            objetivo = (Decimal(total) * meta / Decimal("100")).to_integral_value(rounding=ROUND_CEILING)
            faltan = max(0, int(objetivo) - pagadas)
        if not total or not meta:
            semaforo = "sin_datos"
        elif pct_exacto >= meta:
            semaforo = "verde"
        elif pct_exacto >= meta - 10:
            semaforo = "amarillo"
        else:
            semaforo = "rojo"
        return {
            "pagadas": pagadas, "pendientes": pendientes, "no_pago": no_pago,
            "fuera_plazo": fuera_plazo, "sin_boleta": sin_boleta, "total": total,
            "total_con_sin_boleta": total + sin_boleta, "fuera_medicion": 0,
            "unidad": "RGU", "boletas_total": 0, "boletas_fuera_medicion": 0,
            "meta_pct": float(meta), "pct_cumplimiento": pct, "pct_proyectado": pct,
            "cumplimiento_meta_pct": cumplimiento, "faltan_para_meta": faltan,
            "gestion": {
                "pago": pagadas, "vencido_mas_8": 0, "vencido_0_8": 0,
                "gestionar_0_7": 0, "gestionar_8_mas": 0, "otros": 0,
            },
            "semaforo": semaforo, "boleta": boleta, "mes_ano": camada,
            "tiene_datos": bool(total or sin_boleta), "snapshot_id": carga.id,
            "fecha_reporte": (fecha_reporte_desde_nombre(carga.archivo_nombre).isoformat() if fecha_reporte_desde_nombre(carga.archivo_nombre) else None),
            "fecha_corte": carga.fecha_corte.isoformat() if carga.fecha_corte else None,
            "dia_reporte": carga.dia_reporte, "estado_medicion": carga.estado_reporte,
            "cerrado": (carga.estado_reporte == CargaExcel.EstadoReporte.CIERRE),
            "fuente_formato": formato_carga,
            "valor_informado_claro": _valor_informado_claro_par(carga, boleta, camada),
            "meta_reporte_claro": float(meta_reporte) if meta_reporte is not None else None,
            "kpi_anterior_pct": None, "tendencia_pp": None, "reporte_anterior": None,
        }

    registros = _scope_registros_kpi_qs(
        KPIRegistro.objects.filter(carga=carga, camada=camada, boleta=boleta), user
    )
    es_honorarios = (
        getattr(user, "cargo", None) == Ejecutivo.Cargo.EJECUTIVO
        and getattr(user, "tipo_kpi", Ejecutivo.TipoKPI.REGULAR) == Ejecutivo.TipoKPI.HONORARIOS
        and not getattr(user, "es_supervisor", False)
        and not getattr(user, "es_gerencia", False)
    )
    meta = None if es_honorarios else meta_calidad_para(boleta=boleta, camada=camada, fallback=None)
    resumen = (
        resumen_kpi_honorarios_registros(registros)
        if es_honorarios
        else resumen_kpi_registros(registros, meta_pct=meta or 0)
    )
    resumen.update({
        "boleta": boleta,
        "mes_ano": camada,
        "tiene_datos": bool(resumen.get("total") or resumen.get("sin_boleta") or resumen.get("fuera_medicion")),
        "snapshot_id": carga.id,
        "fecha_reporte": (fecha_reporte_desde_nombre(carga.archivo_nombre).isoformat() if fecha_reporte_desde_nombre(carga.archivo_nombre) else None),
        "fecha_corte": carga.fecha_corte.isoformat() if carga.fecha_corte else None,
        "dia_reporte": carga.dia_reporte,
        "estado_medicion": carga.estado_reporte or CargaExcel.EstadoReporte.AVANCE,
        "cerrado": (carga.estado_reporte == CargaExcel.EstadoReporte.CIERRE),
        "fuente_formato": getattr(carga, "formato_kpi", CargaExcel.FormatoKPI.DETALLADO),
        "perfil_kpi": "HONORARIOS" if es_honorarios else "REGULAR",
        "meta_definida": False if es_honorarios else bool(meta),
        "valor_informado_claro": _valor_informado_claro_par(carga, boleta, camada),
        "meta_reporte_claro": float(getattr(carga, f"meta_{boleta.lower()}") or 0) if getattr(carga, f"meta_{boleta.lower()}") is not None else None,
    })

    # Tendencia del KPI individual respecto del snapshot inmediatamente anterior
    # del mismo par. No se usa el porcentaje global del correo para medir al vendedor.
    candidatos_anteriores = [
        c for c in _cargas_kpi_para_par(boleta, camada)
        if c.id != carga.id and _clave_temporal_carga(c) < _clave_temporal_carga(carga)
    ]
    anterior = max(candidatos_anteriores, key=_clave_temporal_carga) if candidatos_anteriores else None
    if anterior:
        regs_ant = _scope_registros_kpi_qs(
            KPIRegistro.objects.filter(carga=anterior, camada=camada, boleta=boleta), user
        )
        ant = (
            resumen_kpi_honorarios_registros(regs_ant)
            if es_honorarios
            else resumen_kpi_registros(regs_ant, meta_pct=meta or 0)
        )
        resumen["kpi_anterior_pct"] = ant.get("pct_cumplimiento")
        resumen["tendencia_pp"] = round(
            float(resumen.get("pct_cumplimiento") or 0) - float(ant.get("pct_cumplimiento") or 0), 2
        )
        resumen["reporte_anterior"] = {
            "id": anterior.id,
            "fecha_corte": anterior.fecha_corte.isoformat() if anterior.fecha_corte else None,
            "dia_reporte": anterior.dia_reporte,
            "estado_medicion": anterior.estado_reporte,
        }
    else:
        resumen["kpi_anterior_pct"] = None
        resumen["tendencia_pp"] = None
        resumen["reporte_anterior"] = None
    return resumen


def _boleta_en_carga_para_mes(carga, camada: str) -> str | None:
    """Devuelve la boleta con la que una carga midio una camada mensual."""
    if not carga or not camada:
        return None
    for boleta, campo in (("B1", "foco_b1"), ("B2", "foco_b2"), ("B3", "foco_b3")):
        if (getattr(carga, campo, "") or "") == camada:
            return boleta
    return None


def _cierre_oficial_mes(camada: str):
    """Primer CIERRE_FIJO oficial recibido para el mes; nunca se inventa cierre."""
    from integraciones.models import CargaExcel

    if not camada:
        return None
    qs = CargaExcel.objects.filter(
        tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
        estado_reporte=CargaExcel.EstadoReporte.CIERRE,
        formato_kpi=CargaExcel.FormatoKPI.CIERRE_FIJO,
    ).filter(
        models.Q(foco_b1=camada) | models.Q(foco_b2=camada) | models.Q(foco_b3=camada)
        | models.Q(registros_kpi__camada=camada)
    ).distinct()
    return _mas_antigua(qs)


def _ultimo_avance_b1_mes(camada: str):
    """Ãšltimo AVANCE Fijo que contiene B1 de la camada, aunque no sea foco_b1."""
    from integraciones.models import CargaExcel

    if not camada:
        return None
    return _mas_reciente(
        _cargas_kpi_para_par("B1", camada).filter(
            estado_reporte=CargaExcel.EstadoReporte.AVANCE,
            formato_kpi=CargaExcel.FormatoKPI.DETALLADO,
        )
    )


def _camadas_b1_abiertas() -> list[str]:
    """Camadas B1 con AVANCE real y sin CIERRE_FIJO oficial.

    R2.17.2 evita recorrer todo KPIRegistro unido a CargaExcel y evita llamar
    ``_ultimo_avance_b1_mes``/``_cierre_oficial_mes`` una vez por candidato.
    Primero obtiene los IDs de cargas AVANCE/CIERRE (tablas pequeÃ±as) y luego
    resuelve las camadas con consultas indexables por ``carga_id``.
    """
    from integraciones.models import CargaExcel, KPIRegistro

    avances = CargaExcel.objects.filter(
        tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
        estado_reporte=CargaExcel.EstadoReporte.AVANCE,
        formato_kpi=CargaExcel.FormatoKPI.DETALLADO,
    )
    avance_ids = list(avances.values_list("id", flat=True))

    candidatos = set()
    if avance_ids:
        candidatos.update(
            KPIRegistro.objects.filter(carga_id__in=avance_ids, boleta="B1")
            .filter(
                models.Q(marca_mes_kpi=1)
                | models.Q(marca_mes_kpi__isnull=True, es_medible=True)
            )
            .exclude(camada="")
            .values_list("camada", flat=True)
            .distinct()
        )
    candidatos.update(
        avances.exclude(foco_b1="").values_list("foco_b1", flat=True).distinct()
    )
    candidatos.discard("")
    if not candidatos:
        return []

    cierres = CargaExcel.objects.filter(
        tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
        estado_reporte=CargaExcel.EstadoReporte.CIERRE,
        formato_kpi=CargaExcel.FormatoKPI.CIERRE_FIJO,
    )
    cierre_ids = list(cierres.values_list("id", flat=True))
    cerradas = set()
    if cierre_ids:
        cerradas.update(
            KPIRegistro.objects.filter(carga_id__in=cierre_ids, camada__in=candidatos)
            .exclude(camada="")
            .values_list("camada", flat=True)
            .distinct()
        )
    for campo in ("foco_b1", "foco_b2", "foco_b3"):
        cerradas.update(
            cierres.filter(**{f"{campo}__in": candidatos})
            .exclude(**{campo: ""})
            .values_list(campo, flat=True)
        )

    return sorted(candidatos - cerradas, reverse=True)


def _resumen_mes_kpi_usuario(user, camada: str, *, en_curso: bool = False) -> dict | None:
    """Una tarjeta mensual usa B1 mientras estÃ¡ abierta y CIERRE oficial al cerrar.

    R2.14 elimina el cierre operativo inventado. Que una camada deje de ser
    ``foco_b1`` no la congela: puede coexistir con otra camada B1 abierta.
    """
    if not camada:
        return None

    cierre = _cierre_oficial_mes(camada)
    if en_curso:
        if cierre is not None:
            return None
        carga = _ultimo_avance_b1_mes(camada)
        boleta = "B1"
        cierre_oficial = False
        if not carga:
            return None
    else:
        carga = cierre
        cierre_oficial = bool(carga)
        if not carga:
            return None
        boleta = _boleta_en_carga_para_mes(carga, camada)
        if not boleta:
            # Si el RESUMEN cambiÃ³ de estructura, intenta detectar el par real
            # importado en BASE sin convertir un AVANCE en cierre.
            for candidato in ("B1", "B2", "B3"):
                if _cargas_kpi_para_par(candidato, camada).filter(id=carga.id).exists():
                    boleta = candidato
                    break
        if not boleta:
            return None

    if cierre_oficial:
        # Un CIERRE_FIJO se lee desde KPICierreFijoFila, que conserva la
        # poblaciÃ³n ESACOM histÃ³rica aunque la matriz cambie despuÃ©s.
        resumen = _resumen_cierre_fijo_snapshot_usuario(user, carga, camada, boleta)
    else:
        resumen = _resumen_par_snapshot_usuario(user, boleta, camada, carga=carga)

    # Compatibilidad para cierres antiguos sin snapshot de filas. Nunca se usa
    # este fallback cuando KPICierreFijoFila sÃ­ existe.
    if (not resumen or not resumen.get("tiene_datos")) and cierre_oficial:
        respaldo = _ultimo_avance_b1_mes(camada)
        if respaldo:
            resumen = _resumen_par_snapshot_usuario(user, "B1", camada, carga=respaldo)
            boleta = "B1"
    if not resumen:
        return None

    resumen["estado_mes"] = "CERRADO" if cierre_oficial else "EN_CURSO"
    resumen["cerrado_mes"] = bool(cierre_oficial)
    resumen["cierre_oficial"] = bool(cierre_oficial)
    resumen["origen_cierre_mes"] = "OFICIAL" if cierre_oficial else "AVANCE_B1"
    return resumen


def _cortes_vigentes_snapshots_usuario(user, focos: dict[str, str] | None = None) -> list[dict]:
    """Todas las camadas B1 abiertas; Septiembre y Agosto pueden coexistir."""
    resultado = []
    for camada in _camadas_b1_abiertas():
        resumen = _resumen_mes_kpi_usuario(user, camada, en_curso=True)
        if resumen is not None:
            resultado.append(resumen)
    return resultado


def _historico_kpi_usuario_snapshots(user, focos_activos: dict[str, str] | None = None) -> list[dict]:
    """Histórico mensual compuesto exclusivamente por CIERRE_FIJO oficial."""
    from integraciones.models import CargaExcel

    MES_INICIO_HISTORICO = "2026-07"

    meses = set()

    for b1, b2, b3 in CargaExcel.objects.filter(
        tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
        estado_reporte=CargaExcel.EstadoReporte.CIERRE,
        formato_kpi=CargaExcel.FormatoKPI.CIERRE_FIJO,
    ).values_list("foco_b1", "foco_b2", "foco_b3"):
        meses.update(
            m
            for m in (b1, b2, b3)
            if m and m >= MES_INICIO_HISTORICO
        )

    resultado = []

    for camada in sorted(meses, reverse=True):
        resumen = _resumen_mes_kpi_usuario(
            user,
            camada,
            en_curso=False,
        )

        if resumen and resumen.get("tiene_datos"):
            resultado.append(resumen)

    return resultado


def _historico_kpi_usuario(user, focos_activos: dict[str, str]) -> list[dict]:
    """Boletas anteriores a la ventana activa, sin fallback ni reescritura.

    ``Corte`` conserva el estado mÃ¡s reciente de cada venta/camada/boleta. El
    histÃ³rico presentado al Ejecutivo se limita por su propiedad ESACOM y
    solo incluye camadas anteriores a la ventana mensual B1/B2/B3 vigente.
    """
    qs = _scope_cortes_qs(
        Corte.objects.select_related("venta", "venta__ejecutivo", "venta__promocion", "carga_kpi"),
        user,
    )
    if getattr(user, "cargo", "") == Ejecutivo.Cargo.EJECUTIVO:
        if getattr(user, "tipo_kpi", Ejecutivo.TipoKPI.REGULAR) != Ejecutivo.TipoKPI.REGULAR:
            return []
        qs = qs.filter(venta__ejecutivo=user)

    activos = {(boleta, mes) for boleta, mes in focos_activos.items() if mes}
    meses_activos = [mes for mes in focos_activos.values() if mes]
    # La ventana KPI se desplaza por mes. El HistÃ³rico solo puede contener
    # camadas anteriores a la mÃ¡s antigua de las tres boletas vigentes.
    # Ej.: B1 Jul / B2 Jun / B3 May => HistÃ³rico Abr hacia atrÃ¡s.
    limite_historico = min(meses_activos) if meses_activos else ""

    resultado = []
    for resumen in resumen_por_corte(qs):
        mes_resumen = resumen.get("mes_ano", "")
        par = (resumen.get("boleta"), mes_resumen)
        if par in activos:
            continue
        if limite_historico and mes_resumen >= limite_historico:
            continue
        meta = meta_calidad_para(
            boleta=resumen.get("boleta", ""),
            camada=resumen.get("mes_ano", ""),
            fallback=resumen.get("meta_pct"),
        )
        aplicar_meta_resumen(resumen, meta)
        resumen["tiene_datos"] = bool(
            resumen.get("total") or resumen.get("sin_boleta") or resumen.get("fuera_medicion")
        )
        resultado.append(resumen)
    orden_boleta = {"B1": 1, "B2": 2, "B3": 3}
    resultado.sort(key=lambda x: (x.get("mes_ano", ""), orden_boleta.get(x.get("boleta"), 0)), reverse=True)
    return resultado


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_kpi(request):
    """Dashboard KPI con fuente ESACOM separada de mediciÃ³n Claro.

    Para Ejecutivo no se exponen controles tÃ©cnicos de sincronizaciÃ³n. La
    respuesta entrega las tres boletas vigentes del Ãºltimo snapshot, metas
    ESACOM resueltas por vigencia, producciÃ³n del mes calendario y un histÃ³rico
    de boletas anteriores para consulta.
    """
    from integraciones.models import CargaExcel

    ultima = _ultima_carga_kpi_activa()
    focos = _focos_carga(ultima)
    metas_reporte = _metas_reporte_carga(ultima)
    metas = _metas_efectivas_carga(ultima, focos)

    cortes = _cortes_visibles(request.user, carga_kpi=ultima)
    cortes_regulares = cortes.filter(
        venta__ejecutivo__tipo_kpi=Ejecutivo.TipoKPI.REGULAR,
        venta__ejecutivo__cargo=Ejecutivo.Cargo.EJECUTIVO,
        venta__ejecutivo__is_active=True,
    )

    ultima_carga = None
    if ultima:
        ultima_carga = {
            "id": ultima.id,
            "archivo_nombre": ultima.archivo_nombre,
            "fecha_reporte": (fecha_reporte_desde_nombre(ultima.archivo_nombre).isoformat() if fecha_reporte_desde_nombre(ultima.archivo_nombre) else None),
            "fecha_corte": ultima.fecha_corte.isoformat() if ultima.fecha_corte else None,
            "dia_reporte": ultima.dia_reporte,
            "estado_reporte": ultima.estado_reporte,
            "creado_en": ultima.creado_en.isoformat(),
            "avance_b1": float(ultima.avance_b1) if ultima.avance_b1 is not None else None,
            "avance_b2": float(ultima.avance_b2) if ultima.avance_b2 is not None else None,
            "avance_b3": float(ultima.avance_b3) if ultima.avance_b3 is not None else None,
            "meta_b1": metas["B1"],
            "meta_b2": metas["B2"],
            "meta_b3": metas["B3"],
            "meta_reporte_b1": metas_reporte["B1"],
            "meta_reporte_b2": metas_reporte["B2"],
            "meta_reporte_b3": metas_reporte["B3"],
            "foco_b1": focos["B1"],
            "foco_b2": focos["B2"],
            "foco_b3": focos["B3"],
            "metas_esacom": metas,
            "metas_reporte_claro": metas_reporte,
        }

    ultima_esacom = CargaExcel.objects.filter(
        tipo_base__in=[CargaExcel.TipoBase.BASE_MATRIZ, CargaExcel.TipoBase.ANDES]
    ).order_by("-creado_en").first()
    estado_datos = {
        "servidor_en": timezone.now().isoformat(),
        "esacom": {
            "actualizado_en": ultima_esacom.creado_en.isoformat() if ultima_esacom else None,
            "tipo_base": ultima_esacom.tipo_base if ultima_esacom else None,
            "archivo_nombre": ultima_esacom.archivo_nombre if ultima_esacom else None,
        },
        "claro_kpi": {
            "actualizado_en": ultima.creado_en.isoformat() if ultima else None,
            "fecha_reporte": (fecha_reporte_desde_nombre(ultima.archivo_nombre).isoformat() if ultima and fecha_reporte_desde_nombre(ultima.archivo_nombre) else None),
            "fecha_corte": ultima.fecha_corte.isoformat() if ultima and ultima.fecha_corte else None,
            "dia_reporte": ultima.dia_reporte if ultima else None,
        },
    }

    ventas_scope = _ventas_visibles(request.user)
    # Se conserva el acumulado por compatibilidad con Supervisor/Gerencia.
    total_ventas = ventas_scope.count()
    instaladas = ventas_scope.filter(estado_instalacion=Venta.EstadoInstalacion.INSTALADO).count()
    pendiente_instalacion = ventas_scope.filter(estado_instalacion=Venta.EstadoInstalacion.PENDIENTE_INSTALACION).count()
    pendiente_comercial = ventas_scope.filter(estado_instalacion=Venta.EstadoInstalacion.PENDIENTE_COMERCIAL).count()
    anuladas = ventas_scope.filter(estado_instalacion=Venta.EstadoInstalacion.ANULADO).count()
    gestionables = max(total_ventas - anuladas, 0)
    resumen_ventas = {
        "total": total_ventas,
        "gestionables": gestionables,
        "instaladas": instaladas,
        "pendiente_instalacion": pendiente_instalacion,
        "pendiente_comercial": pendiente_comercial,
        "anuladas": anuladas,
        "clientes": ventas_scope.values("rut_cliente").distinct().count(),
        "avance_instalacion_pct": round((instaladas / gestionables) * 100, 1) if gestionables else 0.0,
    }

    mes_actual = timezone.localdate().strftime("%Y-%m")
    mes_anterior = _mes_anterior(mes_actual)
    resumen_mes_actual = _resumen_ventas_mes(ventas_scope, mes_actual)
    resumen_mes_anterior = _resumen_ventas_mes(ventas_scope, mes_anterior)

    produccion_actual = None
    produccion_mes_actual = None
    if request.user.cargo == Ejecutivo.Cargo.EJECUTIVO:
        from ventas.produccion import resumen_produccion_actual, resumen_produccion_mes
        produccion_actual = resumen_produccion_actual(ejecutivo=request.user)
        produccion_mes_actual = resumen_produccion_mes(mes=mes_actual, ejecutivo=request.user)

    es_ejecutivo_raso = (
        request.user.cargo == Ejecutivo.Cargo.EJECUTIVO
        and not request.user.es_supervisor
        and not request.user.es_gerencia
        and not request.user.is_superuser
    )

    if getattr(request.user, "es_honorarios", False) and es_ejecutivo_raso:
        # Honorarios ve la misma separaciÃ³n temporal que Regular: producciÃ³n
        # ESACOM del mes calendario actual + Calidad Claro del perÃ­odo medido.
        # La diferencia es que su porcentaje de pago NO hereda meta Regular.
        ventas_h_mes = ventas_scope.filter(
            camada=mes_actual,
            en_base_vigente=True,
        )
        cortes_h = _cortes_vigentes_snapshots_usuario(request.user, focos)
        historico_h = _historico_kpi_usuario_snapshots(request.user, focos)
        return Response({
            "perfil_kpi": "HONORARIOS",
            "cortes": cortes_h,
            "cortes_todos": [],
            "historico_kpi": historico_h,
            "honorarios": resumen_honorarios(ventas_h_mes),
            "ultima_carga": ultima_carga,
            "estado_datos": None,
            "resumen_ventas": resumen_ventas,
            "resumen_mes_actual": resumen_mes_actual,
            "resumen_mes_anterior": resumen_mes_anterior,
            "mes_actual": mes_actual,
            "mes_anterior": mes_anterior,
            "produccion_actual": produccion_actual,
            "produccion_mes_actual": produccion_mes_actual,
        })

    # Ejecutivo y Supervisor consumen snapshots inmutables: un CIERRE nunca
    # es reemplazado por avances posteriores. El alcance se resuelve segÃºn el
    # usuario (cartera propia, equipo o global).
    cortes_actuales = _cortes_vigentes_snapshots_usuario(request.user, focos)
    historico_kpi = _historico_kpi_usuario_snapshots(request.user, focos) if (es_ejecutivo_raso or request.user.es_supervisor) else []
    return Response({
        "perfil_kpi": "REGULAR",
        "cortes": cortes_actuales,
        "cortes_todos": resumen_por_corte(cortes_regulares),
        "historico_kpi": historico_kpi,
        "ultima_carga": ultima_carga,
        # El Ejecutivo no necesita ni debe ver informaciÃ³n tÃ©cnica de cargas.
        "estado_datos": None if es_ejecutivo_raso else estado_datos,
        "resumen_ventas": resumen_ventas,
        "resumen_mes_actual": resumen_mes_actual,
        "resumen_mes_anterior": resumen_mes_anterior,
        "mes_actual": mes_actual,
        "mes_anterior": mes_anterior,
        "produccion_actual": produccion_actual,
        "produccion_mes_actual": produccion_mes_actual,
    })


@api_view(["GET"])
@permission_classes([PuedeMiEquipoOAnalisis])
def dashboard_kpi_ejecutivos(request):
    """Calidad vigente por Ejecutivo, manteniendo Regular y Honorarios separados."""
    from integraciones.models import CargaExcel
    from ventas.produccion import resumen_produccion_mes

    ultima = _ultima_carga_kpi_activa()
    focos = _focos_carga(ultima)
    metas = _metas_efectivas_carga(ultima, focos)
    mes_actual = timezone.localdate().strftime("%Y-%m")

    honorarios_qs = Ejecutivo.objects.filter(
        cargo=Ejecutivo.Cargo.EJECUTIVO,
        tipo_kpi=Ejecutivo.TipoKPI.HONORARIOS,
        is_active=True,
    )
    if request.user.es_supervisor:
        honorarios_qs = honorarios_qs.filter(supervisor=request.user)
    elif not request.user.tiene_alcance_global:
        honorarios_qs = honorarios_qs.none()

    honorarios = []
    camadas_abiertas = _camadas_b1_abiertas()
    camada_activa = camadas_abiertas[0] if camadas_abiertas else ((focos or {}).get("B1") or "")
    for ejecutivo in honorarios_qs.select_related("supervisor").order_by("nombre"):
        calidad = _resumen_mes_kpi_usuario(ejecutivo, camada_activa, en_curso=True) if camada_activa else None
        produccion = resumen_produccion_mes(mes=mes_actual, ejecutivo=ejecutivo)
        honorarios.append({
            "ejecutivo": {
                "id": ejecutivo.id,
                "rut": ejecutivo.rut,
                "nombre": ejecutivo.nombre,
                "equipo": ejecutivo.equipo,
                "tipo_kpi": ejecutivo.tipo_kpi,
                "supervisor_id": ejecutivo.supervisor_id,
                "supervisor_nombre": ejecutivo.supervisor.nombre if ejecutivo.supervisor_id else "",
            },
            "calidad_actual": calidad,
            "produccion_mes_actual": produccion,
        })

    regulares_qs = Ejecutivo.objects.filter(
        cargo=Ejecutivo.Cargo.EJECUTIVO,
        tipo_kpi=Ejecutivo.TipoKPI.REGULAR,
        is_active=True,
    ).select_related("supervisor").order_by("nombre")
    if request.user.es_supervisor:
        regulares_qs = regulares_qs.filter(supervisor=request.user)
    elif not request.user.tiene_alcance_global:
        regulares_qs = regulares_qs.none()

    ejecutivos_snapshot = []
    for ejecutivo in regulares_qs:
        calidad = _resumen_mes_kpi_usuario(ejecutivo, camada_activa, en_curso=True) if camada_activa else None
        if not calidad or not calidad.get("tiene_datos"):
            continue
        ejecutivos_snapshot.append({
            "ejecutivo": {
                "id": ejecutivo.id,
                "rut": ejecutivo.rut,
                "nombre": ejecutivo.nombre,
                "equipo": ejecutivo.equipo,
                "tipo_kpi": ejecutivo.tipo_kpi,
                "supervisor_id": ejecutivo.supervisor_id,
                "supervisor_nombre": ejecutivo.supervisor.nombre if ejecutivo.supervisor_id else "",
            },
            "cortes": [calidad],
            "promedio_focos": round(float(calidad.get("pct_cumplimiento") or 0), 1),
        })
    ejecutivos_snapshot.sort(key=lambda r: (r["promedio_focos"], r["ejecutivo"]["nombre"]))

    return Response({
        "ejecutivos": ejecutivos_snapshot,
        "honorarios": honorarios,
        "snapshot": {
            "id": ultima.id,
            "fecha_corte": ultima.fecha_corte.isoformat() if ultima and ultima.fecha_corte else None,
            "dia_reporte": ultima.dia_reporte if ultima else None,
            "archivo_nombre": ultima.archivo_nombre if ultima else None,
            "fecha_reporte": (fecha_reporte_desde_nombre(ultima.archivo_nombre).isoformat() if ultima and fecha_reporte_desde_nombre(ultima.archivo_nombre) else None),
            "camadas_abiertas": camadas_abiertas,
            "focos": focos,
            "metas": metas,
            "metas_reporte_claro": _metas_reporte_carga(ultima),
        } if ultima else None,
    })


def _metadata_snapshot_kpi(carga):
    if not carga:
        return None
    focos = _focos_carga(carga)
    metas_reporte = _metas_reporte_carga(carga)
    metas = _metas_efectivas_carga(carga, focos)
    return {
        "id": carga.id,
        "archivo_nombre": carga.archivo_nombre,
        "fecha_reporte": (fecha_reporte_desde_nombre(carga.archivo_nombre).isoformat() if fecha_reporte_desde_nombre(carga.archivo_nombre) else None),
        "fecha_corte": carga.fecha_corte.isoformat() if carga.fecha_corte else None,
        "dia_reporte": carga.dia_reporte,
        "estado_reporte": carga.estado_reporte,
        "creado_en": carga.creado_en.isoformat(),
        "focos": focos,
        "metas": metas,
        "metas_reporte_claro": metas_reporte,
        "avances_claro": {
            "B1": float(carga.avance_b1) if carga.avance_b1 is not None else None,
            "B2": float(carga.avance_b2) if carga.avance_b2 is not None else None,
            "B3": float(carga.avance_b3) if carga.avance_b3 is not None else None,
        },
    }


def _resumen_snapshot_historico(carga, focos, user=None):
    """Resume una carga histÃ³rica sin volver a consultar la matriz ESACOM actual.

    Si ``user`` se entrega, el alcance se resuelve con ``snapshot_esacom``.
    Sin usuario se mantiene un fallback compatible para pruebas legacy.
    """
    from integraciones.models import KPIRegistro

    if not carga:
        return {}
    resultado = {}
    for boleta in ("B1", "B2", "B3"):
        camada = (focos or {}).get(boleta) or ""
        if not camada:
            continue
        qs = KPIRegistro.objects.filter(carga=carga, camada=camada, boleta=boleta)
        if user is not None:
            registros = _scope_registros_kpi_qs(qs, user)
        else:
            # Compatibilidad con pruebas/instalaciones aÃºn no sembradas.
            registros = qs.filter(
                cruce_ok=True,
                venta__estado_instalacion=Venta.EstadoInstalacion.INSTALADO,
                venta__ejecutivo__tipo_kpi=Ejecutivo.TipoKPI.REGULAR,
                venta__ejecutivo__cargo=Ejecutivo.Cargo.EJECUTIVO,
                venta__ejecutivo__is_active=True,
            ).select_related("venta", "venta__promocion")
        meta = meta_calidad_para(boleta=boleta, camada=camada, fallback=getattr(carga, f"meta_{boleta.lower()}", None))
        resumen = resumen_kpi_registros(registros, meta_pct=serializar_meta(meta) or 0)
        resumen.update({"boleta": boleta, "mes_ano": camada})
        resultado[boleta] = resumen
    return resultado


@api_view(["GET"])
@permission_classes([PuedeDashboardOAnalisis])
def dashboard_gerencia(request):
    """Resumen ejecutivo consistente con Portal Ejecutivo/Supervisor.

    ESACOM define venta, RUT, RGU y estructura comercial. Claro aporta los
    snapshots KPI. Entrega ranking por Supervisor/Ejecutivo, evoluciÃ³n del
    Ãºltimo snapshot contra el anterior y datos operativos para drill-down.
    """
    from integraciones.models import CargaExcel, KPIRegistro
    from usuarios.models import Ejecutivo

    cargas = sorted(
        CargaExcel.objects.filter(
            tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
            estado_reporte=CargaExcel.EstadoReporte.AVANCE,
            formato_kpi=CargaExcel.FormatoKPI.DETALLADO,
            fecha_corte__isnull=False,
        ),
        key=_clave_temporal_carga,
        reverse=True,
    )[:2]
    if not cargas:
        fallback = _ultima_carga_kpi_activa()
        cargas = [fallback] if fallback else []
    ultima = cargas[0] if cargas else None
    anterior = cargas[1] if len(cargas) > 1 else None
    snap_actual = _metadata_snapshot_kpi(ultima)
    snap_anterior = _metadata_snapshot_kpi(anterior)
    focos = snap_actual["focos"] if snap_actual else {}
    metas = snap_actual["metas"] if snap_actual else {}

    # R2.17.2: la portada no materializa rankings ni accionables. Esos datos
    # tienen pantallas/endpoints propios y no son renderizados por
    # DashboardGerencia.jsx. Evitar cargarlos aquÃ­ elimina el N+1 que llevaba
    # el request inicial a cientos de consultas.
    # KPI Gerencia sale del snapshot ESACOM+Claro de la carga, no de Venta
    # actual. AsÃ­ una sincronizaciÃ³n posterior solo modifica OperaciÃ³n actual.
    global_actual = []
    for boleta in ("B1", "B2", "B3"):
        camada = (focos or {}).get(boleta) or ""
        if not camada:
            continue
        resumen = _resumen_par_snapshot_usuario(request.user, boleta, camada, carga=ultima)
        if resumen:
            global_actual.append(resumen)

    # Compatibilidad de contrato: la portada conserva las claves, pero no
    # calcula payloads que no utiliza. Rankings se consultan en Ejecutivos y
    # la auditorÃ­a/accionables en sus mÃ³dulos dedicados.
    ejecutivos = []
    supervisores = []
    comparacion = []

    # OperaciÃ³n ACTUAL: la portada de Gerencia no debe mezclar acumulados
    # histÃ³ricos con el mes calendario vigente. ESACOM sigue siendo la fuente
    # maestra operacional; Claro solo aporta la mediciÃ³n de Calidad.
    mes_actual = timezone.localdate().strftime("%Y-%m")
    # Solo la base ESACOM vigente del mes, mÃ¡s la hoja Honorarios del mismo
    # perÃ­odo. AsÃ­ una venta histÃ³rica que ya no estÃ¡ en la matriz vigente no
    # vuelve a inflar Clientes/Instaladas/Pendientes de la portada.
    ventas_scope = Venta.objects.select_related("ejecutivo").filter(
        models.Q(en_base_vigente=True) | models.Q(origen_venta=Venta.OrigenVenta.HONORARIOS)
    )
    actividad_mes = _resumen_ventas_mes(ventas_scope, mes_actual)
    from ventas.produccion import (
        detalle_produccion_actual,
        resumen_movil_vigente_por_supervisor,
        resumen_produccion_actual,
        resumen_produccion_mes,
    )
    # Dos universos deliberadamente separados:
    # - producción del mes: ventas cuya fecha/camada pertenece al mes calendario;
    # - control operativo: fotografía vigente de ESACOM (mismo universo del control diario).
    produccion_mes = resumen_produccion_mes(mes=mes_actual)
    control_operativo = resumen_produccion_actual()
    detalle_control = detalle_produccion_actual()
    movil_por_supervisor = resumen_movil_vigente_por_supervisor()
    ultima_esacom = CargaExcel.objects.filter(
        tipo_base__in=[CargaExcel.TipoBase.BASE_MATRIZ, CargaExcel.TipoBase.ANDES]
    ).order_by("-creado_en").first()
    ejecutivos_activos = Ejecutivo.objects.filter(
        cargo=Ejecutivo.Cargo.EJECUTIVO,
        is_active=True,
    )
    operacion = {
        "mes_actual": mes_actual,
        "ventas_total": actividad_mes["total"],
        "instaladas": actividad_mes["instaladas"],
        "pendiente_instalacion": actividad_mes["pendiente_instalacion"],
        "pendiente_comercial": actividad_mes["pendiente_comercial"],
        "anuladas": actividad_mes["anuladas"],
        "clientes": actividad_mes["clientes"],
        "rgu_fijo_vendidos": produccion_mes.get("rgu_fijo_vendidos", 0),
        "rgu_fijo_gestionables": produccion_mes.get("rgu_fijo_gestionables", 0),
        "ventas_fijo": produccion_mes.get("ventas_fijo", 0),
        "movil_portadas": control_operativo.get("kpi_movil_portadas", 0),
        "movil_principal": control_operativo.get("movil_principal", 0),
        "movil_adicional": control_operativo.get("movil_adicional", 0),
        "movil_por_supervisor": movil_por_supervisor,
        "ejecutivos_activos": ejecutivos_activos.count(),
        "ejecutivos_regulares_activos": ejecutivos_activos.filter(tipo_kpi=Ejecutivo.TipoKPI.REGULAR).count(),
        "ejecutivos_honorarios_activos": ejecutivos_activos.filter(tipo_kpi=Ejecutivo.TipoKPI.HONORARIOS).count(),
        "supervisores_activos": Ejecutivo.objects.filter(
            cargo=Ejecutivo.Cargo.SUPERVISOR,
            is_active=True,
        ).count(),
        "ultima_sync_esacom": ultima_esacom.creado_en.isoformat() if ultima_esacom else None,
        "archivo_esacom": ultima_esacom.archivo_nombre if ultima_esacom else None,
        "produccion_mes": {
            "mes": mes_actual,
            "rgu_fijo_vendidos": produccion_mes.get("rgu_fijo_vendidos", 0),
            "ventas_fijo": produccion_mes.get("ventas_fijo", 0),
            "rgu_fijo_gestionables": produccion_mes.get("rgu_fijo_gestionables", 0),
            "rgu_fijo_anulados": produccion_mes.get("rgu_fijo_anulados", 0),
            "movil_portadas": produccion_mes.get("kpi_movil_portadas", 0),
            "movil_principal": produccion_mes.get("movil", {}).get("principal", 0),
            "movil_adicional": produccion_mes.get("movil", {}).get("adicional", 0),
        },
        "control_operativo": {
            "rgu_completadas": control_operativo.get("rgu_fijo_completados", 0),
            "rgu_pendiente_instalacion": control_operativo.get("rgu_fijo_pendiente_instalacion", 0),
            "rgu_pendiente_comercial": control_operativo.get("rgu_fijo_pendiente_comercial", 0),
            "rgu_anulados": control_operativo.get("rgu_fijo_anulados", 0),
            "rgu_total_control": control_operativo.get("rgu_fijo_control", 0),
            "movil_portadas": control_operativo.get("kpi_movil_portadas", 0),
            "movil_principal": control_operativo.get("movil_principal", 0),
            "movil_adicional": control_operativo.get("movil_adicional", 0),
            "movil_pendiente_activacion": control_operativo.get("movil_pendiente_activacion", 0),
            "fijo_por_supervisor": {
                nombre: {
                    "completadas": datos.get("fija", {}).get("completadas", 0),
                    "pendiente_instalacion": datos.get("fija", {}).get("pendiente_instalacion", 0),
                    "total_control": datos.get("fija", {}).get("total_control", 0),
                }
                for nombre, datos in detalle_control.get("supervisores", {}).items()
            },
            "movil_por_supervisor": movil_por_supervisor,
        },
    }

    # La portada gerencial debe reproducir el control manual diario de la hoja
    # ``Resumen`` cuando ese bloque estÃ¡ disponible en el mismo XLSX de ESACOM.
    # Conservamos el cÃ¡lculo mensual anterior como auditorÃ­a para explicar la
    # diferencia de universo/unidad, pero no lo mostramos como control oficial.
    resumen_fuente = ((ultima_esacom.resumen_produccion or {}).get("resumen_gerencia_fuente", {}) if ultima_esacom else {})
    if resumen_fuente.get("disponible"):
        fija_resumen = resumen_fuente.get("ventas_fijas", {}) or {}
        calculo_mes = {
            "rgu_fijo": int(operacion["rgu_fijo_vendidos"] or 0),
            "completada": int(operacion["instaladas"] or 0),
            "pendiente_instalacion": int(operacion["pendiente_instalacion"] or 0),
            "pendiente_comercial": int(operacion["pendiente_comercial"] or 0),
            "anulado": int(operacion["anuladas"] or 0),
        }
        oficial = {
            "rgu_fijo": int(fija_resumen.get("total_rgu", 0) or 0),
            "completada": int(fija_resumen.get("completada", 0) or 0),
            "pendiente_instalacion": int(fija_resumen.get("pendiente_instalacion", 0) or 0),
            "pendiente_comercial": int(fija_resumen.get("pendiente_comercial", 0) or 0),
            "anulado": int(fija_resumen.get("anulado", 0) or 0),
            "derivado_redes": int(fija_resumen.get("derivado_redes", 0) or 0),
        }
        operacion.update({
            "fuente_operacion": "RESUMEN_ESACOM",
            "rgu_fijo_vendidos": oficial["rgu_fijo"],
            "instaladas": oficial["completada"],
            "pendiente_instalacion": oficial["pendiente_instalacion"],
            "pendiente_comercial": oficial["pendiente_comercial"],
            "anuladas": oficial["anulado"],
            "derivado_redes": oficial["derivado_redes"],
            "completada_por_supervisor": resumen_fuente.get("completada_por_supervisor", {}) or {},
            "cruce_claro_total": int((resumen_fuente.get("cruce_claro", {}) or {}).get("total", 0) or 0),
            "cruce_claro_por_supervisor": (resumen_fuente.get("cruce_claro", {}) or {}).get("por_supervisor", {}) or {},
            "calculo_mes_crm": calculo_mes,
            "diferencias_resumen_vs_mes": {
                clave: oficial.get(clave, 0) - calculo_mes.get(clave, 0)
                for clave in ("rgu_fijo", "completada", "pendiente_instalacion", "pendiente_comercial", "anulado")
            },
        })
    else:
        operacion["fuente_operacion"] = "CALCULO_MES_CRM"

    # La portada no renderiza AuditorÃ­a KPI ni Accionables. Mantener estos
    # cÃ¡lculos aquÃ­ generaba 7 COUNT completos y materializaciÃ³n de Corte en
    # cada apertura. Los mÃ³dulos dedicados siguen entregando esa informaciÃ³n.
    auditoria = None
    accionables = {}
    camadas_abiertas = _camadas_b1_abiertas()
    calidad_abierta = [
        resumen for resumen in (
            _resumen_mes_kpi_usuario(request.user, camada, en_curso=True)
            for camada in camadas_abiertas
        ) if resumen is not None
    ]
    return Response({
        "snapshot_actual": snap_actual,
        "snapshot_anterior": snap_anterior,
        "global": global_actual,
        "calidad_abierta": calidad_abierta,
        "camadas_abiertas": camadas_abiertas,
        "comparacion": comparacion,
        "supervisores": supervisores,
        "ejecutivos": ejecutivos,
        "operacion": operacion,
        "auditoria": auditoria,
        "accionables": accionables,
    })


@api_view(["GET"])
@permission_classes([PuedeDashboardOAnalisis])
def dashboard_gerencia_buscar_usuario(request):
    """Busca personal comercial por nombre o RUT para la ficha KPI de Gerencia."""
    q = str(request.query_params.get("q") or "").strip()
    if len(q) < 2:
        return Response({"resultados": []})

    qs = Ejecutivo.objects.filter(
        cargo__in=[Ejecutivo.Cargo.EJECUTIVO, Ejecutivo.Cargo.SUPERVISOR]
    ).filter(
        models.Q(nombre__icontains=q) | models.Q(rut__icontains=q)
    ).select_related("supervisor").order_by("-is_active", "nombre")[:20]

    return Response({
        "resultados": [
            {
                "id": e.id,
                "rut": e.rut,
                "nombre": e.nombre,
                "cargo": e.cargo,
                "tipo_kpi": e.tipo_kpi,
                "is_active": e.is_active,
                "supervisor_id": e.supervisor_id,
                "supervisor_nombre": e.supervisor.nombre if e.supervisor_id else "",
            }
            for e in qs
        ]
    })


@api_view(["GET"])
@permission_classes([PuedeDashboardOAnalisis])
def dashboard_gerencia_usuario_detalle(request, pk):
    """KPI actual, producciÃ³n actual e histÃ³rico de una persona seleccionada."""
    try:
        usuario = Ejecutivo.objects.select_related("supervisor").get(pk=pk)
    except Ejecutivo.DoesNotExist:
        return Response({"detail": "Usuario no encontrado."}, status=404)

    if usuario.cargo not in (Ejecutivo.Cargo.EJECUTIVO, Ejecutivo.Cargo.SUPERVISOR):
        return Response({"detail": "El usuario no pertenece a la estructura comercial."}, status=400)

    ultima = _ultima_carga_kpi_activa()
    focos = _focos_carga(ultima)
    camadas_abiertas = _camadas_b1_abiertas()
    calidad_abierta = [
        resumen for resumen in (
            _resumen_mes_kpi_usuario(usuario, camada, en_curso=True)
            for camada in camadas_abiertas
        ) if resumen is not None
    ]
    calidad_actual = calidad_abierta[0] if calidad_abierta else None
    historico = _historico_kpi_usuario_snapshots(usuario, focos)

    from ventas.produccion import resumen_produccion_mes
    mes_actual = timezone.localdate().strftime("%Y-%m")
    if usuario.cargo == Ejecutivo.Cargo.SUPERVISOR:
        produccion_mes = resumen_produccion_mes(mes=mes_actual, supervisor=usuario, movil_vigente_actual=True)
        produccion_propia = resumen_produccion_mes(mes=mes_actual, ejecutivo=usuario, movil_vigente_actual=True)
        dotacion = Ejecutivo.objects.filter(
            cargo=Ejecutivo.Cargo.EJECUTIVO, supervisor=usuario, is_active=True
        )
        equipo = {
            "total": dotacion.count(),
            "regular": dotacion.filter(tipo_kpi=Ejecutivo.TipoKPI.REGULAR).count(),
            "honorarios": dotacion.filter(tipo_kpi=Ejecutivo.TipoKPI.HONORARIOS).count(),
        }
    else:
        produccion_mes = resumen_produccion_mes(mes=mes_actual, ejecutivo=usuario, movil_vigente_actual=True)
        produccion_propia = None
        equipo = None

    return Response({
        "usuario": {
            "id": usuario.id,
            "rut": usuario.rut,
            "nombre": usuario.nombre,
            "cargo": usuario.cargo,
            "tipo_kpi": usuario.tipo_kpi,
            "is_active": usuario.is_active,
            "supervisor_id": usuario.supervisor_id,
            "supervisor_nombre": usuario.supervisor.nombre if usuario.supervisor_id else "",
        },
        "mes_actual": mes_actual,
        "calidad_actual": calidad_actual,
        "calidad_abierta": calidad_abierta,
        "camadas_abiertas": camadas_abiertas,
        "produccion_mes_actual": produccion_mes,
        "produccion_propia_mes_actual": produccion_propia,
        "equipo": equipo,
        "historico_kpi": historico,
        "snapshot": _metadata_snapshot_kpi(ultima),
    })



def _config_cierres_canal(canal: str):
    """Configura el origen de cierres sin mezclar Fijo y MÃ³vil."""
    from integraciones.models import CargaExcel

    canal = str(canal or "").strip().upper()
    if canal == "FIJO":
        return {
            "canal": "FIJO",
            "formato_cierre": CargaExcel.FormatoKPI.CIERRE_FIJO,
            "formato_avance": CargaExcel.FormatoKPI.DETALLADO,
        }
    if canal == "MOVIL":
        return {
            "canal": "MOVIL",
            "formato_cierre": CargaExcel.FormatoKPI.CIERRE_MOVIL,
            "formato_avance": CargaExcel.FormatoKPI.AVANCE_MOVIL,
        }
    return None


def _cierres_oficiales_canal(canal: str):
    """Primer CIERRE oficial de cada mes para el canal solicitado.

    Un mes se considera cerrado exclusivamente cuando Claro fue cargado como
    ``CIERRE_FIJO`` o ``CIERRE_MOVIL``. Los AVANCE nunca cierran meses.
    Si por error se cargara otro cierre posterior del mismo mes, se conserva
    el primero, igual que la regla histÃ³rica de ``_cierre_oficial_mes``.
    """
    from integraciones.models import CargaExcel

    cfg = _config_cierres_canal(canal)
    if not cfg:
        return {}
    cargas = CargaExcel.objects.filter(
        tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
        estado_reporte=CargaExcel.EstadoReporte.CIERRE,
        formato_kpi=cfg["formato_cierre"],
    ).order_by("fecha_corte", "creado_en", "id")

    cierres = {}
    for carga in cargas:
        for boleta, campo in (("B1", "foco_b1"), ("B2", "foco_b2"), ("B3", "foco_b3")):
            camada = (getattr(carga, campo, "") or "").strip()
            if camada and camada not in cierres:
                cierres[camada] = {"carga": carga, "boleta": boleta}
    return cierres


def _ultimo_avance_canal(canal: str):
    from integraciones.models import CargaExcel

    cfg = _config_cierres_canal(canal)
    if not cfg:
        return None
    return CargaExcel.objects.filter(
        tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
        estado_reporte=CargaExcel.EstadoReporte.AVANCE,
        formato_kpi=cfg["formato_avance"],
    ).order_by("-fecha_corte", "-creado_en", "-id").first()


def _metadata_cierre(carga, boleta: str, camada: str, canal: str) -> dict:
    meta_reporte = getattr(carga, f"meta_{boleta.lower()}", None)
    if str(canal).upper() == "MOVIL":
        meta = float(meta_reporte) if meta_reporte is not None else None
    else:
        meta_obj = meta_calidad_para(boleta=boleta, camada=camada, fallback=meta_reporte)
        meta = serializar_meta(meta_obj)
    referencia = getattr(carga, f"avance_{boleta.lower()}", None)
    return {
        "canal": str(canal).upper(),
        "mes_ano": camada,
        "boleta": boleta,
        "estado": "CIERRE_OFICIAL" if carga.estado_reporte == "CIERRE" else "EN_CURSO",
        "carga_id": carga.id,
        "archivo": carga.archivo_nombre,
        "fecha_reporte": (fecha_reporte_desde_nombre(carga.archivo_nombre).isoformat() if fecha_reporte_desde_nombre(carga.archivo_nombre) else None),
        "fecha_corte": carga.fecha_corte.isoformat() if carga.fecha_corte else None,
        "dia_reporte": carga.dia_reporte,
        "formato_kpi": carga.formato_kpi,
        "meta_pct": meta,
        "referencia_claro": float(referencia) if referencia is not None else None,
    }


def _resumen_cierre_para_gerencia(request, carga, boleta: str, camada: str, canal: str) -> dict:
    """Usa exactamente la misma regla KPI visible en Gerencia/Portal."""
    resumen = _resumen_par_snapshot_usuario(request.user, boleta, camada, carga=carga) or {}
    return {
        "pagadas": int(resumen.get("pagadas") or 0),
        "pendientes": int(resumen.get("pendientes") or 0),
        "no_pago": int(resumen.get("no_pago") or 0),
        "fuera_plazo": int(resumen.get("fuera_plazo") or 0),
        "sin_boleta": int(resumen.get("sin_boleta") or 0),
        "fuera_medicion": int(resumen.get("fuera_medicion") or 0),
        "total": int(resumen.get("total") or 0),
        "total_con_sin_boleta": int(resumen.get("total_con_sin_boleta") or 0),
        "pct_cumplimiento": float(resumen.get("pct_cumplimiento") or 0),
        "faltan_para_meta": int(resumen.get("faltan_para_meta") or 0),
        "meta_pct": resumen.get("meta_pct"),
        "meta_definida": resumen.get("meta_definida", True),
        "tiene_datos": bool(resumen.get("tiene_datos")),
        "unidad": resumen.get("unidad") or "RGU",
    }


def _resumen_planilla_cierre_fijo(qs):
    """Replica la tabla dinÃ¡mica usada por Gerencia en ``Cierre KPI jul``.

    A diferencia del KPI CRM (Pago / RGU medibles), esta vista de control usa
    Pago / Total general e incluye S/B y estados no clasificados (#N/D), tal
    como la planilla de cierre entregada por Gerencia. Se muestra como mÃ©trica
    paralela; no reemplaza la regla KPI oficial del portal.
    """
    acumulado = {
        "no_pago": 0,
        "fuera_plazo": 0,
        "pagadas": 0,
        "pendientes": 0,
        "sin_boleta": 0,
        "n_d": 0,
    }
    conocidos = {
        "PAGO": "pagadas",
        "NO PAGO": "no_pago",
        "PENDIENTE": "pendientes",
        "S/B": "sin_boleta",
        "PAGADO FUERA DE PLAZO": "fuera_plazo",
    }
    iterable = (
        qs.select_related("venta", "venta__promocion")
        if hasattr(qs, "select_related")
        else qs
    )
    for registro in iterable:
        if not registro.es_medible:
            continue
        rgu = registro.rgu
        if rgu is None and registro.venta_id:
            rgu = registro.venta.rgu_base
        if rgu is None and registro.venta_id:
            rgu = getattr(registro.venta.promocion, "rgu", None)
        rgu = int(rgu or 1)
        texto = " ".join(str(registro.kpi_texto or "").strip().upper().replace("_", " ").split())
        bucket = conocidos.get(texto)
        if bucket is None:
            # Si el texto original no estÃ¡ disponible, usamos el estado
            # normalizado; cualquier otro valor queda como #N/D.
            fallback = {
                Corte.EstadoPago.PAGADO: "pagadas",
                Corte.EstadoPago.NO_PAGO: "no_pago",
                Corte.EstadoPago.PENDIENTE: "pendientes",
                Corte.EstadoPago.SIN_BOLETA: "sin_boleta",
                Corte.EstadoPago.FUERA_PLAZO: "fuera_plazo",
            }.get(registro.estado_normalizado)
            bucket = fallback if not texto and fallback else "n_d"
        acumulado[bucket] += rgu

    total = sum(acumulado.values())
    pct = round((acumulado["pagadas"] / total * 100), 2) if total else 0.0
    return {
        **acumulado,
        "total_general": total,
        "kpi_pct": pct,
    }


def _desglose_cierre_fijo(carga, boleta: str, camada: str):
    """Desglose dual del CIERRE Fijo.

    - KPI CRM conserva la regla validada del portal (Regular activo, Pago/RGU
      medibles).
    - La tabla de cierre Gerencia replica la planilla manual: poblaciÃ³n ESACOM
      instalada del mes de FECHA CIERRE, RGU ESACOM, estado original Claro,
      incluyendo inactivos, Honorarios, S/B y filas sin cruce (#N/D).
    """
    from collections import defaultdict
    from integraciones.models import KPIRegistro
    from integraciones.cierre_fijo_snapshot import desglose_snapshot_cierre_fijo

    # 1) KPI CRM existente. No se modifica su regla.
    base = KPIRegistro.objects.filter(
        carga=carga,
        camada=camada,
        boleta=boleta,
        cruce_ok=True,
        venta__estado_instalacion=Venta.EstadoInstalacion.INSTALADO,
        venta__ejecutivo__tipo_kpi=Ejecutivo.TipoKPI.REGULAR,
        venta__ejecutivo__cargo=Ejecutivo.Cargo.EJECUTIVO,
        venta__ejecutivo__is_active=True,
    ).select_related(
        "venta",
        "venta__promocion",
        "venta__ejecutivo",
        "venta__ejecutivo__supervisor",
    )

    meta = meta_calidad_para(
        boleta=boleta,
        camada=camada,
        fallback=getattr(carga, f"meta_{boleta.lower()}", None),
    )
    meta_pct = serializar_meta(meta) or 0

    registros = list(base)
    por_ejecutivo = defaultdict(list)
    por_supervisor = defaultdict(list)
    personas = {}
    supervisores_nombre = {}

    for registro in registros:
        venta = registro.venta
        persona = venta.ejecutivo if venta else None
        if not persona:
            continue
        personas[persona.id] = persona
        por_ejecutivo[persona.id].append(registro)
        supervisor_id = persona.supervisor_id or 0
        por_supervisor[supervisor_id].append(registro)
        supervisores_nombre[supervisor_id] = (
            persona.supervisor.nombre if persona.supervisor_id else "Sin supervisor"
        )

    crm_ejecutivos = []
    crm_por_rut = {}
    for persona in sorted(personas.values(), key=lambda p: (p.nombre or "")):
        regs = por_ejecutivo.get(persona.id, [])
        r = resumen_kpi_registros(regs, meta_pct=meta_pct)
        if not (r.get("total_con_sin_boleta") or r.get("fuera_medicion")):
            continue
        fila = {
            "id": persona.id,
            "rut": persona.rut,
            "nombre": persona.nombre,
            "supervisor_id": persona.supervisor_id,
            "supervisor": persona.supervisor.nombre if persona.supervisor_id else "Sin supervisor",
            "activo": persona.is_active,
            **r,
        }
        crm_ejecutivos.append(fila)
        crm_por_rut[str(persona.rut or "").replace(".", "").strip().upper()] = fila

    crm_supervisores = []
    for supervisor_id, regs in sorted(
        por_supervisor.items(), key=lambda item: supervisores_nombre.get(item[0], "")
    ):
        r = resumen_kpi_registros(regs, meta_pct=meta_pct)
        crm_supervisores.append({
            "id": supervisor_id or None,
            "nombre": supervisores_nombre.get(supervisor_id, "Sin supervisor"),
            **r,
        })

    # 2) Control de cierre congelado, equivalente a la planilla Gerencia.
    plan_sup, plan_ejec, plan_global, _ = desglose_snapshot_cierre_fijo(carga, boleta, camada)

    def completar_desde_planilla(item, crm=None):
        plan = item.get("planilla_cierre") or {}
        item.update({
            # Las columnas de estado de la tabla deben ser las del cierre
            # manual, no las del denominador CRM.
            "pagadas": int(plan.get("pagadas") or 0),
            "pendientes": int(plan.get("pendientes") or 0),
            "no_pago": int(plan.get("no_pago") or 0),
            "fuera_plazo": int(plan.get("fuera_plazo") or 0),
            "sin_boleta": int(plan.get("sin_boleta") or 0),
            "total_cierre": int(plan.get("total_general") or 0),
            "meta_pct": meta_pct,
            # KPI CRM es paralelo. Si ese histÃ³rico no pertenece al universo
            # Regular activo actual, se deja nulo en vez de inventarlo.
            "pct_cumplimiento": (crm or {}).get("pct_cumplimiento"),
            "faltan_para_meta": (crm or {}).get("faltan_para_meta"),
            "total": (crm or {}).get("total"),
            "fuera_medicion": (crm or {}).get("fuera_medicion", 0),
        })
        return item

    for item in plan_ejec:
        rut = str(item.get("rut") or "").replace(".", "").strip().upper()
        completar_desde_planilla(item, crm_por_rut.get(rut))

    # En supervisores la fuente manual usa el nombre de supervisor de la venta
    # histÃ³rica. KPI CRM usa la dotaciÃ³n vigente; solo lo vinculamos cuando el
    # nombre coincide exactamente para no reasignar historia.
    crm_sup_por_nombre = {
        " ".join(str(x.get("nombre") or "").upper().split()): x
        for x in crm_supervisores
    }
    for item in plan_sup:
        clave = " ".join(str(item.get("nombre") or "").upper().split())
        crm = crm_sup_por_nombre.get(clave)
        if crm is None and clave:
            palabras = set(clave.split())
            candidatos = [
                fila for nombre, fila in crm_sup_por_nombre.items()
                if palabras and palabras.issubset(set(nombre.split()))
            ]
            if len(candidatos) == 1:
                crm = candidatos[0]
        completar_desde_planilla(item, crm)

    return plan_sup, plan_ejec, plan_global

def _resumen_movil_fila(row, meta_pct: float):
    pagadas = int(row.pagadas or 0)
    pendientes = int(row.pendientes or 0)
    no_pago = int(row.no_pago or 0)
    fuera = int(row.fuera_plazo or 0)
    sin_boleta = int(row.sin_boleta or 0)
    total = int(row.total_medible or 0)
    pct = round((pagadas / total * 100), 2) if total else 0.0
    objetivo = 0
    if total and meta_pct:
        objetivo = int((Decimal(total) * Decimal(str(meta_pct)) / Decimal("100")).to_integral_value(rounding=ROUND_CEILING))
    return {
        "pagadas": pagadas,
        "pendientes": pendientes,
        "no_pago": no_pago,
        "fuera_plazo": fuera,
        "sin_boleta": sin_boleta,
        "fuera_medicion": 0,
        "total": total,
        "total_con_sin_boleta": total + sin_boleta,
        "pct_cumplimiento": pct,
        "faltan_para_meta": max(0, objetivo - pagadas),
        "meta_pct": float(meta_pct or 0),
        "unidad": "RGU",
    }


def _desglose_cierre_movil(carga, boleta: str, camada: str):
    from integraciones.models import KPICierreResumen

    meta_raw = getattr(carga, f"meta_{boleta.lower()}", None)
    meta_pct = float(meta_raw or 0)
    qs = KPICierreResumen.objects.filter(carga=carga, camada=camada, boleta=boleta).exclude(
        rut_vendedor_fuente="GLOBAL"
    ).select_related("ejecutivo", "ejecutivo__supervisor")

    ejecutivos = []
    for row in qs.order_by("ejecutivo__nombre", "rut_vendedor_fuente"):
        persona = row.ejecutivo
        r = _resumen_movil_fila(row, meta_pct)
        ejecutivos.append({
            "id": persona.id if persona else None,
            "rut": persona.rut if persona else row.rut_vendedor_fuente,
            "nombre": persona.nombre if persona else (row.rut_vendedor_fuente or "No resuelto"),
            "supervisor_id": persona.supervisor_id if persona else None,
            "supervisor": persona.supervisor.nombre if persona and persona.supervisor_id else "Sin supervisor",
            "activo": persona.is_active if persona else False,
            **r,
        })

    # El reporte mÃ³vil ya viene agregado por vendedor. Sumamos esas filas para
    # la vista por Supervisor sin inventar pedidos que el archivo no trae.
    buckets = {}
    for fila in ejecutivos:
        key = fila["supervisor_id"] or 0
        bucket = buckets.setdefault(key, {
            "id": fila["supervisor_id"], "nombre": fila["supervisor"],
            "pagadas": 0, "pendientes": 0, "no_pago": 0, "fuera_plazo": 0,
            "sin_boleta": 0, "fuera_medicion": 0, "total": 0,
        })
        for campo in ("pagadas", "pendientes", "no_pago", "fuera_plazo", "sin_boleta", "fuera_medicion", "total"):
            bucket[campo] += int(fila.get(campo) or 0)

    supervisores = []
    for bucket in sorted(buckets.values(), key=lambda x: x["nombre"]):
        total = bucket["total"]
        pagadas = bucket["pagadas"]
        pct = round((pagadas / total * 100), 2) if total else 0.0
        objetivo = int((Decimal(total) * Decimal(str(meta_pct)) / Decimal("100")).to_integral_value(rounding=ROUND_CEILING)) if total and meta_pct else 0
        bucket.update({
            "total_con_sin_boleta": total + bucket["sin_boleta"],
            "pct_cumplimiento": pct,
            "faltan_para_meta": max(0, objetivo - pagadas),
            "meta_pct": meta_pct,
            "unidad": "RGU",
        })
        supervisores.append(bucket)
    return supervisores, ejecutivos


def _detalle_cierre(request, canal: str, camada: str):
    canal = str(canal or "").upper()
    cierres = _cierres_oficiales_canal(canal)
    item = cierres.get(camada)
    if not item:
        return None
    carga = item["carga"]
    boleta = item["boleta"]
    meta = _metadata_cierre(carga, boleta, camada, canal)
    resumen = _resumen_cierre_para_gerencia(request, carga, boleta, camada, canal)
    planilla_cierre = None
    if canal == "MOVIL":
        supervisores, ejecutivos = _desglose_cierre_movil(carga, boleta, camada)
    else:
        supervisores, ejecutivos, planilla_cierre = _desglose_cierre_fijo(carga, boleta, camada)
    return {
        "cierre": meta,
        "resumen": resumen,
        "planilla_cierre": planilla_cierre,
        "supervisores": supervisores,
        "ejecutivos": ejecutivos,
    }


@api_view(["GET"])
@permission_classes([PuedeDashboardGerencia])
def dashboard_gerencia_cierres(request):
    """PerÃ­odo abierto + histÃ³rico de CIERRES oficiales por canal."""
    canal = str(request.query_params.get("canal") or "FIJO").upper()
    cfg = _config_cierres_canal(canal)
    if not cfg:
        return Response({"detail": "canal debe ser FIJO o MOVIL."}, status=400)

    cierres_map = _cierres_oficiales_canal(canal)
    cierres = []
    for camada in sorted(cierres_map.keys(), reverse=True):
        carga = cierres_map[camada]["carga"]
        boleta = cierres_map[camada]["boleta"]
        cierres.append({
            **_metadata_cierre(carga, boleta, camada, canal),
            "resumen": _resumen_cierre_para_gerencia(request, carga, boleta, camada, canal),
        })

    actual = None
    avance = _ultimo_avance_canal(canal)
    if avance:
        camada = (avance.foco_b1 or "").strip()
        if camada and camada not in cierres_map:
            actual = {
                **_metadata_cierre(avance, "B1", camada, canal),
                "resumen": _resumen_cierre_para_gerencia(request, avance, "B1", camada, canal),
            }
            actual["estado"] = "EN_CURSO"

    return Response({
        "canal": canal,
        "actual": actual,
        "cierres": cierres,
        "regla": "Un mes se congela solo cuando Claro se carga como CIERRE oficial del canal.",
    })


@api_view(["GET"])
@permission_classes([PuedeDashboardGerencia])
def dashboard_gerencia_cierre_detalle(request, canal, camada):
    canal = str(canal or "").upper()
    if not _config_cierres_canal(canal):
        return Response({"detail": "canal debe ser FIJO o MOVIL."}, status=400)
    detalle = _detalle_cierre(request, canal, camada)
    if not detalle:
        return Response({"detail": "No existe un CIERRE oficial para ese mes y canal."}, status=404)
    return Response(detalle)


def _csv_response(nombre_archivo: str):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{nombre_archivo}"'
    response.write("\ufeff")
    return response


@api_view(["GET"])
@permission_classes([PuedeDashboardGerencia])
def dashboard_gerencia_cierre_csv(request, canal, camada):
    """Exporta el cierre congelado. ``tipo=resumen`` o ``tipo=detalle``."""
    from integraciones.models import CargaExcel, KPIRegistro, KPICierreResumen, KPICierreFijoFila

    canal = str(canal or "").upper()
    tipo = str(request.query_params.get("tipo") or "resumen").lower()
    if tipo not in {"resumen", "detalle"}:
        return Response({"detail": "tipo debe ser resumen o detalle."}, status=400)
    detalle = _detalle_cierre(request, canal, camada)
    if not detalle:
        return Response({"detail": "No existe un CIERRE oficial para ese mes y canal."}, status=404)

    meta = detalle["cierre"]
    carga_id = meta["carga_id"]
    boleta = meta["boleta"]
    response = _csv_response(f"CIERRE_KPI_{canal}_{camada}_{tipo}.csv")
    writer = csv.writer(response, delimiter=";")

    if tipo == "resumen":
        writer.writerow([
            "Canal", "Mes", "Boleta", "Fecha corte", "Archivo", "Supervisor",
            "RUT ejecutivo", "Ejecutivo", "Pago", "Pendiente", "No Pago",
            "Fuera plazo", "S/B", "#N/D cierre", "Fuera medicion", "Total medible", "KPI CRM %",
            "Total general cierre", "KPI cierre planilla %", "Meta %", "Q para meta", "Estado",
        ])
        for fila in detalle["ejecutivos"]:
            crm_pct = fila.get("pct_cumplimiento")
            q_meta = fila.get("faltan_para_meta")
            plan = fila.get("planilla_cierre") or {}
            writer.writerow([
                canal, camada, boleta, meta["fecha_corte"] or "", meta["archivo"],
                fila.get("supervisor") or "", fila.get("rut") or "", fila.get("nombre") or "",
                fila.get("pagadas", 0), fila.get("pendientes", 0), fila.get("no_pago", 0),
                fila.get("fuera_plazo", 0), fila.get("sin_boleta", 0),
                plan.get("n_d", 0), fila.get("fuera_medicion", 0),
                fila.get("total") if fila.get("total") is not None else "",
                "" if crm_pct is None else f'{float(crm_pct):.2f}',
                plan.get("total_general", 0),
                f'{float(plan.get("kpi_pct") or 0):.2f}',
                f'{float(fila.get("meta_pct") or 0):.2f}',
                "" if q_meta is None else q_meta, "CIERRE OFICIAL",
            ])
        return response

    if canal == "FIJO":
        from integraciones.cierre_fijo_snapshot import asegurar_snapshot_cierre_fijo

        carga = detalle["cierre"]
        carga_obj = CargaExcel.objects.get(pk=carga_id)
        asegurar_snapshot_cierre_fijo(carga_obj, boleta, camada)
        qs = KPICierreFijoFila.objects.filter(
            carga_id=carga_id, camada=camada, boleta=boleta
        ).order_by("supervisor_fuente", "nombre_evt", "fila_fuente")
        writer.writerow([
            "Canal", "Mes", "Boleta", "Fila fuente", "N pedido", "RUT ejecutivo ESACOM",
            "Ejecutivo ESACOM", "Supervisor ESACOM", "Tipo KPI", "RGU ESACOM",
            "Estado KPI cierre", "Categoria cierre", "Fuente poblacion",
        ])
        for r in qs:
            writer.writerow([
                canal, camada, boleta, r.fila_fuente, r.n_pedido, r.rut_evt,
                r.nombre_evt, r.supervisor_fuente, r.tipo_kpi, r.rgu,
                r.estado_kpi, r.get_categoria_display(), r.fuente_poblacion,
            ])
    else:
        qs = KPICierreResumen.objects.filter(carga_id=carga_id, camada=camada, boleta=boleta).select_related(
            "ejecutivo", "ejecutivo__supervisor"
        ).order_by("rut_vendedor_fuente")
        writer.writerow([
            "Canal", "Mes", "Boleta", "RUT vendedor", "Ejecutivo", "Supervisor",
            "Pago", "Pendiente", "No Pago", "Fuera plazo", "S/B", "Total medible",
            "KPI pago %", "Meta Claro %", "Referencia Claro %",
        ])
        for r in qs:
            e = r.ejecutivo
            sup = e.supervisor if e and e.supervisor_id else None
            writer.writerow([
                canal, camada, boleta, r.rut_vendedor_fuente, e.nombre if e else "",
                sup.nombre if sup else "", r.pagadas, r.pendientes, r.no_pago, r.fuera_plazo,
                r.sin_boleta, r.total_medible, r.kpi_pago_pct, r.meta_claro_pct or "", r.cierre_claro_pct or "",
            ])
    return response

def _ventas_visibles(user):
    """Mismo alcance por rol que VentaViewSet."""
    ventas = Venta.objects.select_related("ejecutivo", "ejecutivo_ce", "promocion", "comuna")
    return _scope_ventas_qs(ventas, user)


@api_view(["GET"])
@permission_classes([PuedeMiEquipo])
def resumen_equipo_view(request):
    """GET /api/equipo/resumen/ -- cabecera del Portal Supervisor.

    La cantidad de ejecutivos representa la DOTACIÃ“N ASIGNADA al Supervisor,
    no solamente quienes tienen ventas en la cartera visible. Esto evita que
    el dashboard muestre, por ejemplo, 23 vendedores cuando la dotaciÃ³n real
    son 25 (17 Regular + 8 Honorarios).
    """
    data = resumen_equipo(_ventas_visibles(request.user))
    if request.user.es_supervisor:
        from ventas.produccion import resumen_produccion_actual, resumen_produccion_mes
        from integraciones.models import CargaExcel

        equipo = Ejecutivo.objects.filter(
            cargo=Ejecutivo.Cargo.EJECUTIVO, supervisor=request.user, is_active=True
        )
        mes_actual = timezone.localdate().strftime("%Y-%m")
        produccion_equipo_mes = resumen_produccion_mes(mes=mes_actual, supervisor=request.user)
        produccion_supervisor_mes = resumen_produccion_mes(mes=mes_actual, ejecutivo=request.user)
        actividad_equipo_mes = _resumen_ventas_mes(_ventas_visibles(request.user), mes_actual)
        control_operativo_equipo = resumen_produccion_actual(supervisor=request.user)
        control_operativo_supervisor = resumen_produccion_actual(ejecutivo=request.user)
        ventas_propias = Venta.objects.filter(ejecutivo=request.user)
        actividad_supervisor_mes = _resumen_ventas_mes(ventas_propias, mes_actual)
        ultima_esacom = CargaExcel.objects.filter(
            tipo_base__in=[CargaExcel.TipoBase.BASE_MATRIZ, CargaExcel.TipoBase.ANDES]
        ).order_by("-creado_en").first()

        data.update({
            "ejecutivos_con_ventas": data.get("ejecutivos", 0),
            "ejecutivos": equipo.count(),
            "ejecutivos_asignados": equipo.count(),
            "ejecutivos_regulares": equipo.filter(tipo_kpi=Ejecutivo.TipoKPI.REGULAR).count(),
            "ejecutivos_honorarios": equipo.filter(tipo_kpi=Ejecutivo.TipoKPI.HONORARIOS).count(),
            "mes_actual": mes_actual,
            "produccion_equipo_mes": produccion_equipo_mes,
            "produccion_supervisor_mes": produccion_supervisor_mes,
            "control_operativo_equipo": control_operativo_equipo,
            "control_operativo_supervisor": control_operativo_supervisor,
            "actividad_equipo_mes": actividad_equipo_mes,
            "actividad_supervisor_mes": actividad_supervisor_mes,
            "ultima_carga_esacom": ultima_esacom.creado_en.isoformat() if ultima_esacom else None,
        })
    return Response(data)


@api_view(["GET"])
@permission_classes([PuedeAccionables])
def dashboard_accionables(request):
    """GestiÃ³n diaria de todas las camadas B1 que siguen oficialmente abiertas."""
    ultima = _ultima_carga_kpi_activa()
    camadas_abiertas = _camadas_b1_abiertas()

    cortes = _cortes_visibles(request.user).filter(
        boleta=Corte.Boleta.B1,
        mes_ano__in=camadas_abiertas,
    )
    data = resumen_accionables(cortes, focos={}) if camadas_abiertas else resumen_accionables(cortes.none(), focos={})
    data["focos"] = {"B1": camadas_abiertas[0]} if camadas_abiertas else {}
    data["camadas_abiertas"] = camadas_abiertas
    data["snapshot"] = {
        "archivo_nombre": ultima.archivo_nombre,
        "fecha_reporte": (fecha_reporte_desde_nombre(ultima.archivo_nombre).isoformat() if ultima and fecha_reporte_desde_nombre(ultima.archivo_nombre) else None),
        "fecha_corte": ultima.fecha_corte.isoformat() if ultima and ultima.fecha_corte else None,
        "dia_reporte": ultima.dia_reporte,
    } if ultima else None
    return Response(data)


@api_view(["GET"])
@permission_classes([PuedeHistorico])
def dashboard_historico(request):
    """
    GET /api/dashboard/historico/ -- pantalla 'HistÃ³rico': comparativo
    mes a mes de ventas cargadas y su estado de pago, para ver la
    tendencia (este mes vs. el anterior, etc). Mismo alcance por rol.
    """
    return Response({"camadas": resumen_historico_camadas(_ventas_visibles(request.user))})

