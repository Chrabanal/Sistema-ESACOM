"""Lectura segura y auditoría de la fuente de Recursos Humanos ESACOM.

R2.13 introduce una integración en modo SOLO LECTURA / DRY-RUN. La fuente
RRHH se usa para proponer diferencias de dotación, nunca para cambiar el rol
de acceso CRM ni contraseñas. En particular, columnas sensibles como
``CLAVE ANDES`` se ignoran por diseño y no se devuelven por API.
"""
from __future__ import annotations

import os
import re
import tempfile
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from django.conf import settings

from usuarios.dotacion import SUPERVISOR_ALIAS_A_RUT
from usuarios.models import Ejecutivo

HOJA_RRHH = "RECURSOS HUMANOS"
ESTADOS_VIGENTES = {"ACTIVO", "HONORARIO", "PENDIENTE"}
ESTADOS_ACTIVOS = {"ACTIVO", "HONORARIO"}
VALORES_VACIOS = {"", "N/A", "NA", "NO APLICA", "SIN DATO", "-"}

# Lista blanca: ninguna otra columna se lee ni se conserva.
CAMPOS_PERMITIDOS = {
    "rut": "RUT",
    "nombre": "NOMBRE",
    "correo_empresa": "CORREO EMPRESA",
    "plaza": "PLAZA ASIGNADA",
    "fecha_ingreso": "FECHA INICIO",
    "tipo_contrato": "TIPO DE CONTRATO",
    "cargo_laboral": "CARGO",
    "supervisor_fuente": "SUPERVISOR",
    "codigo_movil": "CÓDIGO MÓVIL",
    "codigo_fijo": "CÓDIGO CE",
    "codigo_andes": "CÓDIGO ANDES",
    "estado_contrato": "ESTADO DE CONTRATO",
    "fecha_desvinculacion": "FECHA DE DESVINCULACIÓN",
    "estado_trabajador": "ESTADO DE TRABAJADOR",
    "activo_inactivo": "Activo/Inactivo",
    "base_ventas": "BASE VENTAS",
    "identificacion_cargo": "IDENTIFICACIÓN CARGO",
}

# Campos que sabemos que existen en la planilla, pero deliberadamente nunca
# se importan. Se mantiene el nombre para documentar el límite de seguridad.
COLUMNAS_SENSIBLES_IGNORADAS = [
    "CLAVE ANDES",
    "DIRECCIÓN",
    "FECHA NACIMIENTO",
    "AFP",
    "SALUD",
    "CONTACTO EMERGENCIA",
    "N°CONTACTO",
]

# Alias observados en RRHH. Los roles CRM siguen protegidos y la resolución
# solo se usa como propuesta de asignación de supervisor para ejecutivos.
SUPERVISOR_RRHH_A_RUT = {
    **SUPERVISOR_ALIAS_A_RUT,
    "CHARLY": "17480807-4",
    "JORGE": "16440386-6",
    "JORGE H": "16440386-6",
    "JORGE H.": "16440386-6",
    "PATRICIO": "17790237-3",
    "VICENTE": "22186549-9",
    "ANTONIO": "10837118-8",
}


class RRHHError(RuntimeError):
    pass


@dataclass
class FuenteRRHH:
    path: str
    modo: str
    nombre: str
    temporal: bool = False
    metadata: dict | None = None


