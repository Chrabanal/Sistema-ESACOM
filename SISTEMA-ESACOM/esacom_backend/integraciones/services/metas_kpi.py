from __future__ import annotations

import re
from decimal import Decimal

from integraciones.models import MetaKPICalidad


_CAMADA_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def camada_valida(camada: str) -> bool:
    return bool(_CAMADA_RE.match(str(camada or "")))


def meta_calidad_para(*, boleta: str, camada: str, fallback=None):
    """Resuelve la meta ESACOM por CAMADA, no por fecha de reporte.

    Ejemplo vigente: B1 Agosto 2026 -> 85%, B2 Julio 2026 -> 83%,
    B3 Junio 2026 -> 78%. El 80% de B3 solo aplica cuando la camada
    evaluada es Julio 2026 o posterior.
    """
    boleta = str(boleta or "").upper()
    if boleta not in {"B1", "B2", "B3"} or not camada_valida(camada):
        return fallback
    vigencia = (
        MetaKPICalidad.objects.filter(vigente_desde__lte=camada)
        .order_by("-vigente_desde", "-creado_en")
        .first()
    )
    if not vigencia:
        return fallback
    return getattr(vigencia, f"meta_{boleta.lower()}")


def metas_calidad_para_focos(focos: dict[str, str] | None, *, fallback: dict[str, object] | None = None):
    focos = focos or {}
    fallback = fallback or {}
    resultado = {}
    for boleta in ("B1", "B2", "B3"):
        resultado[boleta] = meta_calidad_para(
            boleta=boleta,
            camada=focos.get(boleta, ""),
            fallback=fallback.get(boleta),
        )
    return resultado


def serializar_meta(valor):
    if valor is None:
        return None
    return float(Decimal(str(valor)))
