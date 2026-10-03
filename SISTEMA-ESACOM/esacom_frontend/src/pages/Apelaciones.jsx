import { useEffect, useMemo, useState } from "react";
import Layout from "../components/Layout";
import { useAuth } from "../context/AuthContext";
import { menuPorUsuario } from "../utils/navigation";
import { ADMIN_URL } from "../api/client";
import {
  fetchApelaciones,
  detectarApelaciones,
  excluirApelacion,
  enviarApelacion,
  descargarApelacionesExcel,
} from "../api/apelaciones";

const ESTADO_ESTILO = {
  DETECTADA: "bg-blue-50 text-blue-700",
  EXCLUIDA: "bg-gray-100 text-gray-500",
  ENVIADA: "bg-esacom-red-light text-esacom-red",
  APROBADA_EN_PLAZO: "bg-green-50 text-esacom-green",
  APROBADA_FUERA_PLAZO: "bg-orange-50 text-esacom-orange",
  RECHAZADA: "bg-red-50 text-red-600",
};

const ESTADO_LABEL = {
  DETECTADA: "Detectada",
  EXCLUIDA: "Excluida",
  ENVIADA: "Enviada",
  APROBADA_EN_PLAZO: "Aprobada — En Plazo",
  APROBADA_FUERA_PLAZO: "Aprobada — Fuera de Plazo",
  RECHAZADA: "Rechazada",
};

const MOTIVO_LABEL = {
  ACREDITACION: "Acreditación",
  APROVISIONAMIENTO: "Aprovisionamiento",
  SUSPENSION: "Cliente suspendido",
};

function mensajeError(error, fallback) {
  return error?.response?.data?.detail || fallback;
}

