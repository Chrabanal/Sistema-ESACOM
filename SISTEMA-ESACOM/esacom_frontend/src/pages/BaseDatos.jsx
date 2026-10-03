import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import { useAuth } from "../context/AuthContext";
import { menuPorUsuario } from "../utils/navigation";
import { ADMIN_URL } from "../api/client";
import { fetchTodasVentas, fetchVentasPaginado } from "../api/apelaciones";

const ESTADOS = [
  { value: "", label: "Todos los estados" },
  { value: "PENDIENTE_INSTALACION", label: "Pendiente Instalación" },
  { value: "PENDIENTE_COMERCIAL", label: "Pendiente Comercial" },
  { value: "INSTALADO", label: "Instalado" },
  { value: "ANULADO", label: "Anulado" },
];

const ESTADO_BADGE = {
  PENDIENTE_INSTALACION: "bg-orange-50 text-esacom-orange",
  PENDIENTE_COMERCIAL: "bg-purple-50 text-purple-600",
  INSTALADO: "bg-green-50 text-esacom-green",
  ANULADO: "bg-gray-100 text-gray-500",
};

const COLUMNAS = [
  { key: "rut_cliente", label: "RUT Cliente" },
  { key: "nombre_cliente", label: "Nombre" },
  { key: "n_pedido", label: "N° Pedido" },
  { key: "ejecutivo", label: "Ejecutivo" },
  { key: "promocion", label: "Promoción" },
  { key: "comuna", label: "Comuna" },
  { key: "estado_instalacion", label: "Estado" },
  { key: "camada", label: "Camada" },
  { key: "fecha_venta", label: "F. Venta" },
  { key: "precio_venta", label: "Precio" },
];

function valorCelda(v, key) {
  switch (key) {
    case "ejecutivo":
      return v.ejecutivo?.nombre || "";
    case "promocion":
      return v.promocion?.nombre || "";
    case "comuna":
      return v.comuna?.nombre || "";
    case "estado_instalacion":
      return ESTADOS.find((e) => e.value === v.estado_instalacion)?.label || v.estado_instalacion;
    case "precio_venta":
      return v.precio_venta ? `$${Number(v.precio_venta).toLocaleString("es-CL")}` : "—";
    default:
      return v[key] ?? "—";
  }
}

function aCsv(filas) {
  const encabezado = COLUMNAS.map((c) => c.label).join(";");
  const cuerpo = filas
    .map((v) => COLUMNAS.map((c) => `"${String(valorCelda(v, c.key)).replace(/"/g, '""')}"`).join(";"))
    .join("\n");
  return encabezado + "\n" + cuerpo;
}

