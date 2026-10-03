from django.core.management.base import BaseCommand, CommandError
from integraciones.models import CargaExcel
from integraciones.services.google_sheets import obtener_metadata_spreadsheet, sincronizar_base_matriz
from usuarios.models import Ejecutivo
from ventas.models import Venta, VentaMovil
from ventas.produccion import resumen_produccion_actual


class Command(BaseCommand):
    help = "Verifica acceso/actualidad de Google Sheets ESACOM y opcionalmente sincroniza mostrando antes/después."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sincronizar", action="store_true",
            help="Descarga e importa la Google Sheet ESACOM antes de mostrar el resultado final."
        )
        parser.add_argument(
            "--usuario-rut", default="",
            help="RUT del usuario que ejecuta la sincronización para trazabilidad."
        )

    def handle(self, *args, **options):
        try:
            meta = obtener_metadata_spreadsheet()
        except Exception as exc:
            raise CommandError(f"No fue posible consultar Google Sheets: {exc}") from exc

        antes_ventas = Venta.objects.count()
        antes_movil = VentaMovil.objects.count()
        antes_usuarios = Ejecutivo.objects.count()
        ultima_antes = CargaExcel.objects.filter(
            tipo_base=CargaExcel.TipoBase.BASE_MATRIZ
        ).order_by("-creado_en").first()

        self.stdout.write(self.style.SUCCESS("ESACOM · VERIFICACIÓN GOOGLE SHEETS"))
        self.stdout.write(f"Spreadsheet: {meta.get('name')}")
        self.stdout.write(f"Google modifiedTime: {meta.get('modifiedTime')}")
        self.stdout.write(f"Ventas fijas antes: {antes_ventas}")
        self.stdout.write(f"Ventas móviles antes: {antes_movil}")
        self.stdout.write(f"Usuarios antes: {antes_usuarios}")
        if ultima_antes:
            self.stdout.write(
                f"Última carga local antes: #{ultima_antes.id} · {ultima_antes.archivo_nombre} · {ultima_antes.creado_en}"
            )
        else:
            self.stdout.write("Última carga local antes: ninguna")

        resultado = None
        if options["sincronizar"]:
            usuario = None
            rut = (options.get("usuario_rut") or "").strip()
            if rut:
                usuario = Ejecutivo.objects.filter(rut=rut).first()
            try:
                resultado = sincronizar_base_matriz(creado_por=usuario)
            except Exception as exc:
                raise CommandError(f"Falló la sincronización: {exc}") from exc

        despues_ventas = Venta.objects.count()
        despues_movil = VentaMovil.objects.count()
        despues_usuarios = Ejecutivo.objects.count()
        ultima = CargaExcel.objects.filter(
            tipo_base=CargaExcel.TipoBase.BASE_MATRIZ
        ).order_by("-creado_en").first()

        self.stdout.write("\nRESULTADO LOCAL")
        self.stdout.write(f"Ventas fijas después: {despues_ventas} (Δ {despues_ventas - antes_ventas:+d})")
        self.stdout.write(f"Ventas móviles después: {despues_movil} (Δ {despues_movil - antes_movil:+d})")
        self.stdout.write(f"Usuarios después: {despues_usuarios} (Δ {despues_usuarios - antes_usuarios:+d})")
        if ultima:
            self.stdout.write(
                f"Última carga local: #{ultima.id} · {ultima.archivo_nombre} · {ultima.creado_en}"
            )
        produccion = resumen_produccion_actual()
        self.stdout.write("\nPRODUCCIÓN VIGENTE CALCULADA")
        self.stdout.write(
            f"Red fija: {produccion['fija']['total_control']} RGU "
            f"({produccion['fija']['completadas']} completados + "
            f"{produccion['fija']['pendiente_instalacion']} pend. instalación)"
        )
        self.stdout.write(
            f"Red móvil efectiva: {produccion['movil']['total']} líneas "
            f"({produccion['movil']['principal']} principal + "
            f"{produccion['movil']['adicional']} adicional + {produccion['movil']['ppm']} PPM)"
        )
        self.stdout.write(
            f"Móvil pendiente de activación: {produccion['movil']['pendiente_activacion']} de "
            f"{produccion['movil']['total_base_vigente']} líneas vigentes"
        )
        self.stdout.write(f"TOTAL PRODUCCIÓN: {produccion['total_produccion']}")
        conflictos = list(
            Venta.objects.filter(en_base_vigente=True, conflicto_fuente=True)
            .values_list("n_pedido", flat=True)[:10]
        )
        total_conflictos = Venta.objects.filter(en_base_vigente=True, conflicto_fuente=True).count()
        if total_conflictos:
            self.stdout.write(self.style.WARNING(
                f"[ALERTA] Pedidos maestros con conflicto multilínea: {total_conflictos} · "
                f"muestra: {', '.join(conflictos)}"
            ))
        else:
            self.stdout.write("Pedidos maestros con conflicto multilínea: 0")

        if resultado:
            self.stdout.write(f"Google modifiedTime importado: {resultado.get('modified_time')}")
            self.stdout.write(f"Carga creada: #{resultado.get('carga_id')}")
            self.stdout.write(f"SHA-256 fuente: {resultado.get('fuente_sha256', '-')}")
            self.stdout.write(f"Snapshot producción guardado: {resultado.get('resumen_produccion') or {}}")
            fuente_directa = resultado.get("fuente_directa") or {}
            if fuente_directa:
                ff = fuente_directa.get("fija") or {}
                fm = fuente_directa.get("movil") or {}
                self.stdout.write(
                    "Fuente DIRECTA del mismo XLSX: "
                    f"F {ff.get('completadas', 0)}/{ff.get('pendiente_instalacion', 0)}="
                    f"{ff.get('total_control', 0)} · "
                    f"M Pr{fm.get('principal', 0)} A{fm.get('adicional', 0)} PPM{fm.get('ppm', 0)}="
                    f"{fm.get('total', 0)} · TOTAL {fuente_directa.get('total_produccion', 0)}"
                )
            trazabilidad_fuente = fuente_directa.get("trazabilidad") or {}
            if trazabilidad_fuente:
                self.stdout.write(
                    "Trazabilidad fuente fija: "
                    f"{trazabilidad_fuente.get('filas_fija_control', 0)} filas control · "
                    f"{trazabilidad_fuente.get('pedidos_fija_control_unicos', 0)} pedidos únicos · "
                    f"{trazabilidad_fuente.get('duplicados_n_pedido_fija_control', 0)} filas duplicadas por N° PEDIDO"
                )
            resumen = resultado.get('resumen') or {}
            self.stdout.write("Resumen importador:")
            self.stdout.write(str(resumen))
            if resultado.get("alineacion_fuente_crm") is True:
                self.stdout.write(self.style.SUCCESS("[OK] XLSX IMPORTADO = CRM en producción fija y móvil."))
            elif resultado.get("alineacion_fuente_crm") is False:
                auditoria = resultado.get("auditoria_operacional") or {}
                self.stdout.write(self.style.WARNING(
                    "[ADVERTENCIA] La auditoría agregada detectó diferencias, pero la sincronización "
                    "se aplicó correctamente y el detalle quedó registrado en el snapshot. "
                    f"Diferencias: {auditoria.get('diferencias') or {}}"
                ))
            if not ultima or ultima.id != resultado.get('carga_id'):
                raise CommandError("La sincronización terminó, pero la carga registrada no coincide con el resultado.")
            self.stdout.write(self.style.SUCCESS("[OK] Google Sheet ESACOM descargada, importada y carga registrada correctamente."))
        else:
            self.stdout.write(self.style.SUCCESS("[OK] Acceso a Google Sheet ESACOM y estado local verificados (sin importar)."))
