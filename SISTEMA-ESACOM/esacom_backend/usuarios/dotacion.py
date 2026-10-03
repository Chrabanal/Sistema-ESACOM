"""Reglas controladas para reconciliar Dotación ESACOM con roles CRM.

El campo Cargo de la planilla es informativo/laboral y no define permisos.
Los supervisores CRM confirmados se identifican por RUT y los alias de la
columna SUPERVISOR se resuelven únicamente contra este catálogo explícito.
"""

SUPERVISOR_ALIAS_A_RUT = {
    "CHARLY ESTAY": "17480807-4",
    "JORGE HERNANDEZ": "16440386-6",
    "PATRICIO GUERRA": "17790237-3",
    "VICENTE MORALES": "22186549-9",
    # Antonio/Leonel es una sola persona: vende con su RUT y además opera
    # como Supervisor. La fuente ESACOM puede traerlo como EJECUTIVO, pero
    # el rol de acceso CRM debe permanecer SUPERVISOR después de cada sync.
    "ANTONIO OCHOA": "10837118-8",
    "LEONEL ANTONIO OCHOA": "10837118-8",
    "LEONEL ANTONIO OCHOA GARAY": "10837118-8",
}

SUPERVISOR_RUTS_CONFIRMADOS = frozenset(SUPERVISOR_ALIAS_A_RUT.values())
