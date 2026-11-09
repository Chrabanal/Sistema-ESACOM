import { useCallback, useEffect, useMemo, useState } from "react";
import Layout from "../components/Layout";
import { fetchAccionables } from "../api/dashboard";
import { useAuth } from "../context/AuthContext";
import { menuPorUsuario } from "../utils/navigation";

const COLUMNAS = [
  {
    key: "vencida_gestionable",
    label: "VENCIDA GESTIONABLE",
    titulo: "Todavía puedes recuperarla",
    ayuda: "Entre +1 y +8 días",
    border: "border-orange-500",
    text: "text-orange-700",
    bg: "bg-orange-50/70",
    ring: "ring-orange-200",
  },
  {
    key: "vence_hoy",
    label: "VENCE HOY",
    titulo: "Gestión durante hoy",
    ayuda: "Prioridad alta",
    border: "border-yellow-500",
    text: "text-yellow-700",
    bg: "bg-yellow-50/70",
    ring: "ring-yellow-200",
  },
  {
    key: "por_vencer",
    label: "POR VENCER",
    titulo: "Aún estás a tiempo",
    ayuda: "Anticipar el pago",
    border: "border-blue-500",
    text: "text-blue-700",
    bg: "bg-blue-50/70",
    ring: "ring-blue-200",
  },
  {
    key: "vencida",
    label: "FUERA DE PLAZO",
    titulo: "Ventana de gestión superada",
    ayuda: "+9 días o más",
    border: "border-red-500",
    text: "text-red-700",
    bg: "bg-red-50/70",
    ring: "ring-red-200",
  },
];

const BADGE = {
  por_vencer: "bg-blue-50 text-blue-700 border-blue-200",
  vence_hoy: "bg-yellow-50 text-yellow-800 border-yellow-200",
  vencida_gestionable: "bg-orange-50 text-orange-700 border-orange-200",
  vencida: "bg-red-50 text-red-700 border-red-200",
};

function telefonoWhatsApp(tel) {
  if (!tel) return null;
  let limpio = String(tel).replace(/\D/g, "").replace(/^0+/, "");
  if (limpio.startsWith("56")) limpio = limpio.slice(2);
  return limpio ? `https://wa.me/56${limpio}` : null;
}

function etiquetaBoleta(boleta) {
  return boleta === "B1" ? "1ª Boleta" : boleta === "B2" ? "2ª Boleta" : "3ª Boleta";
}

function fechaCL(fecha) {
  if (!fecha) return "—";
  const [ano, mes, dia] = String(fecha).split("-");
  return dia && mes && ano ? `${dia}-${mes}-${ano}` : fecha;
}

function reconstruirBucket(items) {
  const grupos = new Map();
  const clientes = new Set();

  items.forEach((item) => {
    const nombre = `${item.camada} · ${etiquetaBoleta(item.boleta)}`;

    if (!grupos.has(nombre)) {
      grupos.set(nombre, {
        nombre,
        rgu: 0,
        clientes: new Set(),
        casos: 0,
      });
    }

    const g = grupos.get(nombre);
    g.rgu += Number(item.rgu || 0);
    g.clientes.add(item.rut_cliente);
    g.casos += 1;
    clientes.add(item.rut_cliente);
  });

  return {
    rgu: items.reduce((acc, item) => acc + Number(item.rgu || 0), 0),
    clientes: clientes.size,
    casos: items.length,
    camadas: [...grupos.values()].map((g) => ({
      nombre: g.nombre,
      rgu: g.rgu,
      clientes: g.clientes.size,
      casos: g.casos,
    })),
    items,
  };
}

