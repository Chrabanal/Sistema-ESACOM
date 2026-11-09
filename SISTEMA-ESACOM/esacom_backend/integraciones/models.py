from django.db import models

from usuarios.models import Ejecutivo


class ClaroImport(models.Model):
    """
    De la hoja 'Base Claro' / 'Móvil Claro': export crudo que Claro entrega.
    Se guardan solo los campos que activamente se usan para el cruce;
    el resto del registro (hasta 132 columnas en el export real) se
    conserva íntegro en `raw_data` para no perder información.
    """

    num_pedido = models.CharField(max_length=30, db_index=True)
    rgu = models.PositiveSmallIntegerField(null=True, blank=True)
    codigo_claro = models.CharField(max_length=30, blank=True)
    ingresador = models.CharField(max_length=100, blank=True)
    estado_pedido = models.CharField(max_length=50, blank=True)
    fecha_creacion = models.DateField(null=True, blank=True)

    raw_data = models.JSONField(help_text="Registro completo tal como llegó de Claro.")
    cruce_ok = models.BooleanField(default=False, help_text="True si encontró match en Venta por n_pedido.")

    carga = models.ForeignKey(
        "CargaExcel", on_delete=models.CASCADE, related_name="registros_claro", null=True, blank=True
    )
    importado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Registro Claro"
        verbose_name_plural = "Registros Claro"
        indexes = [models.Index(fields=["num_pedido"])]

    def __str__(self):
        return f"Claro · {self.num_pedido}"


