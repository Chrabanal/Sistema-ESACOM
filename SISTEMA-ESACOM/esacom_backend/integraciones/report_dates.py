import datetime
import re


_FECHA_EN_NOMBRE = re.compile(r"(?<!\d)(\d{2})(\d{2})(\d{4})(?!\d)")


def fecha_reporte_desde_nombre(nombre: str | None):
    """Obtiene la fecha del reporte Claro desde nombres como KPI23092026 ESACOM.xlsx.

    La fecha del archivo/reporte es distinta de ``fecha_corte`` (pagos considerados)
    y de ``creado_en`` (momento en que Soporte lo cargó al CRM).
    """
    texto = str(nombre or "")
    for dia, mes, anio in _FECHA_EN_NOMBRE.findall(texto):
        try:
            return datetime.date(int(anio), int(mes), int(dia))
        except ValueError:
            continue
    return None
