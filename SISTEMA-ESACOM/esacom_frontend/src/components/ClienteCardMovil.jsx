import { registrarGestion } from "../api/apelaciones";

const ESTADOS_COMERCIALES = {
  INSTALADO: ["Instalado", "border-green-200 bg-green-50 text-green-800", "border-l-green-500"],
  PENDIENTE_INSTALACION: ["Pend. instalación", "border-orange-200 bg-orange-50 text-orange-800", "border-l-orange-500"],
  PENDIENTE_COMERCIAL: ["Pend. comercial", "border-blue-200 bg-blue-50 text-blue-800", "border-l-blue-500"],
  ANULADO: ["Anulado", "border-red-200 bg-red-50 text-red-800", "border-l-red-500"],
};

const ESTADOS_PAGO = {
  PAGADO: "Pagada",
  PENDIENTE: "Pendiente",
  NO_PAGO: "No pagada",
  FUERA_PLAZO: "Pagada fuera de plazo",
  SIN_BOLETA: "Sin boleta",
};

function fechaCorta(valor) {
  if (!valor) return "Sin fecha";
  const [anio, mes, dia] = String(valor).slice(0, 10).split("-");
  return dia && mes && anio ? `${dia}/${mes}/${anio}` : String(valor);
}

function telefonoChile(valor) {
  const soloDigitos = String(valor || "").replace(/\D/g, "");
  if (!soloDigitos) return "";
  return soloDigitos.startsWith("56") ? soloDigitos : `56${soloDigitos.replace(/^0+/, "")}`;
}

/**
 * Ficha compacta para trabajar desde teléfono.
 * Comparte los mismos datos de Venta y Corte que la ficha de escritorio;
 * no modifica estados ni calcula indicadores KPI.
 */
export default function ClienteCardMovil({ venta, onDetalle, mesSeleccionado, boletaActivaMes, activoPago = false }) {
  const estado = ESTADOS_COMERCIALES[venta.estado_instalacion] ||
    ["Sin estado", "border-gray-200 bg-gray-50 text-gray-700", "border-l-gray-300"];
  const cortes = Array.isArray(venta.cortes_resumen) ? venta.cortes_resumen : [];
  const corte = cortes.find((c) => c.mes_ano === mesSeleccionado && (!boletaActivaMes || c.boleta === boletaActivaMes)) || null;
  const telefono = telefonoChile(venta.telefono_cliente);

  const registrarContacto = (tipo) => {
    // No retrasar la acción de llamar o escribir por esperar la auditoría.
    Promise.resolve(registrarGestion(venta.id, tipo)).catch(() => {});
  };

  return (
    <article className={`overflow-hidden rounded-2xl border border-gray-200 border-l-4 bg-white shadow-sm ${estado[2]}`}>
      <div className="p-4">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <h3 className="break-words text-sm font-extrabold leading-snug text-slate-900">{venta.nombre_cliente || venta.rut_cliente || "Cliente sin nombre"}</h3>
            <p className="mt-1 text-xs text-slate-500">RUT {venta.rut_cliente || "—"}</p>
          </div>
          <span className={`shrink-0 rounded-full border px-2.5 py-1 text-[10px] font-bold ${estado[1]}`}>{estado[0]}</span>
        </div>

        <div className="mt-3 rounded-xl bg-slate-50 p-3">
          <p className="truncate text-[11px] font-bold text-slate-800">{venta.promocion?.nombre || "Servicio sin detalle"}</p>
          <p className="mt-1 break-all text-[11px] text-slate-500">Pedido: {venta.n_pedido || "—"}</p>
        </div>

        <div className="mt-2 flex items-center justify-between gap-3 rounded-xl border border-slate-100 p-3">
          <div className="min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Boleta y pago</p>
            <p className="mt-1 text-xs font-bold text-slate-900">
              {corte ? `${corte.boleta} · ${ESTADOS_PAGO[corte.estado_pago] || corte.estado_pago || "Sin estado"}` : "Aún sin boleta informada"}
            </p>
          </div>
          <div className="shrink-0 text-right">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">{corte?.estado_pago === "PAGADO" ? "Pagada" : "Vencimiento"}</p>
            <p className="mt-1 text-xs font-extrabold text-slate-900">
              {fechaCorta(corte?.estado_pago === "PAGADO" ? corte.fecha_pago : corte?.fecha_vencimiento)}
            </p>
          </div>
        </div>

        {activoPago && <p className="mt-2 text-xs font-semibold text-green-800">✓ Pago informado para la boleta consultada</p>}

        {telefono ? (
          <div className="mt-3 grid grid-cols-2 gap-2">
            <a
              href={`tel:+${telefono}`}
              onClick={() => registrarContacto("LLAMADA")}
              aria-label={`Llamar a ${venta.nombre_cliente || "cliente"}`}
              className="flex min-h-12 items-center justify-center rounded-xl border border-green-200 bg-green-50 text-sm font-bold text-green-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-green-600"
            >
              ☎ Llamar
            </a>
            <a
              href={`https://wa.me/${telefono}`}
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => registrarContacto("WHATSAPP")}
              aria-label={`Abrir WhatsApp con ${venta.nombre_cliente || "cliente"}`}
              className="flex min-h-12 items-center justify-center rounded-xl bg-green-600 text-sm font-bold text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-green-600"
            >
              WhatsApp
            </a>
          </div>
        ) : (
          <p className="mt-3 rounded-xl bg-slate-50 p-3 text-center text-xs text-slate-500">Sin teléfono registrado</p>
        )}

        <button
          type="button"
          onClick={() => onDetalle(venta.id)}
          className="mt-2 flex min-h-11 w-full items-center justify-center rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-800 hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-lime-600"
        >
          Ver venta, historial y boletas →
        </button>
      </div>
    </article>
  );
}
