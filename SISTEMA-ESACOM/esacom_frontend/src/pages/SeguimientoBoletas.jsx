import { useCallback, useEffect, useMemo, useState } from "react";
import Layout from "../components/Layout";
import { fetchAccionables } from "../api/dashboard";
import { useAuth } from "../context/AuthContext";
import { menuPorUsuario } from "../utils/navigation";

const COLUMNAS = [
  {
    key: "vencidos",
    label: "VENCIDOS",
    color: "border-esacom-red text-esacom-red",
    ayuda: "Gestión inmediata",
  },
  {
    key: "hoy",
    label: "HOY",
    color: "border-esacom-orange text-esacom-orange",
    ayuda: "Vencen hoy",
  },
  {
    key: "manana",
    label: "MAÑANA",
    color: "border-yellow-500 text-yellow-700",
    ayuda: "Vencen mañana",
  },
  {
    key: "prox_3d",
    label: "PRÓX. 3 DÍAS",
    color: "border-esacom-blue text-esacom-blue",
    ayuda: "Próximos vencimientos",
  },
];

function telefonoWhatsApp(tel) {
  if (!tel) return null;

  let limpio = String(tel)
    .replace(/\D/g, "")
    .replace(/^0+/, "");

  if (limpio.startsWith("56")) {
    limpio = limpio.slice(2);
  }

  return limpio ? `https://wa.me/56${limpio}` : null;
}

function etiquetaBoleta(boleta) {
  return boleta === "B1"
    ? "1ª Boleta"
    : boleta === "B2"
      ? "2ª Boleta"
      : "3ª Boleta";
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

    const grupo = grupos.get(nombre);

    grupo.rgu += Number(item.rgu || 0);
    grupo.clientes.add(item.rut_cliente);
    grupo.casos += 1;

    clientes.add(item.rut_cliente);
  });

  return {
    rgu: items.reduce(
      (acc, item) => acc + Number(item.rgu || 0),
      0,
    ),
    clientes: clientes.size,
    casos: items.length,
    camadas: [...grupos.values()].map((grupo) => ({
      nombre: grupo.nombre,
      rgu: grupo.rgu,
      clientes: grupo.clientes.size,
      casos: grupo.casos,
    })),
    items,
  };
}

