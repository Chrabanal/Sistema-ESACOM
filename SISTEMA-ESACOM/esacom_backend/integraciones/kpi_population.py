"""Helpers de auditoría de población KPI.

La población operativa se compara por la identidad relacional interna
(Venta + camada + boleta), no por el texto externo NUM_PEDIDO.
"""


def clave_poblacion(venta_id, camada, boleta):
    return (venta_id, camada, boleta)


def diferencias_poblacion(esperadas, actuales):
    esperadas = set(esperadas)
    actuales = set(actuales)
    return esperadas - actuales, actuales - esperadas