def _texto(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return re.sub(r"\s+", " ", str(valor).strip())


def _clave(valor) -> str:
    texto = _texto(valor).upper()
    texto = "".join(
        c for c in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(c)
    )
    return re.sub(r"\s+", " ", texto).strip()


def _valor_util(valor) -> str:
    texto = _texto(valor)
    return "" if _clave(texto) in VALORES_VACIOS else texto


def _fecha_iso(valor) -> str | None:
    if valor in (None, ""):
        return None
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    texto = _texto(valor)
    if not texto or _clave(texto) in VALORES_VACIOS or texto == "0":
        return None
    # openpyxl suele convertir fechas reales. Este fallback cubre textos
    # ISO y dd/mm/yyyy sin interpretar de forma agresiva otros formatos.
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(texto[:10], fmt).date().isoformat()
        except ValueError:
            pass
    return texto


def _es_comercial(registro: dict) -> bool:
    cargo = _clave(registro.get("cargo_laboral"))
    return bool(
        "VENTA" in cargo
        or "SUPERVISOR COMERCIAL" in cargo
        or "GERENTE COMERCIAL" in cargo
    )


def _tipo_kpi_rrhh(registro: dict) -> str:
    if (
        _clave(registro.get("tipo_contrato")) == "HONORARIO"
        or _clave(registro.get("estado_trabajador")) == "HONORARIO"
        or _clave(registro.get("estado_contrato")) == "HONORARIO"
    ):
        return Ejecutivo.TipoKPI.HONORARIOS
    return Ejecutivo.TipoKPI.REGULAR


def _activo_rrhh(registro: dict) -> bool | None:
    estado = _clave(registro.get("estado_trabajador"))
    if estado in ESTADOS_ACTIVOS:
        return True
    if estado == "PENDIENTE":
        return None
    if estado:
        return False
    return None


def _resolver_supervisor(nombre: str) -> str | None:
    clave = _clave(nombre)
    if not clave or clave in {"N/A", "SIN SUPERVISOR", "DON ENZO", "ENZO"}:
        return None
    return SUPERVISOR_RRHH_A_RUT.get(clave)


def _rut(valor) -> str:
    return Ejecutivo.objects.normalize_rut(_texto(valor))


def _leer_registros_xlsx(path: str) -> tuple[list[dict], dict]:
    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        if HOJA_RRHH not in wb.sheetnames:
            raise RRHHError(f'No existe la hoja obligatoria "{HOJA_RRHH}".')
        ws = wb[HOJA_RRHH]
        filas = ws.iter_rows(values_only=True)
        try:
            encabezados_raw = next(filas)
        except StopIteration as exc:
            raise RRHHError("La hoja RECURSOS HUMANOS está vacía.") from exc

        indices = {_clave(v): i for i, v in enumerate(encabezados_raw) if _clave(v)}
        faltantes = [nombre for nombre in CAMPOS_PERMITIDOS.values() if _clave(nombre) not in indices]
        if faltantes:
            raise RRHHError("Faltan columnas RRHH requeridas: " + ", ".join(faltantes))

        registros = []
        vistos = set()
        duplicados = set()
        filas_leidas = 0
        for numero_fila, valores in enumerate(filas, start=2):
            filas_leidas += 1
            def obtener(cabecera):
                idx = indices[_clave(cabecera)]
                return valores[idx] if idx < len(valores) else None

            rut = _rut(obtener(CAMPOS_PERMITIDOS["rut"]))
            if not rut:
                continue
            if rut in vistos:
                duplicados.add(rut)
            vistos.add(rut)
            registro = {
                "fila": numero_fila,
                "rut": rut,
                "nombre": _valor_util(obtener(CAMPOS_PERMITIDOS["nombre"])),
                "correo_empresa": _valor_util(obtener(CAMPOS_PERMITIDOS["correo_empresa"])),
                "plaza": _valor_util(obtener(CAMPOS_PERMITIDOS["plaza"])),
                "fecha_ingreso": _fecha_iso(obtener(CAMPOS_PERMITIDOS["fecha_ingreso"])),
                "tipo_contrato": _valor_util(obtener(CAMPOS_PERMITIDOS["tipo_contrato"])),
                "cargo_laboral": _valor_util(obtener(CAMPOS_PERMITIDOS["cargo_laboral"])),
                "supervisor_fuente": _valor_util(obtener(CAMPOS_PERMITIDOS["supervisor_fuente"])),
                "codigo_movil": _valor_util(obtener(CAMPOS_PERMITIDOS["codigo_movil"])),
                "codigo_fijo": _valor_util(obtener(CAMPOS_PERMITIDOS["codigo_fijo"])),
                "codigo_andes": _valor_util(obtener(CAMPOS_PERMITIDOS["codigo_andes"])),
                "estado_contrato": _valor_util(obtener(CAMPOS_PERMITIDOS["estado_contrato"])),
                "fecha_desvinculacion": _fecha_iso(obtener(CAMPOS_PERMITIDOS["fecha_desvinculacion"])),
                "estado_trabajador": _valor_util(obtener(CAMPOS_PERMITIDOS["estado_trabajador"])),
                "activo_inactivo": _valor_util(obtener(CAMPOS_PERMITIDOS["activo_inactivo"])),
                "base_ventas": _valor_util(obtener(CAMPOS_PERMITIDOS["base_ventas"])),
                "identificacion_cargo": _valor_util(obtener(CAMPOS_PERMITIDOS["identificacion_cargo"])),
            }
            registro["vigente_rrhh"] = _clave(registro["estado_trabajador"]) in ESTADOS_VIGENTES
            registro["comercial"] = _es_comercial(registro)
            registro["tipo_kpi_propuesto"] = _tipo_kpi_rrhh(registro)
            registro["activo_propuesto"] = _activo_rrhh(registro)
            registro["supervisor_rut_propuesto"] = _resolver_supervisor(registro["supervisor_fuente"])
            registros.append(registro)

        return registros, {
            "filas_leidas": filas_leidas,
            "ruts_unicos": len(vistos),
            "ruts_duplicados": sorted(duplicados),
            "columnas_leidas": list(CAMPOS_PERMITIDOS.values()),
            "columnas_sensibles_ignoradas": COLUMNAS_SENSIBLES_IGNORADAS,
        }
    finally:
        wb.close()


def _guardar_upload(uploaded_file) -> FuenteRRHH:
    sufijo = Path(getattr(uploaded_file, "name", "rrhh.xlsx")).suffix.lower() or ".xlsx"
    if sufijo != ".xlsx":
        raise RRHHError("Recursos Humanos debe cargarse en formato .xlsx")
    tmp = tempfile.NamedTemporaryFile(prefix="esacom_rrhh_upload_", suffix=".xlsx", delete=False)
    try:
        for chunk in uploaded_file.chunks():
            tmp.write(chunk)
        tmp.flush()
    finally:
        tmp.close()
    return FuenteRRHH(path=tmp.name, modo="UPLOAD_DRY_RUN", nombre=getattr(uploaded_file, "name", "rrhh.xlsx"), temporal=True)


def _descargar_google_rrhh(file_id: str) -> FuenteRRHH:
    from googleapiclient.http import MediaIoBaseDownload
    from integraciones.services.google_sheets import _drive_service

    drive = _drive_service()
    metadata = drive.files().get(fileId=file_id, fields="id,name,mimeType,modifiedTime,size").execute()
    mime = metadata.get("mimeType", "")
    if mime == "application/vnd.google-apps.spreadsheet":
        request = drive.files().export_media(
            fileId=file_id,
            mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    else:
        request = drive.files().get_media(fileId=file_id)

    tmp = tempfile.NamedTemporaryFile(prefix="esacom_rrhh_google_", suffix=".xlsx", delete=False)
    tmp_path = tmp.name
    tmp.close()
    with open(tmp_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request, chunksize=1024 * 1024)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    return FuenteRRHH(path=tmp_path, modo="GOOGLE_DRIVE_DRY_RUN", nombre=metadata.get("name") or "Recursos Humanos", temporal=True, metadata=metadata)


def obtener_fuente_rrhh(*, uploaded_file=None) -> FuenteRRHH:
    if uploaded_file is not None:
        return _guardar_upload(uploaded_file)

    local = str(getattr(settings, "HR_LOCAL_XLSX", "") or "").strip()
    if local:
        path = Path(local)
        if not path.exists():
            raise RRHHError(f"HR_LOCAL_XLSX no existe dentro del contenedor: {local}")
        return FuenteRRHH(path=str(path), modo="LOCAL_XLSX_DRY_RUN", nombre=path.name)

    google_id = str(getattr(settings, "GOOGLE_HR_SPREADSHEET_ID", "") or "").strip()
    if google_id:
        return _descargar_google_rrhh(google_id)

    raise RRHHError(
        "No hay fuente RRHH configurada. Sube un XLSX desde la pantalla de Auditoría RRHH "
        "o configura HR_LOCAL_XLSX / GOOGLE_HR_SPREADSHEET_ID."
    )


def _diferencia(campo: str, crm, rrhh, accion: str, severidad: str = "MEDIA") -> dict:
    return {
        "campo": campo,
        "crm": crm if crm not in (None, "") else "—",
        "rrhh": rrhh if rrhh not in (None, "") else "—",
        "accion_sugerida": accion,
        "severidad": severidad,
    }


def auditar_rrhh(*, uploaded_file=None) -> dict:
    fuente = obtener_fuente_rrhh(uploaded_file=uploaded_file)
    try:
        registros, lectura = _leer_registros_xlsx(fuente.path)
    finally:
        if fuente.temporal:
            try:
                os.unlink(fuente.path)
            except OSError:
                pass

    # Si hubiese RUT repetido, la última fila prevalece para el diagnóstico;
    # el duplicado igualmente queda informado en lectura.ruts_duplicados.
    por_rut = {r["rut"]: r for r in registros}
    vigentes = {rut: r for rut, r in por_rut.items() if r["vigente_rrhh"]}
    vigentes_comerciales = {rut: r for rut, r in vigentes.items() if r["comercial"]}

    qs = Ejecutivo.objects.select_related("supervisor").all()
    crm = {u.rut: u for u in qs}
    # Se audita toda cuenta CRM salvo Soporte técnico, más cada persona
    # comercial vigente de RRHH que todavía no exista en CRM.
    crm_operacional = {
        rut: u for rut, u in crm.items()
        if u.cargo != Ejecutivo.Cargo.SOPORTE
    }
    universo = sorted(set(crm_operacional) | set(vigentes_comerciales))

    filas = []
    supervisor_no_resuelto = 0
    for rut in universo:
        u = crm_operacional.get(rut)
        r = por_rut.get(rut)
        diferencias = []

        if u is None and r is not None:
            diferencias.append(_diferencia(
                "existencia_crm", "NO EXISTE", "VIGENTE RRHH",
                "Revisar y crear acceso CRM solo si corresponde al proceso comercial.", "ALTA",
            ))
        elif u is not None and r is None:
            diferencias.append(_diferencia(
                "existencia_rrhh", "EXISTE CRM", "SIN REGISTRO RRHH",
                "Revisar manualmente; RRHH no debe borrar ni desactivar accesos por sí solo.", "ALTA",
            ))
        elif u is not None and r is not None:
            if r.get("nombre") and _clave(r["nombre"]) != _clave(u.nombre):
                diferencias.append(_diferencia("nombre", u.nombre, r["nombre"], "Revisar nombre maestro por RUT."))

            if r.get("correo_empresa") and _clave(r["correo_empresa"]) != _clave(u.correo):
                diferencias.append(_diferencia("correo_empresa", u.correo, r["correo_empresa"], "Proponer correo corporativo RRHH."))

            if r.get("plaza") and _clave(r["plaza"]) != _clave(u.equipo):
                diferencias.append(_diferencia("plaza_equipo", u.equipo, r["plaza"], "Proponer plaza/equipo RRHH."))

            if r.get("tipo_contrato") and _clave(r["tipo_contrato"]) != _clave(u.tipo_contrato):
                diferencias.append(_diferencia("tipo_contrato", u.tipo_contrato, r["tipo_contrato"], "Proponer tipo de contrato RRHH."))

            if r["tipo_kpi_propuesto"] != u.tipo_kpi and u.cargo == Ejecutivo.Cargo.EJECUTIVO:
                diferencias.append(_diferencia("tipo_kpi", u.tipo_kpi, r["tipo_kpi_propuesto"], "Revisar Regular/Honorarios según RRHH.", "ALTA"))

            activo = r["activo_propuesto"]
            if activo is not None and bool(u.is_active) != bool(activo):
                diferencias.append(_diferencia(
                    "estado_acceso", "ACTIVO" if u.is_active else "INACTIVO",
                    "ACTIVO" if activo else "INACTIVO",
                    "Revisar alta/baja. Nunca se aplica automáticamente desde RRHH.", "ALTA",
                ))

            if r.get("cargo_laboral") and _clave(r["cargo_laboral"]) != _clave(u.cargo_fuente_esacom):
                diferencias.append(_diferencia(
                    "cargo_laboral", u.cargo_fuente_esacom, r["cargo_laboral"],
                    "Actualizar solo cargo laboral de fuente; NO cambiar rol CRM.",
                ))

            if u.cargo == Ejecutivo.Cargo.EJECUTIVO:
                sup_fuente = _clave(r.get("supervisor_fuente"))
                sup_rut = r.get("supervisor_rut_propuesto")
                if sup_fuente and sup_fuente not in {"N/A", "DON ENZO", "ENZO"}:
                    if sup_rut:
                        crm_sup = u.supervisor.rut if u.supervisor else None
                        if crm_sup != sup_rut:
                            sup = crm.get(sup_rut)
                            destino = f"{getattr(sup, 'nombre', '')} · {sup_rut}".strip(" ·")
                            actual = f"{getattr(u.supervisor, 'nombre', '')} · {crm_sup or ''}".strip(" ·")
                            diferencias.append(_diferencia("supervisor", actual, destino, "Proponer reasignación por RUT RRHH.", "ALTA"))
                    else:
                        supervisor_no_resuelto += 1
                        diferencias.append(_diferencia(
                            "supervisor_no_resuelto",
                            getattr(u.supervisor, "nombre", "") if u.supervisor else "—",
                            r.get("supervisor_fuente") or "—",
                            "Agregar alias confirmado antes de permitir una actualización.", "ALTA",
                        ))

            for campo_rrhh, campo_crm, etiqueta in (
                ("codigo_movil", "codigo_movil", "codigo_movil"),
                ("codigo_fijo", "codigo_fijo", "codigo_fijo"),
                ("codigo_andes", "codigo_andes", "codigo_andes"),
            ):
                valor = r.get(campo_rrhh)
                actual = getattr(u, campo_crm, "")
                if valor and _clave(valor) != _clave(actual):
                    diferencias.append(_diferencia(etiqueta, actual, valor, "Proponer código operativo RRHH."))

            if r.get("fecha_ingreso"):
                actual_fecha = u.fecha_ingreso.isoformat() if u.fecha_ingreso else None
                if actual_fecha != r["fecha_ingreso"]:
                    diferencias.append(_diferencia("fecha_ingreso", actual_fecha, r["fecha_ingreso"], "Proponer fecha de ingreso RRHH."))

        if diferencias:
            filas.append({
                "rut": rut,
                "nombre": (r or {}).get("nombre") or getattr(u, "nombre", ""),
                "rol_crm": getattr(u, "cargo", None),
                "rol_crm_protegido": bool(u),
                "estado_trabajador_rrhh": (r or {}).get("estado_trabajador"),
                "tipo_contrato_rrhh": (r or {}).get("tipo_contrato"),
                "cargo_laboral_rrhh": (r or {}).get("cargo_laboral"),
                "plaza_rrhh": (r or {}).get("plaza"),
                "supervisor_rrhh": (r or {}).get("supervisor_fuente"),
                "diferencias": diferencias,
            })

    solo_rrhh = sum(1 for rut in vigentes_comerciales if rut not in crm_operacional)
    solo_crm = sum(1 for rut in crm_operacional if rut not in por_rut)
    coincidencias = sum(1 for rut in crm_operacional if rut in por_rut)

    return {
        "modo": "DRY_RUN",
        "aplica_cambios": False,
        "fuente": {
            "modo": fuente.modo,
            "nombre": fuente.nombre,
            "metadata": fuente.metadata or {},
        },
        "seguridad": {
            "rol_crm_protegido": True,
            "passwords_ignoradas": True,
            "columnas_sensibles_ignoradas": COLUMNAS_SENSIBLES_IGNORADAS,
            "mensaje": "Esta versión solo compara. No crea, edita, activa ni desactiva usuarios.",
        },
        "resumen": {
            **lectura,
            "rrhh_vigentes": len(vigentes),
            "rrhh_comerciales_vigentes": len(vigentes_comerciales),
            "rrhh_honorarios_vigentes": sum(1 for r in vigentes_comerciales.values() if r["tipo_kpi_propuesto"] == Ejecutivo.TipoKPI.HONORARIOS),
            "rrhh_pendientes": sum(1 for r in vigentes_comerciales.values() if _clave(r["estado_trabajador"]) == "PENDIENTE"),
            "crm_operacionales": len(crm_operacional),
            "coincidencias_por_rut": coincidencias,
            "solo_rrhh": solo_rrhh,
            "solo_crm": solo_crm,
            "con_diferencias": len(filas),
            "supervisores_no_resueltos": supervisor_no_resuelto,
        },
        "filas": filas,
    }