export default function BaseDatos() {
  const { user } = useAuth();
  const [datos, setDatos] = useState(null);
  const [busqueda, setBusqueda] = useState("");
  const [busquedaAplicada, setBusquedaAplicada] = useState("");
  const [estado, setEstado] = useState("");
  const [camada, setCamada] = useState("");
  const [pagina, setPagina] = useState(1);
  const [error, setError] = useState("");
  const [exportando, setExportando] = useState(false);

  useEffect(() => {
    const params = { page: pagina };
    if (busquedaAplicada) params.search = busquedaAplicada;
    if (estado) params.estado_instalacion = estado;
    if (camada) params.camada = camada;
    fetchVentasPaginado(params)
      .then(setDatos)
      .catch(() => setError("No se pudo cargar la base de datos."));
  }, [pagina, busquedaAplicada, estado, camada]);

  function handleBuscar(e) {
    e.preventDefault();
    setPagina(1);
    setBusquedaAplicada(busqueda);
  }

  async function handleExportar() {
    setExportando(true);
    try {
      const params = {};
      if (busquedaAplicada) params.search = busquedaAplicada;
      if (estado) params.estado_instalacion = estado;
      if (camada) params.camada = camada;
      const filas = await fetchTodasVentas(params);
      const csv = aCsv(filas);
      const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `esacom_ventas_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("No se pudo exportar. Intenta de nuevo.");
    } finally {
      setExportando(false);
    }
  }

  const totalPaginas = datos ? Math.ceil(datos.count / 50) : 1;

  return (
    <Layout
      titulo="Base de Datos"
      items={menuPorUsuario(user)}
    >
      <p className="text-sm text-gray-500 mb-4">
        Todo lo que hoy se consulta en el Excel de ventas, centralizado y en un solo lugar.
      </p>

      <div className="flex flex-col sm:flex-row gap-3 mb-4">
        <form onSubmit={handleBuscar} className="flex-1 flex gap-2">
          <input
            type="text"
            placeholder="Buscar por cliente, RUT, N° pedido o ejecutivo..."
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm
                       focus:outline-none focus:ring-2 focus:ring-esacom-red/40 focus:border-esacom-red"
          />
          <button
            type="submit"
            className="text-xs font-semibold bg-gray-900 text-white rounded-lg px-4 py-2 hover:bg-gray-700 transition-colors"
          >
            Buscar
          </button>
        </form>
        <select
          value={estado}
          onChange={(e) => { setEstado(e.target.value); setPagina(1); }}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm bg-white"
        >
          {ESTADOS.map((e) => (
            <option key={e.value} value={e.value}>{e.label}</option>
          ))}
        </select>
        <input
          type="text"
          placeholder="Camada (2026-08)"
          value={camada}
          onChange={(e) => { setCamada(e.target.value); setPagina(1); }}
          className="w-40 rounded-lg border border-gray-300 px-3 py-2 text-sm"
        />
        <button
          onClick={handleExportar}
          disabled={exportando}
          className="text-xs font-semibold border border-esacom-red text-esacom-red rounded-lg px-4 py-2
                     hover:bg-esacom-red-light transition-colors disabled:opacity-50 whitespace-nowrap"
        >
          {exportando ? "Exportando..." : "Exportar CSV"}
        </button>
      </div>

      {error && <p className="text-sm text-esacom-red bg-esacom-red-light rounded-lg px-4 py-3 mb-4">{error}</p>}

      {!error && datos === null && <div className="h-64 rounded-xl bg-gray-100 animate-pulse" />}

      {!error && datos && (
        <>
          <p className="text-xs text-gray-400 mb-2">{datos.count} registros encontrados</p>
          <div className="bg-white rounded-xl border border-gray-200 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-xs text-gray-500 bg-gray-50">
                  {COLUMNAS.map((c) => (
                    <th key={c.key} className="text-left px-3 py-2 font-medium whitespace-nowrap">{c.label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {datos.results.map((v) => (
                  <tr key={v.id} className="border-b border-gray-100 last:border-0 hover:bg-gray-50">
                    {COLUMNAS.map((c) => (
                      <td key={c.key} className="px-3 py-2 text-xs text-gray-700 whitespace-nowrap">
                        {c.key === "estado_instalacion" ? (
                          <span className={`px-2 py-0.5 rounded-full text-[11px] font-medium ${ESTADO_BADGE[v.estado_instalacion]}`}>
                            {valorCelda(v, c.key)}
                          </span>
                        ) : (
                          valorCelda(v, c.key)
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between mt-4">
            <button
              onClick={() => setPagina((p) => Math.max(1, p - 1))}
              disabled={!datos.previous}
              className="text-xs font-medium text-gray-600 border border-gray-300 rounded-lg px-3 py-1.5
                         hover:border-esacom-red hover:text-esacom-red disabled:opacity-40 disabled:hover:border-gray-300 disabled:hover:text-gray-600"
            >
              ← Anterior
            </button>
            <span className="text-xs text-gray-400">Página {pagina} de {totalPaginas || 1}</span>
            <button
              onClick={() => setPagina((p) => p + 1)}
              disabled={!datos.next}
              className="text-xs font-medium text-gray-600 border border-gray-300 rounded-lg px-3 py-1.5
                         hover:border-esacom-red hover:text-esacom-red disabled:opacity-40 disabled:hover:border-gray-300 disabled:hover:text-gray-600"
            >
              Siguiente →
            </button>
          </div>
        </>
      )}
    </Layout>
  );
}