export default function Apelaciones() {
  const { user } = useAuth();
  const [apelaciones, setApelaciones] = useState(null);
  const [error, setError] = useState("");
  const [detectando, setDetectando] = useState(false);
  const [procesandoId, setProcesandoId] = useState(null);
  const [mensaje, setMensaje] = useState("");
  const [estado, setEstado] = useState("");
  const [motivo, setMotivo] = useState("");
  const [busqueda, setBusqueda] = useState("");

  function cargar() {
    setError("");
    fetchApelaciones({ page_size: 500 })
      .then(setApelaciones)
      .catch((e) => setError(mensajeError(e, "No se pudo cargar el listado de apelaciones.")));
  }

  useEffect(cargar, []);

  async function handleDetectar() {
    setDetectando(true);
    setMensaje("");
    setError("");
    try {
      const r = await detectarApelaciones();
      setMensaje(`${r.apelaciones_nuevas} apelación(es) nueva(s) detectada(s) sobre ${r.cortes_revisados} cortes revisados.`);
      cargar();
    } catch (e) {
      setError(mensajeError(e, "No se pudo correr la detección automática."));
    } finally {
      setDetectando(false);
    }
  }

  async function handleExcluir(id) {
    setProcesandoId(id);
    setError("");
    try {
      await excluirApelacion(id);
      setMensaje("Apelación excluida correctamente.");
      cargar();
    } catch (e) {
      setError(mensajeError(e, "No se pudo excluir la apelación."));
    } finally {
      setProcesandoId(null);
    }
  }

  async function handleEnviar(id) {
    setProcesandoId(id);
    setError("");
    try {
      await enviarApelacion(id);
      setMensaje("Apelación enviada y marcada como ENVIADA.");
      cargar();
    } catch (e) {
      setError(mensajeError(e, "No se pudo enviar la apelación. Revisa la configuración de correo."));
    } finally {
      setProcesandoId(null);
    }
  }

  const filtradas = useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    return (apelaciones || []).filter((a) => {
      if (estado && a.estado !== estado) return false;
      if (motivo && a.motivo !== motivo) return false;
      if (!q) return true;
      const texto = [
        a.corte?.venta?.n_pedido,
        a.corte?.venta?.rut_cliente,
        a.corte?.venta?.ejecutivo?.nombre,
        a.observacion,
        a.bill_no,
      ].filter(Boolean).join(" ").toLowerCase();
      return texto.includes(q);
    });
  }, [apelaciones, estado, motivo, busqueda]);

  return (
    <Layout
      titulo="Seguimiento apelaciones"
      items={menuPorUsuario(user)}
    >
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-4">
        <div>
          <p className="text-sm text-gray-500">Casos detectados por reglas de pago y aprovisionamiento, con trazabilidad antes del envío.</p>
          <p className="text-[11px] text-gray-400 mt-1">
            {["GERENCIA","OPERACIONES"].includes(user?.cargo)
              ? "El envío real requiere configurar APELACIONES_EMAIL_TO en el .env."
              : "Supervisor puede detectar y revisar casos; el envío externo a Claro queda reservado a Gerencia."}
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => descargarApelacionesExcel({ estado: estado || undefined, motivo: motivo || undefined })} className="text-xs font-semibold bg-white border border-gray-300 text-gray-700 rounded-lg px-4 py-2 hover:bg-gray-50">Exportar Excel</button>
          <button
            onClick={handleDetectar}
            disabled={detectando}
            className="text-xs font-semibold bg-esacom-red text-white rounded-lg px-4 py-2 hover:bg-esacom-red-dark transition-colors disabled:opacity-60"
          >
            {detectando ? "Detectando..." : "Detección automática"}
          </button>
        </div>
      </div>

      {mensaje && <p className="text-sm text-esacom-green bg-green-50 rounded-lg px-4 py-2 mb-4">{mensaje}</p>}
      {error && <p className="text-sm text-esacom-red bg-esacom-red-light rounded-lg px-4 py-3 mb-4">{error}</p>}

      {apelaciones && apelaciones.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-3 mb-4 grid grid-cols-1 md:grid-cols-[1fr_220px_220px] gap-3">
          <input
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            placeholder="Buscar pedido, RUT, ejecutivo o Bill No..."
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
          <select value={estado} onChange={(e) => setEstado(e.target.value)} className="rounded-lg border border-gray-300 px-3 py-2 text-sm bg-white">
            <option value="">Todos los estados</option>
            {Object.entries(ESTADO_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
          <select value={motivo} onChange={(e) => setMotivo(e.target.value)} className="rounded-lg border border-gray-300 px-3 py-2 text-sm bg-white">
            <option value="">Todos los motivos</option>
            {Object.entries(MOTIVO_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </div>
      )}

      {!error && apelaciones === null && <div className="h-64 rounded-xl bg-gray-100 animate-pulse" />}

      {!error && apelaciones?.length === 0 && (
        <div className="rounded-xl border border-dashed border-gray-300 bg-white p-10 text-center text-sm text-gray-400">
          No hay apelaciones detectadas todavía. Prueba “Detección automática”.
        </div>
      )}

      {!error && apelaciones && apelaciones.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-x-auto">
          <table className="w-full text-sm min-w-[1050px]">
            <thead className="bg-gray-900 text-white text-xs">
              <tr>
                <th className="text-left font-medium px-4 py-3">Condición</th>
                <th className="text-left font-medium px-4 py-3">Pedido</th>
                <th className="text-left font-medium px-4 py-3">RUT</th>
                <th className="text-left font-medium px-4 py-3">Ejecutivo</th>
                <th className="text-left font-medium px-4 py-3">Corte</th>
                <th className="text-left font-medium px-4 py-3">Motivo / Observación</th>
                <th className="text-left font-medium px-4 py-3">Estado</th>
                <th className="text-right font-medium px-4 py-3">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {filtradas.map((a) => (
                <tr key={a.id} className="border-b border-gray-100 last:border-0 align-top">
                  <td className="px-4 py-3 text-xs font-medium text-gray-700">{MOTIVO_LABEL[a.motivo] || a.motivo}</td>
                  <td className="px-4 py-3 text-xs text-gray-700">{a.corte.venta.n_pedido}</td>
                  <td className="px-4 py-3 text-xs text-gray-700">{a.corte.venta.rut_cliente}</td>
                  <td className="px-4 py-3 text-xs text-gray-700">{a.corte.venta.ejecutivo?.nombre || "—"}</td>
                  <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">{a.corte.mes_ano} · {a.corte.boleta}</td>
                  <td className="px-4 py-3 text-xs text-gray-500 max-w-sm">{a.observacion || "—"}</td>
                  <td className="px-4 py-3">
                    <span className={`text-[11px] font-medium px-2 py-1 rounded-full ${ESTADO_ESTILO[a.estado] || "bg-gray-100 text-gray-500"}`}>
                      {ESTADO_LABEL[a.estado] || a.estado}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right whitespace-nowrap">
                    {a.estado === "DETECTADA" && (
                      <>
                        <button
                          onClick={() => handleExcluir(a.id)}
                          disabled={procesandoId === a.id}
                          className="text-xs text-gray-500 hover:text-esacom-red mr-3 disabled:opacity-40"
                        >Excluir</button>
                        {["GERENCIA","OPERACIONES"].includes(user?.cargo) ? (
                          <button
                            onClick={() => handleEnviar(a.id)}
                            disabled={procesandoId === a.id}
                            className="text-xs font-medium text-esacom-red hover:underline disabled:opacity-40"
                          >{procesandoId === a.id ? "Procesando..." : "Enviar a Claro"}</button>
                        ) : (
                          <span className="text-[11px] text-gray-400">Pendiente de envío por Gerencia</span>
                        )}
                      </>
                    )}
                  </td>
                </tr>
              ))}
              {filtradas.length === 0 && (
                <tr><td colSpan="8" className="px-4 py-8 text-center text-gray-400">No hay apelaciones para este filtro.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </Layout>
  );
}
