from django.db import models

from catalogos.models import Comuna, Promocion
from usuarios.models import Ejecutivo


class Venta(models.Model):
    """
    De la hoja 'Base de Ventas' / 'Ventas Móvil'.
    Corazón del sistema: una venta = un pedido, con su ejecutivo,
    promoción vendida y estado de instalación.
    """

    class TipoCliente(models.TextChoices):
        B2C = "B2C", "B2C"
        B2B = "B2B", "B2B"

    class EstadoInstalacion(models.TextChoices):
        INSTALADO = "INSTALADO", "Instalado"
        PENDIENTE_COMERCIAL = "PENDIENTE_COMERCIAL", "Pendiente comercial"
        PENDIENTE_INSTALACION = "PENDIENTE_INSTALACION", "Pendiente instalación"
        ANULADO = "ANULADO", "Anulado"

    class OrigenVenta(models.TextChoices):
        BASE_VENTAS = "BASE_VENTAS", "Base de Ventas ESACOM"
        HONORARIOS = "HONORARIOS", "Honorarios ESACOM"

    rut_cliente = models.CharField(max_length=20, db_index=True)
    nombre_cliente = models.CharField(max_length=200, blank=True)
    telefono_cliente = models.CharField(max_length=20, blank=True)
    n_pedido = models.CharField(max_length=30, unique=True, db_index=True)
    rut_evt = models.CharField(max_length=12, blank=True, db_index=True)
    nombre_evt = models.CharField(max_length=150, blank=True, db_index=True)
    origen_venta = models.CharField(
        max_length=20, choices=OrigenVenta.choices, default=OrigenVenta.BASE_VENTAS, db_index=True
    )
    # Trazabilidad de la hoja operacional ESACOM. ``en_base_vigente`` permite
    # reproducir exactamente los pivots de la hoja "Base de Ventas" actual
    # sin confundirlos con los respaldos históricos BV/BDVentas.
    supervisor_fuente = models.CharField(max_length=150, blank=True, db_index=True)
    estado_instalacion_fuente = models.CharField(max_length=100, blank=True)
    hoja_fuente = models.CharField(max_length=100, blank=True)
    en_base_vigente = models.BooleanField(default=False, db_index=True)
    conflicto_fuente = models.BooleanField(
        default=False, db_index=True,
        help_text="True cuando Base de Ventas trae más de una fila del mismo pedido con datos operacionales incompatibles.",
    )
    detalle_conflicto_fuente = models.JSONField(
        default=dict, blank=True,
        help_text="Trazabilidad del conflicto detectado en la matriz ESACOM; no se usa para reasignar la venta.",
    )
    fecha_pago_honorarios = models.DateField(null=True, blank=True)

    # ESACOM define al dueño de la venta por RUT EVT. CE/propietario final
    # se conserva únicamente para comparación y auditoría contra Claro.
    rut_ce = models.CharField(max_length=12, blank=True, db_index=True)
    codigo_ce = models.CharField(max_length=30, blank=True, db_index=True)
    rgu_base = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="RGU informado por la Base de Ventas de ESACOM."
    )

    ejecutivo = models.ForeignKey(
        Ejecutivo, on_delete=models.SET_NULL, null=True, blank=True, related_name="ventas",
        help_text="EVT original. Puede faltar en respaldos históricos incompletos.",
    )
    ejecutivo_ce = models.ForeignKey(
        Ejecutivo, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="ventas_como_ce",
        help_text="CE/propietario final informado en la base; no cambia al dueño ESACOM de la venta.",
    )
    promocion = models.ForeignKey(
        Promocion, on_delete=models.PROTECT, related_name="ventas"
    )
    comuna = models.ForeignKey(
        Comuna, on_delete=models.SET_NULL, null=True, blank=True, related_name="ventas"
    )

    tipo_cliente = models.CharField(max_length=3, choices=TipoCliente.choices, default=TipoCliente.B2C)
    estado_instalacion = models.CharField(
        max_length=25, choices=EstadoInstalacion.choices, default=EstadoInstalacion.PENDIENTE_INSTALACION
    )
    motivo_pendiente = models.CharField(max_length=500, blank=True)

    fecha_venta = models.DateField()
    primera_agenda = models.DateField(null=True, blank=True)
    segunda_agenda = models.DateField(null=True, blank=True)
    fecha_cierre = models.DateField(null=True, blank=True)

    precio_venta = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True)
    honorarios = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True)
    ingresador = models.CharField(max_length=100, blank=True)

    camada = models.CharField(max_length=7, help_text="Mes de la venta, ej. '2026-08'", db_index=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Venta"
        verbose_name_plural = "Ventas"
        ordering = ["-fecha_venta"]
        indexes = [models.Index(fields=["camada", "ejecutivo"])]

    def __str__(self):
        return f"Pedido {self.n_pedido} — {self.rut_cliente}"


class VentaFijaFuente(models.Model):
    """Fila operacional exacta de la hoja vigente ``Base de Ventas``.

    ``Venta`` sigue representando el pedido único para cruces KPI. Esta tabla
    conserva la granularidad de la matriz ESACOM, porque un mismo N° PEDIDO
    puede aparecer en más de una fila e incluso con estados distintos. La
    producción de Gerencia se calcula desde estas filas, igual que el pivot.
    """

    fila_fuente = models.PositiveIntegerField()
    hoja_fuente = models.CharField(max_length=100, default="Base de Ventas")
    en_base_vigente = models.BooleanField(default=True, db_index=True)

    n_pedido = models.CharField(max_length=30, blank=True, db_index=True)
    rut_evt = models.CharField(max_length=12, blank=True, db_index=True)
    nombre_evt = models.CharField(max_length=150, blank=True, db_index=True)
    supervisor_fuente = models.CharField(max_length=150, blank=True, db_index=True)
    estado_instalacion_fuente = models.CharField(max_length=100, blank=True)
    rgu_base = models.PositiveSmallIntegerField(null=True, blank=True)
    fecha_venta = models.DateField(null=True, blank=True)
    promocion_fuente = models.CharField(max_length=200, blank=True)

    ejecutivo = models.ForeignKey(
        Ejecutivo, on_delete=models.SET_NULL, null=True, blank=True, related_name="filas_fijas_fuente"
    )
    venta = models.ForeignKey(
        Venta, on_delete=models.SET_NULL, null=True, blank=True, related_name="filas_fuente"
    )

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Fila fija ESACOM"
        verbose_name_plural = "Filas fijas ESACOM"
        ordering = ["fila_fuente"]
        constraints = [
            models.UniqueConstraint(
                fields=["hoja_fuente", "fila_fuente", "en_base_vigente"],
                name="venta_fija_fuente_fila_vig_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["en_base_vigente", "supervisor_fuente"], name="vf_fuente_vig_sup_idx"),
            models.Index(fields=["en_base_vigente", "rut_evt"], name="vf_fuente_vig_rut_idx"),
        ]

    def __str__(self):
        return f"Base de Ventas fila {self.fila_fuente} · {self.n_pedido or 'sin pedido'}"


class VentaMovil(models.Model):
    """Línea móvil vendida en la fuente ESACOM (hoja ``Ventas Móvil``).

    Se mantiene separada de :class:`Venta` porque móvil no usa N° de pedido y
    su unidad operacional es la línea/PCS. La pertenencia comercial se resuelve
    por RUT EVT de ESACOM; supervisor/nombre del archivo se conservan para
    auditoría contra los pivots manuales.
    """

    class TipoLinea(models.TextChoices):
        PRINCIPAL = "PRINCIPAL", "Principal"
        ADICIONAL = "ADICIONAL", "Adicional"
        PPM = "PPM", "PPM"
        OTRO = "OTRO", "Otro"

    clave_origen = models.CharField(max_length=64, unique=True, db_index=True)
    rut_cliente = models.CharField(max_length=12, blank=True, db_index=True)
    supervisor_fuente = models.CharField(max_length=150, blank=True, db_index=True)
    nombre_evt = models.CharField(max_length=150, blank=True, db_index=True)
    rut_evt_ingreso = models.CharField(max_length=12, blank=True, db_index=True)
    codigo_ingreso = models.CharField(max_length=30, blank=True)
    rut_evt = models.CharField(max_length=12, blank=True, db_index=True)
    ejecutivo = models.ForeignKey(
        Ejecutivo, on_delete=models.SET_NULL, null=True, blank=True, related_name="ventas_movil"
    )

    migracion = models.CharField(max_length=100, blank=True)
    tipo_linea = models.CharField(max_length=15, choices=TipoLinea.choices, default=TipoLinea.OTRO, db_index=True)
    plan = models.CharField(max_length=150, blank=True)
    pcs = models.CharField(max_length=30, blank=True, db_index=True)
    fecha_venta = models.DateField(null=True, blank=True, db_index=True)
    fecha_activacion = models.DateField(null=True, blank=True)
    donante = models.CharField(max_length=100, blank=True)
    estado = models.CharField(max_length=100, blank=True, db_index=True)
    observacion = models.CharField(max_length=250, blank=True)
    fecha_cc = models.DateField(null=True, blank=True)

    camada = models.CharField(max_length=7, blank=True, db_index=True)
    hoja_fuente = models.CharField(max_length=100, blank=True)
    en_base_vigente = models.BooleanField(default=False, db_index=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Venta móvil"
        verbose_name_plural = "Ventas móviles"
        ordering = ["-fecha_venta", "nombre_evt"]
        indexes = [models.Index(fields=["en_base_vigente", "supervisor_fuente"], name="ventas_movil_vig_sup_idx")]

    def __str__(self):
        return f"Móvil {self.pcs or self.rut_cliente} · {self.nombre_evt}"


class Corte(models.Model):
    """
    Reemplaza el patrón de 'una pestaña por mes' (BV202601, BV202602...).
    Cada boleta (B1/B2/B3) de una venta es una fila con fecha propia,
    en vez de una copia completa de la base cada mes.
    """

    class Boleta(models.TextChoices):
        B1 = "B1", "1ª Boleta"
        B2 = "B2", "2ª Boleta"
        B3 = "B3", "3ª Boleta"

    class EstadoPago(models.TextChoices):
        PAGADO = "PAGADO", "Pagado"
        PENDIENTE = "PENDIENTE", "Pendiente"
        NO_PAGO = "NO_PAGO", "No Pago"
        FUERA_PLAZO = "FUERA_PLAZO", "Pagado Fuera de Plazo"
        SIN_BOLETA = "SIN_BOLETA", "Sin Boleta (S/B)"

    class EstadoCalculado(models.TextChoices):
        PAGADO = "PAGADO", "Pagado"
        PENDIENTE = "PENDIENTE", "Pendiente"
        NO_PAGO = "NO_PAGO", "No Pago"
        FUERA_PLAZO = "FUERA_PLAZO", "Pagado Fuera de Plazo"
        SIN_BOLETA = "SIN_BOLETA", "Sin Boleta (S/B)"
        FUERA_MEDICION = "FUERA_MEDICION", "Fuera de medición"

    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name="cortes")
    boleta = models.CharField(max_length=2, choices=Boleta.choices)
    mes_ano = models.CharField(max_length=7, help_text="Mes evaluado, ej. '2026-08'")

    meta_pct = models.DecimalField(max_digits=5, decimal_places=2, help_text="Meta vigente para este corte, ej. 85.00")
    estado_pago = models.CharField(max_length=15, choices=EstadoPago.choices, default=EstadoPago.PENDIENTE)

    fecha_vencimiento = models.DateField(null=True, blank=True)
    fecha_pago = models.DateField(null=True, blank=True)
    fecha_limite_medicion = models.DateField(
        null=True, blank=True, help_text="Fecha de vencimiento + 8 días según regla de medición Claro."
    )
    es_medible = models.BooleanField(
        default=True, db_index=True,
        help_text="False cuando fecha_vencimiento + 8 días queda después de la fecha de corte del reporte."
    )
    marca_mes_kpi = models.SmallIntegerField(
        null=True, blank=True, db_index=True,
        help_text="Marca de mes oficial del reporte Claro: 1 entra al foco KPI; 0 queda fuera de medición."
    )
    carga_kpi = models.ForeignKey(
        "integraciones.CargaExcel", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="cortes_vigentes", db_index=True,
        help_text="Último snapshot KPI de Claro en el que esta fila estuvo presente. Evita mezclar filas obsoletas de cargas anteriores.",
    )
    estado_calculado = models.CharField(
        max_length=20, blank=True, choices=EstadoCalculado.choices,
        help_text="Validación ESACOM calculada sin sobrescribir el estado original informado por Claro."
    )

    # NP8+2 (Hogar) / NP8+3 (Móvil), calculado en base a fecha_vencimiento + fecha_pago
    dias_diferencia = models.SmallIntegerField(null=True, blank=True)

    # --- Verificación de Cobranza (reunión 14/08) ------------------------
    # `estado_claro`: último estado que Claro reportó para este corte.
    # El historial por archivo queda en integraciones.KPIRegistro.
    # `estado_pago`: el estado OPERATIVO que usa el cálculo de KPI y el
    # dashboard. Empieza igual a estado_claro, pero Cobranza lo puede
    # corregir a mano después de verificar en el portal de pago o en la
    # app Andes -- ese es el estado que se considera "la verdad" para
    # efectos internos, aunque Claro todavía no lo haya actualizado.
    estado_claro = models.CharField(
        max_length=15, blank=True, choices=EstadoPago.choices,
        help_text="Último estado reportado por Claro. El historial por carga queda en KPIRegistro.",
    )
    verificado_en_andes = models.BooleanField(default=False)
    fecha_verificacion_andes = models.DateTimeField(null=True, blank=True)
    verificado_por = models.ForeignKey(
        "usuarios.Ejecutivo", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="cortes_verificados",
    )

    # Informativos, calculados por Claro y traídos tal cual del reporte KPI
    # (no se recalculan localmente para poder auditar contra la fuente).
    rango_pago = models.CharField(
        max_length=40, blank=True,
        help_text="Bucket de urgencia de Claro: Pago / Gestionar vence 0-7 / Vencido 0-8 / etc.",
    )
    apelacion_claro = models.SmallIntegerField(
        null=True, blank=True, help_text="Código 0/1/2 que trae el reporte de Claro (distinto de nuestra tabla Apelacion)."
    )

    # Datos promovidos del KPI de Claro. Se guardan en Corte porque son
    # los valores vigentes que alimentan el dashboard. El historial crudo
    # de cada lunes/miércoles queda en integraciones.KPIRegistro.
    rgu_kpi = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="RGU reportado por Claro para esta camada/boleta."
    )
    propietario_final = models.CharField(max_length=50, blank=True, db_index=True)
    rut_propietario_final = models.CharField(max_length=20, blank=True)
    ejecutivo_kpi = models.ForeignKey(
        "usuarios.Ejecutivo", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="cortes_kpi",
        help_text="Ejecutivo interpretado desde Claro solo para auditoría; la atribución del dashboard usa Venta.ejecutivo (RUT EVT ESACOM).",
    )
    bill_no = models.CharField(max_length=50, blank=True)
    monto_boleta = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    monto_pago = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Corte"
        verbose_name_plural = "Cortes"
        constraints = [
            models.UniqueConstraint(
                fields=["venta", "mes_ano", "boleta"],
                name="uniq_corte_venta_camada_boleta",
            )
        ]
        ordering = ["venta", "mes_ano", "boleta"]
        indexes = [models.Index(fields=["mes_ano", "boleta", "estado_pago"], name="ventas_cort_mes_ano_97858a_idx")]

    def __str__(self):
        return f"{self.venta.n_pedido} · {self.boleta} · {self.mes_ano}"

    def boleta_previa_cumplida(self) -> bool:
        """Regla de correlatividad: B2 exige B1 pagada, B3 exige B1 y B2 pagadas."""
        orden = ["B1", "B2", "B3"]
        idx = orden.index(self.boleta)
        if idx == 0:
            return True
        previas = self.venta.cortes.filter(mes_ano=self.mes_ano, boleta__in=orden[:idx])
        return all(c.estado_pago in [self.EstadoPago.PAGADO] for c in previas)

    @property
    def extension_np8(self) -> int:
        """
        DEPRECADA desde la reunión del 14/08/26: se confirmó que el día 8
        es el corte real (sin extensión NP8+2/+3 del documento de criterios
        de apelación, que aplicaba a otro caso o quedó obsoleto). Se deja
        el método solo para no romper código viejo que aún la referencie;
        ya no se usa en `limite_pago` ni en el motor de detección.
        """
        promo = self.venta.promocion
        es_hogar = promo.tiene_internet or promo.tiene_tv or promo.tiene_fono
        return 2 if es_hogar else 3

    @property
    def dias_vencido(self) -> int | None:
        """Días transcurridos desde el vencimiento (negativo = todavía no vence)."""
        if not self.fecha_vencimiento:
            return None
        import datetime
        return (datetime.date.today() - self.fecha_vencimiento).days

    @property
    def esta_muerto(self) -> bool:
        """
        Para boletas SIN fecha_pago todavía: si ya vencieron hace más de
        8 días, quedan sin esperanza de pago a tiempo (útil para marcar
        casos perdidos en el dashboard/Accionables). No usar esto para
        evaluar si un pago YA ocurrido es apelable -- para eso importa
        la distancia entre fecha_pago y fecha_vencimiento, no la fecha
        de hoy (ver ventas/apelaciones.py::_regla_a_correccion_estado).
        """
        dias = self.dias_vencido
        return dias is not None and dias > 8

    @property
    def limite_pago(self):
        """
        Fecha límite real de pago: vencimiento + 8 días, sin extensión
        (confirmado en reunión 14/08/26 -- ver `extension_np8`). Es la
        columna 'LÍMITE (+8D)' del mockup de apelaciones.
        """
        if not self.fecha_vencimiento:
            return None
        import datetime
        return self.fecha_vencimiento + datetime.timedelta(days=8)


class MetaKPI(models.Model):
    """
    Metas por corte, como las que llegan cada mes en el correo de
    directrices ('Metas de Calidad de este Mes'). Se editan desde el
    Admin -- no van hardcodeadas en el código porque cambian mes a mes.
    """

    class Canal(models.TextChoices):
        FIJO = "FIJO", "Fijo"
        MOVIL = "MOVIL", "Móvil"

    mes_ano = models.CharField(max_length=7, help_text="Ej. '2026-08'", db_index=True)
    boleta = models.CharField(max_length=2, choices=Corte.Boleta.choices)
    canal = models.CharField(max_length=5, choices=Canal.choices, default=Canal.FIJO)
    tipo_cliente = models.CharField(max_length=3, choices=Venta.TipoCliente.choices, default=Venta.TipoCliente.B2C)
    meta_pct = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        verbose_name = "Meta KPI"
        verbose_name_plural = "Metas KPI"
        unique_together = ("mes_ano", "boleta", "canal", "tipo_cliente")
        ordering = ["-mes_ano", "boleta"]

    def __str__(self):
        return f"{self.mes_ano} · {self.boleta} · {self.canal}/{self.tipo_cliente} · {self.meta_pct}%"



class Apelacion(models.Model):
    """
    Motor de apelaciones, según 'Criterios de Apelación — KPI Calidad de Ventas' (vigente jul-2026).
    """

    class Motivo(models.TextChoices):
        ACREDITACION = "ACREDITACION", "Apelación por acreditación"
        APROVISIONAMIENTO = "APROVISIONAMIENTO", "Aprovisionamiento y facturación"
        SUSPENSION = "SUSPENSION", "Cliente suspendido o desconectado"

    class Estado(models.TextChoices):
        DETECTADA = "DETECTADA", "Detectada"
        EXCLUIDA = "EXCLUIDA", "Excluida manualmente"
        ENVIADA = "ENVIADA", "Enviada a Claro"
        APROBADA_EN_PLAZO = "APROBADA_EN_PLAZO", "Aprobada — Pagado en Plazo"
        APROBADA_FUERA_PLAZO = "APROBADA_FUERA_PLAZO", "Aprobada — Pagado Fuera de Plazo"
        RECHAZADA = "RECHAZADA", "Rechazada — Pagado Fuera de Plazo"

    corte = models.OneToOneField(Corte, on_delete=models.CASCADE, related_name="apelacion")
    motivo = models.CharField(max_length=20, choices=Motivo.choices)
    estado = models.CharField(max_length=25, choices=Estado.choices, default=Estado.DETECTADA)

    observacion = models.TextField(blank=True)
    bill_no = models.CharField(max_length=30, blank=True)

    fecha_deteccion = models.DateTimeField(auto_now_add=True)
    fecha_envio = models.DateTimeField(null=True, blank=True)
    fecha_respuesta = models.DateTimeField(null=True, blank=True)

    excluida_por = models.ForeignKey(
        Ejecutivo, on_delete=models.SET_NULL, null=True, blank=True, related_name="apelaciones_excluidas"
    )

    class Meta:
        verbose_name = "Apelación"
        verbose_name_plural = "Apelaciones"
        ordering = ["-fecha_deteccion"]

    def __str__(self):
        return f"Apelación {self.corte} — {self.get_estado_display()}"


class Gestion(models.Model):
    """
    Registro de contacto con el cliente (Llamar / WhatsApp) desde el
    Portal Ejecutivo -- 'Deja constancia de llamadas y mensajes a
    clientes para trazabilidad', según el mockup.
    """

    class Tipo(models.TextChoices):
        LLAMADA = "LLAMADA", "Llamada"
        WHATSAPP = "WHATSAPP", "WhatsApp"
        OTRO = "OTRO", "Otro"

    class Resultado(models.TextChoices):
        CONTACTADO = "CONTACTADO", "Contactado"
        NO_CONTESTA = "NO_CONTESTA", "No contesta"
        COMPROMISO_PAGO = "COMPROMISO_PAGO", "Compromiso de pago"
        NUMERO_INVALIDO = "NUMERO_INVALIDO", "Número inválido"
        REAGENDAR = "REAGENDAR", "Reagendar"
        OTRO = "OTRO", "Otro"

    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name="gestiones")
    ejecutivo = models.ForeignKey(Ejecutivo, on_delete=models.CASCADE, related_name="gestiones")
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    resultado = models.CharField(max_length=20, choices=Resultado.choices, blank=True)
    nota = models.CharField(max_length=500, blank=True)
    proximo_contacto = models.DateTimeField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Gestión"
        verbose_name_plural = "Gestiones"
        ordering = ["-creado_en"]

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.venta.rut_cliente} · {self.creado_en:%d/%m/%Y %H:%M}"
