from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from openpyxl import Workbook

from integraciones.services.rrhh import CAMPOS_PERMITIDOS, auditar_rrhh
from usuarios.models import Ejecutivo


class AuditoriaRRHHTests(TestCase):
    def setUp(self):
        self.antonio = Ejecutivo.objects.create_user(
            rut="10837118-8", nombre="LEONEL ANTONIO OCHOA GARAY",
            cargo=Ejecutivo.Cargo.SUPERVISOR, password="Test1234!",
        )
        self.luis = Ejecutivo.objects.create_user(
            rut="17480608-K", nombre="LUIS ALFREDO LARENAS ORTIZ",
            cargo=Ejecutivo.Cargo.EJECUTIVO, tipo_kpi=Ejecutivo.TipoKPI.REGULAR,
            equipo="QUILPUÉ", password="Test1234!",
        )

    def _archivo(self):
        wb = Workbook()
        ws = wb.active
        ws.title = "RECURSOS HUMANOS"
        headers = list(CAMPOS_PERMITIDOS.values()) + ["CLAVE ANDES"]
        ws.append(headers)

        def fila(**kwargs):
            data = {h: "" for h in headers}
            data.update(kwargs)
            ws.append([data[h] for h in headers])

        fila(**{
            "RUT": "17.480.608-K", "NOMBRE": "LUIS ALFREDO LARENAS ORTIZ",
            "CORREO EMPRESA": "luis@esacomspa.cl", "PLAZA ASIGNADA": "QUILPUÉ",
            "FECHA INICIO": "01/09/2026", "TIPO DE CONTRATO": "PLAZO FIJO",
            "CARGO": "Ejecutivo de Ventas y Mantención de Cartera", "SUPERVISOR": "ANTONIO",
            "CÓDIGO MÓVIL": "MOV-1", "CÓDIGO CE": "CE-1", "CÓDIGO ANDES": "LANDES",
            "ESTADO DE CONTRATO": "CONTRATADO", "FECHA DE DESVINCULACIÓN": "",
            "ESTADO DE TRABAJADOR": "ACTIVO", "Activo/Inactivo": "ACTIVO",
            "BASE VENTAS": "NO", "IDENTIFICACIÓN CARGO": "EVT",
            "CLAVE ANDES": "NO-DEBE-SALIR",
        })
        fila(**{
            "RUT": "21.435.800-K", "NOMBRE": "DILAN ANTONIO GONZALEZ CONTRERAS",
            "CORREO EMPRESA": "dilan@esacomspa.cl", "PLAZA ASIGNADA": "QUILPUÉ",
            "FECHA INICIO": "01/09/2026", "TIPO DE CONTRATO": "PLAZO FIJO",
            "CARGO": "Ejecutivo de Ventas y Mantención de Cartera", "SUPERVISOR": "ANTONIO",
            "CÓDIGO MÓVIL": "", "CÓDIGO CE": "", "CÓDIGO ANDES": "",
            "ESTADO DE CONTRATO": "CONTRATADO", "FECHA DE DESVINCULACIÓN": "",
            "ESTADO DE TRABAJADOR": "ACTIVO", "Activo/Inactivo": "ACTIVO",
            "BASE VENTAS": "NO", "IDENTIFICACIÓN CARGO": "EVT",
            "CLAVE ANDES": "OTRA-CLAVE-PRIVADA",
        })
        out = BytesIO()
        wb.save(out)
        return SimpleUploadedFile(
            "Recursos Humanos.xlsx", out.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def test_dry_run_detecta_antonio_y_no_aplica_cambios(self):
        resultado = auditar_rrhh(uploaded_file=self._archivo())
        self.luis.refresh_from_db()

        self.assertFalse(resultado["aplica_cambios"])
        self.assertIsNone(self.luis.supervisor)
        self.assertEqual(resultado["resumen"]["rrhh_comerciales_vigentes"], 2)
        self.assertEqual(resultado["resumen"]["solo_rrhh"], 1)

        luis = next(f for f in resultado["filas"] if f["rut"] == "17480608-K")
        supervisor = next(d for d in luis["diferencias"] if d["campo"] == "supervisor")
        self.assertIn("10837118-8", supervisor["rrhh"])

        texto = str(resultado)
        self.assertNotIn("NO-DEBE-SALIR", texto)
        self.assertNotIn("OTRA-CLAVE-PRIVADA", texto)
        self.assertIn("CLAVE ANDES", resultado["seguridad"]["columnas_sensibles_ignoradas"])