export default function SeguimientoBoletas() {
  const { user } = useAuth();

  const [datos, setDatos] = useState(null);
  const [error, setError] = useState("");
  const [abierto, setAbierto] = useState(() => {
    const estado = new URLSearchParams(window.location.search).get("estado");
    return ["por_vencer", "vence_hoy", "vencida_gestionable", "vencida"].includes(estado)
      ? estado
      : "vencida_gestionable";
  });
  const [ejecutivoFiltro, setEjecutivoFiltro] = useState(() => {
    return new URLSearchParams(window.location.search).get("ejecutivo") || "";
  });
  const [actualizando, setActualizando] = useState(false);
  const [refrescadoEn, setRefrescadoEn] = useState(null);

  const cargarAccionables = useCallback(async ({ silencioso = false } = {}) => {
    if (!silencioso) setActualizando(true);

    try {
      const r = await fetchAccionables();
      setDatos(r);
      setRefrescadoEn(new Date());
      setError("");
    } catch {
      if (!silencioso) {
        setError("No se pudo actualizar tus accionables.");
      }
    } finally {
      if (!silencioso) setActualizando(false);
    }
  }, []);

  useEffect(() => {
    cargarAccionables();

    const timer = window.setInterval(
      () => cargarAccionables({ silencioso: true }),
      60_000
    );

    const onFocus = () => cargarAccionables({ silencioso: true });

    window.addEventListener("focus", onFocus);

    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", onFocus);
    };
  }, [cargarAccionables]);

  const ejecutivos = useMemo(() => {
    if (!datos) return [];

    const nombres = new Set();

    COLUMNAS.forEach(({ key }) => {
      (datos?.[key]?.items || []).forEach((item) => {
        if (item.ejecutivo) nombres.add(item.ejecutivo);
      });
    });

    return [...nombres].sort((a, b) => a.localeCompare(b, "es"));
  }, [datos]);

  const datosFiltrados = useMemo(() => {
    if (!datos || !ejecutivoFiltro) return datos;

    const salida = { ...datos };

    COLUMNAS.forEach(({ key }) => {
      salida[key] = reconstruirBucket(
        (datos?.[key]?.items || []).filter(
          (item) => item.ejecutivo === ejecutivoFiltro
        )
      );
    });

    return salida;
  }, [datos, ejecutivoFiltro]);

  const resumenGestion = useMemo(() => {
    const clientes = new Set();
    let rgu = 0;
    let casos = 0;

    ["por_vencer", "vence_hoy", "vencida_gestionable"].forEach((clave) => {
      const bucket = datosFiltrados?.[clave] || {};

      rgu += Number(bucket.rgu || 0);
      casos += Number(bucket.casos || 0);

      (bucket.items || []).forEach((item) => {
        if (item.rut_cliente) clientes.add(item.rut_cliente);
      });
    });

    return {
      clientes: clientes.size,
      rgu,
      casos,
    };
  }, [datosFiltrados]);

  const clientesUrgentes = useMemo(() => {
    const ruts = new Set();

    [
      ...(datosFiltrados?.vence_hoy?.items || []),
      ...(datosFiltrados?.vencida_gestionable?.items || []),
    ].forEach((item) => {
      if (item.rut_cliente) ruts.add(item.rut_cliente);
    });

    return ruts.size;
  }, [datosFiltrados]);

  return (
    <Layout titulo="Mis Accionables" items={menuPorUsuario(user)}>
      <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-sm text-gray-600">
            Gestiona tus clientes antes de que termine su ventana de pago.
          </p>

          <p className="mt-1 text-xs text-gray-400">
            Se muestran boletas pendientes de camadas abiertas: antes del
            vencimiento, el día del vencimiento y hasta 8 días después.
          </p>

          <p className="mt-2 text-[10px] text-gray-400">
            Actualizado:{" "}
            {refrescadoEn
              ? refrescadoEn.toLocaleString("es-CL")
              : "—"}{" "}
            · refresco automático cada 60 segundos.
          </p>
        </div>

        <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
          {["SUPERVISOR", "GERENCIA", "OPERACIONES"].includes(user?.cargo) &&
            ejecutivos.length > 0 && (
              <select
                value={ejecutivoFiltro}
                onChange={(e) => setEjecutivoFiltro(e.target.value)}
                className="min-h-11 rounded-xl border border-gray-300 bg-white px-3 py-2 text-sm"
              >
                <option value="">Todos los ejecutivos</option>
                {ejecutivos.map((nombre) => (
                  <option key={nombre} value={nombre}>
                    {nombre}
                  </option>
                ))}
              </select>
            )}

          <button
            type="button"
            onClick={() => cargarAccionables()}
            disabled={actualizando}
            className="min-h-11 rounded-xl bg-gray-900 px-4 text-xs font-semibold text-white shadow-sm transition hover:bg-gray-800 disabled:opacity-50"
          >
            {actualizando ? "Actualizando…" : "↻ Actualizar"}
          </button>
        </div>
      </div>

      {error && (
        <p className="mb-4 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </p>
      )}

      {!error && datos === null && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="h-32 animate-pulse rounded-2xl bg-gray-100" />
          <div className="h-32 animate-pulse rounded-2xl bg-gray-100" />
        </div>
      )}

      {!error && datos && (
        <>
          <div className="mb-5 grid gap-3 lg:grid-cols-2">
            <section className="rounded-2xl border border-blue-100 bg-blue-50/60 p-4 shadow-sm">
              <p className="text-[10px] font-bold uppercase tracking-wide text-blue-600">
                Gestión activa
              </p>

              <div className="mt-2 flex items-end justify-between gap-4">
                <div>
                  <p className="text-4xl font-black tracking-tight text-gray-900">
                    {resumenGestion.clientes}
                  </p>
                  <p className="mt-1 text-xs text-gray-600">
                    clientes dentro de la ventana de gestión
                  </p>
                </div>

                <div className="text-right">
                  <p className="text-xl font-extrabold text-blue-700">
                    {resumenGestion.rgu} RGU
                  </p>
                  <p className="text-[11px] text-gray-500">
                    {resumenGestion.casos} casos
                  </p>
                </div>
              </div>
            </section>

            <section
              className={`rounded-2xl border p-4 shadow-sm ${
                clientesUrgentes > 0
                  ? "border-orange-200 bg-orange-50/70"
                  : "border-green-100 bg-green-50/60"
              }`}
            >
              <p
                className={`text-[10px] font-bold uppercase tracking-wide ${
                  clientesUrgentes > 0 ? "text-orange-700" : "text-green-700"
                }`}
              >
                Prioridad inmediata
              </p>

              <div className="mt-2 flex items-end justify-between gap-4">
                <div>
                  <p className="text-4xl font-black tracking-tight text-gray-900">
                    {clientesUrgentes}
                  </p>
                  <p className="mt-1 text-xs text-gray-600">
                    clientes que requieren atención prioritaria
                  </p>
                </div>

                <div className="text-right text-xs">
                  <p className="font-semibold text-yellow-700">
                    Vence hoy: {datosFiltrados?.vence_hoy?.clientes || 0}
                  </p>
                  <p className="mt-1 font-semibold text-orange-700">
                    +1 a +8 días:{" "}
                    {datosFiltrados?.vencida_gestionable?.clientes || 0}
                  </p>
                </div>
              </div>
            </section>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {COLUMNAS.map((col) => {
              const bucket = datosFiltrados?.[col.key] || {
                rgu: 0,
                clientes: 0,
                casos: 0,
                camadas: [],
                items: [],
              };

              const items = bucket.items || [];
              const seleccionado = abierto === col.key;

              return (
                <button
                  type="button"
                  key={col.key}
                  onClick={() => setAbierto(col.key)}
                  className={`rounded-2xl border border-gray-200 border-t-4 ${
                    col.border
                  } p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-md ${
                    seleccionado
                      ? `${col.bg} ring-2 ${col.ring}`
                      : "bg-white"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className={`text-xs font-bold ${col.text}`}>
                        {col.label}
                      </p>
                      <p className="mt-1 text-[10px] text-gray-400">
                        {col.titulo}
                      </p>
                    </div>

                    <span className="rounded-full bg-white/80 px-2 py-1 text-[9px] font-medium text-gray-500">
                      {col.ayuda}
                    </span>
                  </div>

                  <div className="mt-4 flex items-end justify-between gap-3">
                    <div>
                      <p className="text-4xl font-black tracking-tight text-gray-900">
                        {bucket.rgu}
                      </p>
                      <p className="text-[11px] font-semibold text-gray-500">
                        RGU
                      </p>
                    </div>

                    <div className="text-right text-xs text-gray-500">
                      <p>
                        <strong className="text-gray-800">
                          {bucket.clientes}
                        </strong>{" "}
                        clientes
                      </p>
                      <p className="mt-1">
                        <strong className="text-gray-800">
                          {bucket.casos}
                        </strong>{" "}
                        casos
                      </p>
                    </div>
                  </div>

                  <div className="mt-4 space-y-2">
                    {bucket.camadas?.length === 0 && (
                      <p className="rounded-xl bg-gray-50 px-3 py-2 text-xs text-gray-300">
                        Sin casos en este rango.
                      </p>
                    )}

                    {(bucket.camadas || []).map((c) => (
                      <div
                        key={c.nombre}
                        className="flex items-center justify-between rounded-xl border border-gray-100 bg-white/80 px-3 py-2"
                      >
                        <span className="text-xs text-gray-600">
                          {c.nombre}
                        </span>

                        <span className="text-xs font-semibold text-gray-900">
                          {c.rgu} RGU{" "}
                          <span className="font-normal text-gray-400">
                            · {c.casos} casos
                          </span>
                        </span>
                      </div>
                    ))}
                  </div>

                  {items.length > 0 && (
                    <p className={`mt-3 text-[11px] font-semibold ${col.text}`}>
                      {seleccionado
                        ? "Viendo estos casos ↓"
                        : `Ver ${items.length} caso(s) →`}
                    </p>
                  )}
                </button>
              );
            })}
          </div>

          {(() => {
            const bucket = datosFiltrados?.[abierto] || {};
            const items = bucket.items || [];
            const columna = COLUMNAS.find((c) => c.key === abierto);

            if (!items.length) return null;

            return (
              <div className="mt-5 overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">
                <div className="flex flex-col gap-2 border-b border-gray-100 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="text-sm font-bold text-gray-900">
                      {abierto === "vencida"
                        ? "Casos fuera de ventana"
                        : "Clientes para gestionar"}
                    </p>

                    <div className="mt-1 flex items-center gap-2">
                      <span
                        className={`rounded-full border px-2.5 py-1 text-[10px] font-bold ${
                          BADGE[abierto] || "bg-gray-50 text-gray-600"
                        }`}
                      >
                        {columna?.label}
                      </span>

                      <span className="text-[11px] text-gray-400">
                        {items.length} registros
                      </span>
                    </div>
                  </div>

                  <p className="text-xs text-gray-400">
                    {bucket.rgu || 0} RGU · {bucket.clientes || 0} clientes
                  </p>
                </div>

                <div className="divide-y divide-gray-100 md:hidden">
                  {items.map((item) => {
                    const wa = telefonoWhatsApp(item.telefono_cliente);

                    return (
                      <div key={`mobile-${item.corte_id}`} className="p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="text-sm font-bold leading-snug text-gray-900">
                              {item.nombre_cliente || item.rut_cliente}
                            </p>

                            <p className="mt-0.5 text-xs text-gray-400">
                              {item.rut_cliente}
                            </p>
                          </div>

                          <span className="shrink-0 rounded-full bg-gray-100 px-2.5 py-1 text-[11px] font-bold text-gray-700">
                            {item.rgu} RGU
                          </span>
                        </div>

                        <div className="mt-3">
                          <span
                            className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-bold ${
                              BADGE[item.estado_gestion] ||
                              "bg-gray-50 text-gray-600"
                            }`}
                          >
                            {item.estado_vencimiento}
                          </span>
                        </div>

                        <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                          <div className="rounded-xl bg-gray-50 p-2.5">
                            <span className="block text-[9px] font-bold uppercase text-gray-400">
                              Vencimiento
                            </span>
                            <span className="mt-1 block font-semibold text-gray-700">
                              {fechaCL(item.fecha_vencimiento)}
                            </span>
                          </div>

                          <div className="rounded-xl bg-gray-50 p-2.5">
                            <span className="block text-[9px] font-bold uppercase text-gray-400">
                              Límite +8
                            </span>
                            <span className="mt-1 block font-semibold text-gray-700">
                              {fechaCL(item.fecha_limite_pago)}
                            </span>
                          </div>

                          <div className="rounded-xl bg-gray-50 p-2.5">
                            <span className="block text-[9px] font-bold uppercase text-gray-400">
                              Pedido
                            </span>
                            <span className="mt-1 block break-all font-medium text-gray-700">
                              {item.pedido}
                            </span>
                          </div>

                          <div className="rounded-xl bg-gray-50 p-2.5">
                            <span className="block text-[9px] font-bold uppercase text-gray-400">
                              Boleta
                            </span>
                            <span className="mt-1 block font-medium text-gray-700">
                              {item.camada} · {etiquetaBoleta(item.boleta)}
                            </span>
                          </div>
                        </div>

                        {wa ? (
                          <a
                            href={wa}
                            target="_blank"
                            rel="noreferrer"
                            className="mt-3 flex min-h-11 w-full items-center justify-center rounded-xl bg-green-600 text-xs font-bold text-white shadow-sm transition hover:bg-green-700"
                          >
                            Contactar por WhatsApp
                          </a>
                        ) : (
                          <p className="mt-3 rounded-xl bg-gray-50 p-3 text-center text-xs text-gray-300">
                            Cliente sin teléfono registrado.
                          </p>
                        )}
                      </div>
                    );
                  })}
                </div>

                <div className="hidden overflow-x-auto md:block">
                  <table className="w-full min-w-[1100px] text-xs">
                    <thead className="bg-gray-50 text-gray-500">
                      <tr>
                        <th className="px-3 py-3 text-left font-medium">
                          Cliente
                        </th>
                        <th className="px-3 py-3 text-left font-medium">
                          Pedido
                        </th>
                        <th className="px-3 py-3 text-left font-medium">
                          Boleta
                        </th>
                        <th className="px-3 py-3 text-left font-medium">
                          Prioridad
                        </th>
                        <th className="px-3 py-3 text-left font-medium">
                          Vencimiento
                        </th>
                        <th className="px-3 py-3 text-left font-medium">
                          Límite +8
                        </th>
                        <th className="px-3 py-3 text-right font-medium">
                          RGU
                        </th>
                        <th className="px-3 py-3 text-right font-medium">
                          Contacto
                        </th>
                      </tr>
                    </thead>

                    <tbody>
                      {items.map((item) => {
                        const wa = telefonoWhatsApp(item.telefono_cliente);

                        return (
                          <tr
                            key={item.corte_id}
                            className="border-t border-gray-100 hover:bg-gray-50/70"
                          >
                            <td className="px-3 py-3">
                              <p className="font-semibold text-gray-900">
                                {item.nombre_cliente || item.rut_cliente}
                              </p>
                              <p className="mt-0.5 text-[11px] text-gray-400">
                                {item.rut_cliente}
                              </p>
                            </td>

                            <td className="px-3 py-3 text-gray-700">
                              {item.pedido}
                            </td>

                            <td className="px-3 py-3 text-gray-700">
                              {item.camada} · {etiquetaBoleta(item.boleta)}
                            </td>

                            <td className="px-3 py-3">
                              <span
                                className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-bold ${
                                  BADGE[item.estado_gestion] ||
                                  "bg-gray-50 text-gray-600"
                                }`}
                              >
                                {item.estado_vencimiento}
                              </span>
                            </td>

                            <td className="px-3 py-3 font-medium text-gray-700">
                              {fechaCL(item.fecha_vencimiento)}
                            </td>

                            <td className="px-3 py-3 text-gray-500">
                              {fechaCL(item.fecha_limite_pago)}
                            </td>

                            <td className="px-3 py-3 text-right font-bold text-gray-900">
                              {item.rgu}
                            </td>

                            <td className="px-3 py-3 text-right">
                              {wa ? (
                                <a
                                  href={wa}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="inline-flex min-h-9 items-center justify-center rounded-lg bg-green-50 px-3 font-bold text-green-700 transition hover:bg-green-100"
                                >
                                  WhatsApp
                                </a>
                              ) : (
                                <span className="text-gray-300">
                                  Sin teléfono
                                </span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            );
          })()}
        </>
      )}
    </Layout>
  );
}