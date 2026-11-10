const TONOS = {
  verde: "border-green-200 bg-green-50/80 text-green-900",
  lima: "border-lime-200 bg-lime-50 text-lime-900",
  naranja: "border-orange-200 bg-orange-50/80 text-orange-900",
  azul: "border-blue-200 bg-blue-50/80 text-blue-900",
  rojo: "border-red-200 bg-red-50/80 text-red-900",
  neutro: "border-slate-200 bg-white text-slate-900",
};

/**
 * Filtros visibles y táctiles para la cartera comercial.
 * Los valores provienen de ventas ESACOM; algunos filtros (por ejemplo
 * "Nuevos" y "Pagaron") pueden solaparse con los estados de instalación.
 */
export default function TarjetasEstadoComercial({ items, activo, onSeleccionar }) {
  return (
    <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 xl:grid-cols-6">
      {items.map(({ key, label, valor, detalle, tono = "neutro", icono = "•" }) => {
        const seleccionado = activo === key;
        return (
          <button
            key={key}
            type="button"
            aria-pressed={seleccionado}
            onClick={() => onSeleccionar(key)}
            className={`group flex min-h-[132px] flex-col items-start rounded-2xl border p-3 text-left shadow-sm transition-all duration-150 hover:-translate-y-0.5 hover:shadow-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-lime-600 active:translate-y-0 sm:p-4 ${TONOS[tono] || TONOS.neutro} ${seleccionado ? "ring-2 ring-lime-500 ring-offset-1" : ""}`}
          >
            <span className="mb-2 flex w-full items-center gap-2">
              <span aria-hidden="true" className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-white/80 text-lg font-bold shadow-sm">
                {icono}
              </span>
              <span className="text-[11px] font-bold leading-tight sm:text-xs">{label}</span>
            </span>
            <strong className="text-3xl font-black tracking-tight tabular-nums">{valor ?? 0}</strong>
            <span className="mt-1 text-[10px] leading-snug opacity-75 sm:text-[11px]">{detalle}</span>
            {seleccionado && <span className="mt-auto pt-2 text-[10px] font-bold">✓ Mostrando estos clientes</span>}
          </button>
        );
      })}
    </div>
  );
}
