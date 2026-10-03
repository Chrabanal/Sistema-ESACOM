"""
Arma el archivo de apelación (mismo formato de columnas que la tabla
del mockup 'Seguimiento apelaciones') y envía el correo a Claro.
"""
from __future__ import annotations

import io

import openpyxl
from django.conf import settings
from django.core.mail import EmailMessage

from .models import Apelacion

COLUMNAS = [
    "CONDICIÓN", "PEDIDO", "RUT", "EVT", "CAMADA", "BOLETA", "ESTADO KPI",
    "FECHA PAGO", "VENCIMIENTO", "MOTIVO / OBSERVACIÓN", "BILL_NO",
]


def generar_archivo_apelaciones(apelaciones: list[Apelacion]) -> io.BytesIO:
    """Excel con una fila por apelación, formato ESACOM para radicar con el operador."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Apelaciones"
    ws.append(COLUMNAS)

    for a in apelaciones:
        corte = a.corte
        venta = corte.venta
        ws.append([
            a.get_motivo_display(),
            venta.n_pedido,
            venta.rut_cliente,
            venta.nombre_evt,
            corte.mes_ano,
            corte.boleta,
            corte.get_estado_pago_display(),
            corte.fecha_pago.isoformat() if corte.fecha_pago else "",
            corte.fecha_vencimiento.isoformat() if corte.fecha_vencimiento else "",
            a.observacion,
            a.bill_no,
        ])

    for col in ws.columns:
        largo = max(len(str(c.value)) for c in col if c.value) if any(c.value for c in col) else 10
        ws.column_dimensions[col[0].column_letter].width = min(largo + 2, 50)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def enviar_apelacion_por_correo(apelacion: Apelacion) -> None:
    """Envía UNA apelación por correo. Usado por el botón 'Enviar a Claro' manual."""
    enviar_apelaciones_por_correo([apelacion])


def enviar_apelaciones_por_correo(apelaciones: list[Apelacion]) -> None:
    """Envía un correo con todas las apelaciones dadas, adjuntas en un solo Excel."""
    if not apelaciones:
        return
    if not settings.APELACIONES_EMAIL_TO:
        raise ValueError(
            "No hay destinatarios configurados para apelaciones. Define APELACIONES_EMAIL_TO en el .env."
        )

    archivo = generar_archivo_apelaciones(apelaciones)
    n_pedidos = ", ".join(a.corte.venta.n_pedido for a in apelaciones[:5])
    if len(apelaciones) > 5:
        n_pedidos += f" y {len(apelaciones) - 5} más"

    mensaje = EmailMessage(
        subject=f"Apelaciones ESACOM — {len(apelaciones)} caso(s) — {apelaciones[0].corte.mes_ano}",
        body=(
            f"Se adjuntan {len(apelaciones)} apelación(es) para revisión.\n\n"
            f"Pedidos incluidos: {n_pedidos}\n\n"
            f"Generado automáticamente por ESACOM CRM."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=settings.APELACIONES_EMAIL_TO,
    )
    mensaje.attach(
        f"apelaciones_esacom_{apelaciones[0].corte.mes_ano}.xlsx",
        archivo.getvalue(),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    mensaje.send()