class CargaExcel(models.Model):
    """Log de cada importación — manual o automática (Google Sheets)."""

    class Origen(models.TextChoices):
        MANUAL = "MANUAL", "Carga manual"
        AUTOMATICO_SHEETS = "AUTOMATICO_SHEETS", "Automático (Google Sheets)"

    class TipoBase(models.TextChoices):
        BASE_MATRIZ = "BASE_MATRIZ", "Base matriz"
        REPORTE_CLARO = "REPORTE_CLARO", "Reporte Claro"
        REPORTE_KPI = "REPORTE_KPI", "Reporte KPI"
        ANDES = "ANDES", "Andes"

    class DiaReporte(models.TextChoices):
        LUNES = "LUNES", "Lunes"
        MIERCOLES = "MIERCOLES", "Miércoles"
        JUEVES = "JUEVES", "Jueves"
        OTRO = "OTRO", "Otro"

    class EstadoReporte(models.TextChoices):
        AVANCE = "AVANCE", "Avance"
        CIERRE = "CIERRE", "Cierre"

    class FormatoKPI(models.TextChoices):
        DETALLADO = "DETALLADO", "Avance detallado Claro/VTR"
        AVANCE_MOVIL = "AVANCE_MOVIL", "Avance Claro Móvil"
        CIERRE_FIJO = "CIERRE_FIJO", "Cierre Claro Fijo"
        CIERRE_MOVIL = "CIERRE_MOVIL", "Cierre Claro Móvil"

    origen = models.CharField(max_length=20, choices=Origen.choices)
    tipo_base = models.CharField(max_length=20, choices=TipoBase.choices)
    archivo_nombre = models.CharField(max_length=255, blank=True)

    # Metadata del correo/reporte de Claro. `fecha_corte` es la fecha hasta
    # la que Claro considera pagos (no necesariamente la fecha del asunto).
    fecha_corte = models.DateField(null=True, blank=True)
    dia_reporte = models.CharField(max_length=12, choices=DiaReporte.choices, blank=True)
    estado_reporte = models.CharField(
        max_length=10, choices=EstadoReporte.choices, default=EstadoReporte.AVANCE, db_index=True,
        help_text="AVANCE para reportes semanales; CIERRE congela el resultado de cada camada/boleta incluida.",
    )
    formato_kpi = models.CharField(
        max_length=20, choices=FormatoKPI.choices, default=FormatoKPI.DETALLADO, db_index=True,
        help_text=(
            "DETALLADO para avances semanales Fijo con NUM_PEDIDO; AVANCE_MOVIL para avance Móvil "
            "agregado sin NUM_PEDIDO; CIERRE_FIJO para cierre oficial Fijo con NUM_PEDIDO; "
            "CIERRE_MOVIL para cierre oficial Móvil agregado sin NUM_PEDIDO."
        ),
    )
    avance_b1 = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    avance_b2 = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    avance_b3 = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    meta_b1 = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    meta_b2 = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    meta_b3 = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    foco_b1 = models.CharField(max_length=7, blank=True, help_text="Camada oficial B1 del reporte, ej. 2026-07")
    foco_b2 = models.CharField(max_length=7, blank=True, help_text="Camada oficial B2 del reporte, ej. 2026-06")
    foco_b3 = models.CharField(max_length=7, blank=True, help_text="Camada oficial B3 del reporte, ej. 2026-05")

    filas_totales = models.PositiveIntegerField(default=0)
    filas_sin_cruce = models.PositiveIntegerField(default=0)
    filas_con_error = models.PositiveIntegerField(default=0)

    # Snapshot auditable de la matriz ESACOM al momento de cada sync.
    # Permite distinguir un error del CRM de una evolución real de la Sheet
    # entre el control manual de la mañana y una consulta posterior.
    fuente_modificada_en = models.DateTimeField(null=True, blank=True)
    fuente_sha256 = models.CharField(max_length=64, blank=True)
    resumen_produccion = models.JSONField(default=dict, blank=True)

    creado_por = models.ForeignKey(
        Ejecutivo, on_delete=models.SET_NULL, null=True, blank=True, related_name="cargas"
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Carga de Excel"
        verbose_name_plural = "Cargas de Excel"
        ordering = ["-creado_en"]

    def __str__(self):
        return f"{self.get_tipo_base_display()} · {self.creado_en:%d/%m/%Y %H:%M}"


class KPIRegistro(models.Model):
    """
    Snapshot normalizado de una fila de la hoja BASE del KPI de Claro.

    Los archivos de lunes/miércoles son snapshots acumulativos: una fila
    puede volver a llegar con un estado distinto. Por eso este modelo no
    reemplaza a Corte: conserva el historial de *cada carga*, mientras
    Corte mantiene el último estado operativo para el dashboard.
    """

    carga = models.ForeignKey(CargaExcel, on_delete=models.CASCADE, related_name="registros_kpi")
    venta = models.ForeignKey(
        "ventas.Venta", on_delete=models.SET_NULL, null=True, blank=True, related_name="registros_kpi"
    )

    num_pedido = models.CharField(max_length=30, db_index=True)
    camada = models.CharField(max_length=7, db_index=True, help_text="Ej. 2026-07")
    boleta = models.CharField(max_length=2, db_index=True, help_text="B1/B2/B3")

    rut_cliente = models.CharField(max_length=20, blank=True)
    propietario_final = models.CharField(max_length=50, blank=True, db_index=True)
    rut_propietario_final = models.CharField(max_length=20, blank=True)
    supervisor_fuente = models.CharField(max_length=100, blank=True)
    ingresador = models.CharField(max_length=100, blank=True)
    comuna = models.CharField(max_length=100, blank=True)

    rgu = models.PositiveSmallIntegerField(null=True, blank=True)
    kpi_texto = models.CharField(max_length=40, blank=True)
    estado_normalizado = models.CharField(max_length=20, blank=True)
    bill_no = models.CharField(max_length=50, blank=True)
    fecha_pago = models.DateField(null=True, blank=True)
    fecha_vencimiento = models.DateField(null=True, blank=True)
    fecha_limite_medicion = models.DateField(null=True, blank=True)
    es_medible = models.BooleanField(default=True, db_index=True)
    marca_mes_kpi = models.SmallIntegerField(
        null=True, blank=True, db_index=True,
        help_text="Marca de mes original de Claro: 1 entra al foco KPI; 0 queda fuera de medición.",
    )
    estado_calculado = models.CharField(max_length=20, blank=True)
    diferencia_estado = models.BooleanField(default=False)
    monto_boleta = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    monto_pago = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    rango_pago = models.CharField(max_length=40, blank=True)
    apelacion_claro = models.SmallIntegerField(null=True, blank=True)

    # Resultado del cruce contra nuestra base ESACOM.
    cruce_ok = models.BooleanField(default=False, db_index=True)
    diferencia_rut = models.BooleanField(default=False)
    diferencia_rgu = models.BooleanField(default=False)
    diferencia_propietario = models.BooleanField(default=False)
    ejecutivo_kpi_no_resuelto = models.BooleanField(default=False)

    # Snapshot ESACOM al momento exacto de cargar este reporte KPI.
    # ESACOM es la fuente maestra de población, RGU, ejecutivo y supervisor;
    # Claro solo aporta el estado de Calidad. Este JSON evita que una sync
    # posterior de la matriz cambie retroactivamente un KPI ya cargado.
    snapshot_esacom = models.JSONField(null=True, blank=True)

    # Registro íntegro de origen para auditoría (campos extra que no
    # promovemos a columnas del sistema).
    raw_data = models.JSONField(default=dict, blank=True)
    importado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Registro KPI"
        verbose_name_plural = "Registros KPI"
        constraints = [
            models.UniqueConstraint(
                fields=["carga", "num_pedido", "camada", "boleta"],
                name="uniq_kpi_por_carga_pedido_camada_boleta",
            )
        ]
        indexes = [
            models.Index(fields=["num_pedido", "camada", "boleta"], name="integracion_num_ped_9c50e2_idx"),
            models.Index(fields=["cruce_ok", "camada", "boleta"], name="integracion_cruce_o_7a8d20_idx"),
            models.Index(fields=["carga", "camada", "boleta", "cruce_ok"], name="kpi_carga_camada_bol_ok_idx"),
            models.Index(fields=["camada", "boleta", "carga"], name="kpi_camada_bol_carga_idx"),
            models.Index(fields=["carga", "boleta", "marca_mes_kpi", "camada"], name="kpi_carga_bol_marca_cam_idx"),
        ]
        ordering = ["-importado_en", "num_pedido", "boleta"]

    @property
    def tiene_inconsistencias(self) -> bool:
        return any(
            [
                self.diferencia_rut,
                self.diferencia_rgu,
                self.diferencia_propietario,
                self.diferencia_estado,
                self.ejecutivo_kpi_no_resuelto,
            ]
        )

    def __str__(self):
        return f"KPI {self.num_pedido} · {self.camada} · {self.boleta}"


class KPICierreResumen(models.Model):
    """Resultado agregado de un reporte Claro Móvil (avance o cierre).

    Los reportes Móvil no traen NUM_PEDIDO, por lo que no deben forzarse al
    modelo KPIRegistro. Se conserva el resultado por vendedor/camada/boleta y
    un total global para auditoría. El canal Móvil permanece independiente del
    AVANCE Fijo y nunca alimenta sus accionables.
    """

    carga = models.ForeignKey(CargaExcel, on_delete=models.CASCADE, related_name="cierres_resumen")
    ejecutivo = models.ForeignKey(
        Ejecutivo, on_delete=models.SET_NULL, null=True, blank=True, related_name="cierres_kpi_calidad"
    )
    rut_vendedor_fuente = models.CharField(max_length=20, blank=True, db_index=True)
    camada = models.CharField(max_length=7, db_index=True)
    boleta = models.CharField(max_length=2, db_index=True)

    pagadas = models.PositiveIntegerField(default=0)
    pendientes = models.PositiveIntegerField(default=0)
    no_pago = models.PositiveIntegerField(default=0)
    fuera_plazo = models.PositiveIntegerField(default=0)
    sin_boleta = models.PositiveIntegerField(default=0)
    total_medible = models.PositiveIntegerField(default=0)

    kpi_pago_pct = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    meta_claro_pct = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    cierre_claro_pct = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Resumen cierre KPI"
        verbose_name_plural = "Resúmenes cierre KPI"
        constraints = [
            models.UniqueConstraint(
                fields=["carga", "rut_vendedor_fuente", "camada", "boleta"],
                name="uniq_cierre_carga_rut_cb",
            )
        ]
        indexes = [
            models.Index(fields=["camada", "boleta"], name="cierre_camada_bol_idx"),
            models.Index(fields=["ejecutivo", "camada", "boleta"], name="cierre_ejec_cb_idx"),
        ]

    def __str__(self):
        quien = self.rut_vendedor_fuente or "GLOBAL"
        return f"Cierre {self.camada} {self.boleta} · {quien}"


class KPICierreFijoFila(models.Model):
    """Fila congelada del control mensual de CIERRE Fijo para Gerencia.

    Reproduce la planilla manual ``Cierre KPI`` usando la población ESACOM
    instalada del mes de cierre y el estado original informado por Claro.
    Se guarda una sola vez por CIERRE oficial para que sincronizaciones
    posteriores de ESACOM no modifiquen el histórico.
    """

    class Categoria(models.TextChoices):
        PAGO = "PAGO", "Pago"
        NO_PAGO = "NO_PAGO", "No Pago"
        FUERA_PLAZO = "FUERA_PLAZO", "Pagado Fuera de Plazo"
        PENDIENTE = "PENDIENTE", "Pendiente"
        SIN_BOLETA = "SIN_BOLETA", "S/B"
        N_D = "N_D", "#N/D"

    carga = models.ForeignKey(
        CargaExcel, on_delete=models.CASCADE, related_name="cierre_fijo_filas"
    )
    camada = models.CharField(max_length=7, db_index=True)
    boleta = models.CharField(max_length=2, db_index=True)
    fila_fuente = models.PositiveIntegerField()

    n_pedido = models.CharField(max_length=30, blank=True, db_index=True)
    rut_evt = models.CharField(max_length=20, blank=True, db_index=True)
    nombre_evt = models.CharField(max_length=150, blank=True, db_index=True)
    supervisor_fuente = models.CharField(max_length=150, blank=True, db_index=True)
    tipo_kpi = models.CharField(max_length=20, blank=True)

    rgu = models.PositiveSmallIntegerField(default=0)
    estado_kpi = models.CharField(max_length=40, blank=True)
    categoria = models.CharField(max_length=20, choices=Categoria.choices, db_index=True)
    fuente_poblacion = models.CharField(max_length=30, default="VENTA_FIJA_FUENTE")
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Fila cierre KPI Fijo"
        verbose_name_plural = "Filas cierre KPI Fijo"
        constraints = [
            models.UniqueConstraint(
                fields=["carga", "camada", "boleta", "fila_fuente"],
                name="uniq_cierre_fijo_fila_snapshot",
            )
        ]
        indexes = [
            models.Index(fields=["carga", "camada", "boleta"], name="cierre_fijo_carga_cb_idx"),
            models.Index(fields=["supervisor_fuente", "camada"], name="cierre_fijo_sup_mes_idx"),
            models.Index(fields=["rut_evt", "camada"], name="cierre_fijo_rut_mes_idx"),
        ]
        ordering = ["supervisor_fuente", "nombre_evt", "fila_fuente"]

    def __str__(self):
        return f"Cierre Fijo {self.camada} {self.boleta} · {self.nombre_evt or self.n_pedido}"


class MetaKPICalidad(models.Model):
    """Vigencias de meta ESACOM para KPI Calidad por boleta.

    La meta se resuelve según la camada mensual evaluada. Cada cambio crea una
    nueva vigencia; no se editan ni eliminan vigencias anteriores para evitar
    modificar retroactivamente meses ya cerrados.
    """

    vigente_desde = models.CharField(
        max_length=7, unique=True, db_index=True,
        help_text="Camada desde la que aplica, formato YYYY-MM.",
    )
    meta_b1 = models.DecimalField(max_digits=5, decimal_places=2)
    meta_b2 = models.DecimalField(max_digits=5, decimal_places=2)
    meta_b3 = models.DecimalField(max_digits=5, decimal_places=2)
    motivo = models.CharField(max_length=250, blank=True)
    creado_por = models.ForeignKey(
        Ejecutivo, on_delete=models.SET_NULL, null=True, blank=True, related_name="metas_kpi_calidad_creadas"
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Meta KPI Calidad"
        verbose_name_plural = "Metas KPI Calidad"
        ordering = ["-vigente_desde", "-creado_en"]

    def __str__(self):
        return f"KPI Calidad desde {self.vigente_desde}: B1 {self.meta_b1}% · B2 {self.meta_b2}% · B3 {self.meta_b3}%"