export default function SeguimientoBoletas() {
  const { user } = useAuth();

  const [datos, setDatos] = useState(null);
  const [error, setError] = useState("");
  const [abierto, setAbierto] = useState("vencidos");
  const [ejecutivoFiltro, setEjecutivoFiltro] = useState("");
  const [busqueda, setBusqueda] = useState("");
  const [actualizando, setActualizando] = useState(false);
  const [refrescadoEn, setRefrescadoEn] = useState(null);

  const cargarAccionables = useCallback(
    async ({ silencioso = false } = {}) => {
      if (!silencioso) {
        setActualizando(true);
      }

      try {
        const respuesta = await fetchAccionables();

        setDatos(respuesta);
        setRefrescadoEn(new Date());
        setError("");
      } catch {
        if (!silencioso) {
          setError("No se pudo actualizar tus accionables.");
        }
      } finally {
        if (!silencioso) {
          setActualizando(false);
        }
      }
    },
    [],
  );

  useEffect(() => {
    cargarAccionables();

    const timer = window.setInterval(
      () => cargarAccionables({ silencioso: true }),
      60_000,
    );

    const onFocus = () => {
      cargarAccionables({ silencioso: true });
    };

    window.addEventListener("focus", onFocus);

    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", onFocus);
    };
  }, [cargarAccionables]);

  const ejecutivos = useMemo(() => {
    if (!datos) {
      return [];
    }

    const nombres = new Set();

    Object.values(datos).forEach((bucket) => {
      (bucket?.items || []).forEach((item) => {
        if (item.ejecutivo) {
          nombres.add(item.ejecutivo);
        }
      });
    });

    return [...nombres].sort((a, b) =>
      a.localeCompare(b, "es"),
    );
  }, [datos]);

  const datosFiltrados = useMemo(() => {
    if (!datos) {
      return datos;
    }

    const textoBusqueda = busqueda
      .trim()
      .toLowerCase();

    if (!ejecutivoFiltro && !textoBusqueda) {
      return datos;
    }

    const salida = {};

    for (const [clave, bucket] of Object.entries(datos)) {
      const items = (bucket?.items || []).filter((item) => {
        const coincideEjecutivo =
          !ejecutivoFiltro ||
          item.ejecutivo === ejecutivoFiltro;

        const textoItem = [
          item.nombre_cliente,
          item.rut_cliente,
          item.pedido,
          item.ejecutivo,
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();

        const coincideBusqueda =
          !textoBusqueda ||
          textoItem.includes(textoBusqueda);

        return coincideEjecutivo && coincideBusqueda;
      });

      salida[clave] = reconstruirBucket(items);
    }

    return salida;
  }, [datos, ejecutivoFiltro, busqueda]);

  const hayResultados = useMemo(() => {
    if (!datosFiltrados) {
      return false;
    }

    return Object.values(datosFiltrados).some(
      (bucket) => (bucket?.items || []).length > 0,
    );
  }, [datosFiltrados]);

  const clientesUrgentes = useMemo(() => {
    if (!datosFiltrados) {
      return 0;
    }

    const ruts = new Set();

    [
      ...(datosFiltrados.vencidos?.items || []),
      ...(datosFiltrados.hoy?.items || []),
    ].forEach((item) => {
      if (item.rut_cliente) {
        ruts.add(item.rut_cliente);
      }
    });

    return ruts.size;
  }, [datosFiltrados]);

  const filtrosActivos =
    busqueda.trim() !== "" ||
    ejecutivoFiltro !== "";

  const limpiarFiltros = () => {
    setBusqueda("");
    setEjecutivoFiltro("");
  };

  return (
    <Layout
      titulo="Mis Accionables"
      items={menuPorUsuario(user)}
    >
      <div className="mb-4 -mt-1 flex flex-col md:flex-row md:items-end md:justify-between gap-3">
        <div>
          <p className="text-sm text-gray-600">
            Prioriza clientes con boletas vencidas o próximas a vencer.
          </p>

          <p className="text-xs text-gray-400 mt-1">
            Solo se muestran boletas pendientes, medibles y asociadas
            al vendedor ESACOM.
          </p>
        </div>

        <div className="flex flex-col sm:flex-row gap-2 sm:items-end">
          <input
            type="search"
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            placeholder="Buscar cliente, RUT o pedido"
            className="min-h-11 rounded-xl border border-gray-300 bg-white px-3 py-2 text-sm sm:min-w-[240px]"
          />

          {[
            "SUPERVISOR",
            "GERENCIA",
            "OPERACIONES",
          ].includes(user?.cargo) &&
            ejecutivos.length > 0 && (
              <select
                value={ejecutivoFiltro}
                onChange={(e) =>
                  setEjecutivoFiltro(e.target.value)
                }
                className="min-h-11 rounded-xl border border-gray-300 bg-white px-3 py-2 text-sm"
              >
                <option value="">
                  Todos con KPI vigente
                </option>

                {ejecutivos.map((nombre) => (
                  <option
                    key={nombre}
                    value={nombre}
                  >
                    {nombre}
                  </option>
                ))}
              </select>
            )}

          {filtrosActivos && (
            <button
              type="button"
              onClick={limpiarFiltros}
              className="min-h-11 rounded-xl border border-gray-300 bg-white px-3 py-2 text-xs font-medium text-gray-600 hover:bg-gray-50"
            >
              Limpiar filtros
            </button>
          )}

          <button
            type="button"
            onClick={() => cargarAccionables()}
            disabled={actualizando}
            className="esacom-primary-btn text-xs"
          >
            {actualizando
              ? "Actualizando…"
              : "↻ Actualizar"}
          </button>
        </div>
      </div>

      <p className="text-[10px] text-gray-400 -mt-2 mb-3">
        Actualizado:{" "}
        {refrescadoEn
          ? refrescadoEn.toLocaleString("es-CL")
          : "—"}{" "}
        · refresco automático cada 60 segundos.
      </p>

      {datos && clientesUrgentes > 0 && (
        <div className="mb-4 rounded-2xl border border-red-100 bg-red-50 px-4 py-3">
          <p className="text-sm font-semibold text-red-800">
            Tienes {clientesUrgentes} cliente(s) que requieren
            atención prioritaria.
          </p>

          <p className="text-xs text-red-600 mt-0.5">
            Revisa primero Vencidos y Hoy.
          </p>
        </div>
      )}

      {error && (
        <p className="text-sm text-esacom-red bg-esacom-red-light rounded-lg px-4 py-3">
          {error}
        </p>
      )}

      {!error && datos === null && (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="h-56 rounded-xl bg-gray-100 animate-pulse"
            />
          ))}
        </div>
      )}

      {!error &&
        datos &&
        filtrosActivos &&
        !hayResultados && (
          <div className="mb-4 rounded-xl border border-dashed border-gray-300 bg-white p-6 text-center">
            <p className="text-sm font-medium text-gray-700">
              No se encontraron resultados.
            </p>

            <p className="text-xs text-gray-400 mt-1">
              Revisa el cliente, RUT, pedido o ejecutivo seleccionado.
            </p>

            <button
              type="button"
              onClick={limpiarFiltros}
              className="mt-4 rounded-lg border border-gray-300 bg-white px-4 py-2 text-xs font-medium text-gray-600 hover:bg-gray-50"
            >
              Limpiar búsqueda
            </button>
          </div>
        )}

      {!error && datos && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3 sm:gap-4">
            {COLUMNAS.map((col) => {
              const bucket =
                datosFiltrados?.[col.key] || {
                  rgu: 0,
                  clientes: 0,
                  casos: 0,
                  camadas: [],
                  items: [],
                };

              const items = bucket.items || [];

              return (
                <button
                  type="button"
                  key={col.key}
                  onClick={() =>
                    setAbierto(col.key)
                  }
                  className={`text-left bg-white rounded-2xl border-t-4 ${
                    col.color.split(" ")[0]
                  } border-x border-b ${
                    abierto === col.key
                      ? "border-x-gray-300 border-b-gray-300 shadow-md"
                      : "border-x-gray-200 border-b-gray-200"
                  } p-4 sm:p-5 active:scale-[0.995] transition`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <p
                      className={`text-xs font-semibold ${
                        col.color.split(" ")[1]
                      }`}
                    >
                      {col.label}
                    </p>

                    <span className="text-[10px] text-gray-400">
                      {col.ayuda}
                    </span>
                  </div>

                  <p className="text-4xl font-bold tracking-tight text-gray-900 mt-1">
                    {bucket.rgu}
                  </p>

                  <p className="text-xs text-gray-500">
                    RGU · {bucket.clientes} clientes ·{" "}
                    {bucket.casos ?? items.length} casos
                  </p>

                  <div className="mt-4 space-y-2">
                    {bucket.camadas.length === 0 && (
                      <p className="text-xs text-gray-300">
                        Sin casos en este rango.
                      </p>
                    )}

                    {bucket.camadas.map((camada) => (
                      <div
                        key={camada.nombre}
                        className="flex items-center justify-between border border-gray-100 rounded-lg px-3 py-2"
                      >
                        <span className="text-xs text-gray-700">
                          {camada.nombre}
                        </span>

                        <span className="text-xs font-medium text-gray-900">
                          {camada.rgu} RGU{" "}
                          <span className="text-gray-400">
                            ({camada.casos} casos)
                          </span>
                        </span>
                      </div>
                    ))}
                  </div>

                  {items.length > 0 && (
                    <p className="text-[11px] text-gray-400 mt-3">
                      Ver {items.length} caso(s) →
                    </p>
                  )}
                </button>
              );
            })}
          </div>

          {(() => {
            const bucket =
              datosFiltrados?.[abierto] || {};

            const items = bucket.items || [];

            if (!items.length) {
              return null;
            }

            return (
              <div className="mt-5 bg-white rounded-xl border border-gray-200 overflow-hidden">
                <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
                  <div>
                    <p className="text-sm font-semibold text-gray-900">
                      Clientes para gestionar
                    </p>

                    <p className="text-xs text-gray-400">
                      {
                        COLUMNAS.find(
                          (columna) =>
                            columna.key === abierto,
                        )?.label
                      }
                    </p>
                  </div>

                  <span className="text-xs text-gray-500">
                    {items.length} registros
                  </span>
                </div>

                <div className="md:hidden divide-y divide-gray-100">
                  {items.map((item) => {
                    const wa =
                      telefonoWhatsApp(
                        item.telefono_cliente,
                      );

                    return (
                      <div
                        key={`mobile-${item.corte_id}`}
                        className="p-4"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="text-sm font-semibold text-gray-900 leading-snug">
                              {item.nombre_cliente ||
                                item.rut_cliente}
                            </p>

                            <p className="text-xs text-gray-400 mt-0.5">
                              {item.rut_cliente}
                            </p>
                          </div>

                          <span className="shrink-0 rounded-full bg-gray-100 px-2.5 py-1 text-[11px] font-semibold text-gray-700">
                            {item.rgu} RGU
                          </span>
                        </div>

                        <div className="mt-3 rounded-xl bg-gray-50 p-3">
                          <p
                            className={`text-xs font-semibold ${
                              item.dias_para_vencer < 0
                                ? "text-red-700"
                                : "text-gray-800"
                            }`}
                          >
                            {item.estado_vencimiento}
                          </p>

                          <p className="text-[11px] text-gray-400 mt-0.5">
                            Vencimiento:{" "}
                            {item.fecha_vencimiento}
                          </p>
                        </div>

                        <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                          <div className="rounded-xl bg-gray-50 p-2.5">
                            <span className="block text-[10px] uppercase text-gray-400">
                              Pedido
                            </span>

                            <span className="font-medium text-gray-700 break-all">
                              {item.pedido}
                            </span>
                          </div>

                          <div className="rounded-xl bg-gray-50 p-2.5">
                            <span className="block text-[10px] uppercase text-gray-400">
                              Boleta
                            </span>

                            <span className="font-medium text-gray-700">
                              {item.camada} ·{" "}
                              {etiquetaBoleta(
                                item.boleta,
                              )}
                            </span>
                          </div>
                        </div>

                        {wa ? (
                          <a
                            href={wa}
                            target="_blank"
                            rel="noreferrer"
                            className="mt-3 min-h-11 w-full rounded-xl bg-green-50 text-green-700 text-xs font-semibold flex items-center justify-center"
                          >
                            Contactar por WhatsApp
                          </a>
                        ) : (
                          <p className="mt-3 text-xs text-gray-300">
                            Cliente sin teléfono registrado.
                          </p>
                        )}
                      </div>
                    );
                  })}
                </div>

                <div className="hidden md:block overflow-x-auto">
                  <table className="w-full text-xs min-w-[900px]">
                    <thead className="bg-gray-50 text-gray-500">
                      <tr>
                        <th className="text-left px-3 py-2 font-medium">
                          Cliente
                        </th>
                        <th className="text-left px-3 py-2 font-medium">
                          Pedido
                        </th>
                        <th className="text-left px-3 py-2 font-medium">
                          Boleta
                        </th>
                        <th className="text-left px-3 py-2 font-medium">
                          Prioridad
                        </th>
                        <th className="text-left px-3 py-2 font-medium">
                          Vencimiento
                        </th>
                        <th className="text-right px-3 py-2 font-medium">
                          RGU
                        </th>
                        <th className="text-right px-3 py-2 font-medium">
                          Contacto
                        </th>
                      </tr>
                    </thead>

                    <tbody>
                      {items.map((item) => {
                        const wa =
                          telefonoWhatsApp(
                            item.telefono_cliente,
                          );

                        return (
                          <tr
                            key={item.corte_id}
                            className="border-t border-gray-100"
                          >
                            <td className="px-3 py-2">
                              <p className="font-medium text-gray-800">
                                {item.nombre_cliente ||
                                  item.rut_cliente}
                              </p>
                              <p className="text-gray-400">
                                {item.rut_cliente}
                              </p>
                            </td>

                            <td className="px-3 py-2 text-gray-700">
                              {item.pedido}
                            </td>

                            <td className="px-3 py-2 text-gray-700">
                              {item.camada} ·{" "}
                              {etiquetaBoleta(
                                item.boleta,
                              )}
                            </td>

                            <td
                              className={`px-3 py-2 font-medium ${
                                item.dias_para_vencer < 0
                                  ? "text-red-700"
                                  : "text-gray-700"
                              }`}
                            >
                              {item.estado_vencimiento}
                            </td>

                            <td className="px-3 py-2 text-gray-700">
                              {item.fecha_vencimiento}
                            </td>

                            <td className="px-3 py-2 text-right font-medium">
                              {item.rgu}
                            </td>

                            <td className="px-3 py-2 text-right">
                              {wa ? (
                                <a
                                  href={wa}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="text-green-700 font-medium hover:underline"
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
