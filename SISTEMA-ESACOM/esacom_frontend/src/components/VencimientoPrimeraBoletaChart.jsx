import { useMemo } from "react";

const FECHA_REGEX = /^\d{4}-\d{2}-\d{2}$/;

function fechaDia(valor) {
  const fecha = String(valor || "").slice(0, 10);
  return FECHA_REGEX.test(fecha) ? fecha : null;
}

function hoyLocal() {
  const hoy = new Date();
  const yyyy = hoy.getFullYear();
  const mm = String(hoy.getMonth() + 1).padStart(2, "0");
  const dd = String(hoy.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function sumarDias(fecha, dias) {
  const d = new Date(`${fecha}T12:00:00`);
  d.setDate(d.getDate() + dias);
  return fechaDia(
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`
  );
}

function fechaVisible(fecha) {
  const [yyyy, mm, dd] = fecha.split("-");
  return `${dd}/${mm}/${yyyy}`;
}

export default function VencimientoPrimeraBoletaChart({
  cortes = [],
  mesSeleccionado,
  fechaSeleccionada,
  onSeleccionarFecha,
}) {
  const hoy = hoyLocal();
  const limiteProximos = sumarDias(hoy, 7);

  const resumen = useMemo(() => {
    const fechas = new Map();
    const totales = {
      vencidos: 0,
      proximos: 0,
      posteriores: 0,
      clientes: 0,
    };

    for (const corte of cortes || []) {
      if (corte.mes_ano !== mesSeleccionado) continue;
      if (corte.boleta !== "B1") continue;
      if (corte.estado_pago !== "PENDIENTE") continue;
      if (corte.venta?.estado_instalacion !== "INSTALADO") continue;

      const fecha = fechaDia(corte.fecha_vencimiento);
      if (!fecha) continue;

      const rgu = Number(corte.rgu_kpi ?? corte.venta?.rgu_base ?? 0);
      if (!Number.isFinite(rgu) || rgu <= 0) continue;

      const actual = fechas.get(fecha) || {
        fecha,
        rgu: 0,
        clientes: 0,
      };

      actual.rgu += rgu;
      actual.clientes += 1;
      fechas.set(fecha, actual);

      totales.clientes += 1;

      if (fecha < hoy) {
        totales.vencidos += rgu;
      } else if (fecha <= limiteProximos) {
        totales.proximos += rgu;
      } else {
        totales.posteriores += rgu;
      }
    }

    return {
      fechas: [...fechas.values()].sort((a, b) =>
        a.fecha.localeCompare(b.fecha)
      ),
      totales,
    };
  }, [cortes, mesSeleccionado, hoy, limiteProximos]);

  const maximo = Math.max(
    ...resumen.fechas.map((f) => f.rgu),
    1
  );

  return (
    <section className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
      <h3 className="text-sm font-extrabold text-gray-900">
        Vencimiento primera boleta
      </h3>
      <p className="mt-1 text-[11px] text-gray-500">
        RGU pendientes de B1 del período seleccionado.
      </p>

      <div className="mt-4 grid grid-cols-3 gap-2">
        {[
          ["Vencidos", resumen.totales.vencidos, "text-red-700 bg-red-50"],
          ["Próximos 7 días", resumen.totales.proximos, "text-amber-700 bg-amber-50"],
          ["Posteriores", resumen.totales.posteriores, "text-blue-700 bg-blue-50"],
        ].map(([titulo, valor, clases]) => (
          <div key={titulo} className={`rounded-xl p-3 ${clases}`}>
            <p className="text-[10px] font-bold">{titulo}</p>
            <p className="mt-1 text-xl font-black">{valor} RGU</p>
          </div>
        ))}
      </div>

      {resumen.fechas.length === 0 ? (
        <div className="mt-4 rounded-xl border border-green-100 bg-green-50 p-4 text-center">
          <p className="text-xs font-bold text-green-700">
            No hay vencimientos B1 pendientes con fecha registrada en este período.
          </p>
        </div>
      ) : (
        <div className="mt-4 space-y-3">
          {resumen.fechas.map((item) => {
            const vencida = item.fecha < hoy;
            const proxima = item.fecha <= limiteProximos;
            const color = vencida
              ? "bg-red-500"
              : proxima
              ? "bg-amber-400"
              : "bg-blue-500";

            return (
              <button
                key={item.fecha}
                type="button"
                onClick={() =>
                  onSeleccionarFecha(
                    fechaSeleccionada === item.fecha ? null : item.fecha
                  )
                }
                className={`w-full rounded-lg p-2 text-left hover:bg-gray-50 ${
                  fechaSeleccionada === item.fecha
                    ? "ring-2 ring-blue-400"
                    : ""
                }`}
              >
                <div className="mb-1 flex justify-between text-xs">
                  <span className="font-semibold text-gray-700">
                    {fechaVisible(item.fecha)}
                  </span>
                  <span className="font-bold text-gray-900">
                    {item.rgu} RGU · {item.clientes} clientes
                  </span>
                </div>
                <div className="h-2.5 overflow-hidden rounded-full bg-gray-100">
                  <div
                    className={`h-full rounded-full ${color}`}
                    style={{ width: `${(item.rgu / maximo) * 100}%` }}
                  />
                </div>
              </button>
            );
          })}
        </div>
      )}

      {fechaSeleccionada && (
        <p className="mt-3 text-xs font-semibold text-blue-700">
          Fecha seleccionada: {fechaVisible(fechaSeleccionada)}
        </p>
      )}
    </section>
  );
}
