import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import PortalEjecutivo from "../src/pages/PortalEjecutivo";

vi.mock("../src/context/AuthContext", () => ({
  useAuth: () => ({ user: { nombre: "Brian Aburto", cargo: "EJECUTIVO" }, logout: vi.fn() }),
}));

const CORTES = [
  { pagadas: 11, pendientes: 0, no_pago: 0, fuera_plazo: 0, sin_boleta: 0, total: 11, meta_pct: 85, pct_cumplimiento: 100, pct_proyectado: 100, cumplimiento_meta_pct: 117.6, faltan_para_meta: 0, semaforo: "verde", mes_ano: "2026-08", boleta: "B1", tiene_datos: true, gestion: {}, estado_mes: "EN_CURSO" },
];

const VENTA = {
  id: 364, rut_cliente: "16xxxxx-x", nombre_cliente: "GLORIA PAMELA ARBULO NUNEZ", telefono_cliente: "956827600",
  n_pedido: "1-285xxxxxx", camada: "2026-09",
  promocion: { id: 1, nombre: "VTR 2P TV-INT", rgu: 2 }, estado_instalacion: "PENDIENTE_INSTALACION",
};

const registrarGestionMock = vi.fn(() => Promise.resolve({ id: 1, tipo: "LLAMADA" }));

vi.mock("../src/api/dashboard", () => ({
  fetchDashboardKpiCompleto: () => Promise.resolve({
    perfil_kpi: "REGULAR", cortes: CORTES,
    historico_kpi: [{ ...CORTES[0], mes_ano: "2026-07", boleta: "B1", meta_pct: 85, pct_cumplimiento: 88.24, estado_mes: "CERRADO" }],
    mes_actual: "2026-09", mes_anterior: "2026-08",
    resumen_mes_actual: { mes: "2026-09", total: 2, instaladas: 1, pendiente_instalacion: 0, pendiente_comercial: 0, avance_instalacion_pct: 50 },
    produccion_mes_actual: {
      kpi_fijo_rgu: 4, rgu_fijo_vendidos: 4, rgu_fijo_gestionables: 3, ventas_fijo: 2, rgu_fijo_anulados: 1,
      kpi_movil_portadas: 2, movil: { principal: 1, adicional: 1 }
    },
    estado_datos: null,
  }),
}));

vi.mock("../src/api/apelaciones", () => ({
  fetchVentas: () => Promise.resolve([VENTA]),
  registrarGestion: (...args) => registrarGestionMock(...args),
}));

function conRouter(ui) { return <MemoryRouter>{ui}</MemoryRouter>; }

describe("PortalEjecutivo nueva experiencia", () => {
  it("quita Estado de tus datos y prioriza resumen ESACOM + Calidad Claro", async () => {
    render(conRouter(<PortalEjecutivo />));
    expect(await screen.findByText("Resumen actual")).toBeInTheDocument();
    expect(screen.queryByText("Estado de tus datos")).not.toBeInTheDocument();
    expect(screen.getByPlaceholderText("Buscar por RUT o nombre…")).toBeInTheDocument();
    expect(screen.getByText("4 RGU vendidos")).toBeInTheDocument();
    expect(screen.getByText(/2 ventas · 3 gestionables · 1 RGU anulado/)).toBeInTheDocument();
    expect(screen.getByText("2 portadas")).toBeInTheDocument();
    expect(screen.getByText(/Septiembre 2026.*ventas y RGU actuales/)).toBeInTheDocument();
    expect(screen.getByText(/Agosto 2026.*período que Claro está midiendo/)).toBeInTheDocument();
  });

  it("muestra solo el mes de Calidad en curso y separa el histórico mensual", async () => {
    render(conRouter(<PortalEjecutivo />));
    expect(await screen.findByText("KPI Calidad en curso")).toBeInTheDocument();
    expect(screen.getByText(/Septiembre 2026 · aún sin medición de Calidad/)).toBeInTheDocument();
    fireEvent.click(screen.getByText("Histórico"));
    expect(await screen.findByText("Histórico KPI")).toBeInTheDocument();
    expect(screen.getByText("Julio 2026")).toBeInTheDocument();
  });

  it("Mis Clientes solo ofrece mes actual/anterior y no filtro Todos", async () => {
    render(conRouter(<PortalEjecutivo />));
    fireEvent.click(screen.getByText("Mis Clientes"));
    expect(await screen.findByText("GLORIA PAMELA ARBULO NUNEZ")).toBeInTheDocument();
    expect(screen.getByText("Mes actual")).toBeInTheDocument();
    expect(screen.getByText("Mes anterior")).toBeInTheDocument();
    expect(screen.queryByText("Todos")).not.toBeInTheDocument();
    expect(screen.getByText(/Activos por pago/)).toBeInTheDocument();
    expect(screen.queryByText("Guardar gestión")).not.toBeInTheDocument();
  });

  it("mantiene llamada/WhatsApp como acción operativa sin editor manual", async () => {
    window.open = vi.fn();
    render(conRouter(<PortalEjecutivo />));
    fireEvent.click(screen.getByText("Mis Clientes"));
    const llamar = await screen.findByText("📞 Llamar");
    fireEvent.click(llamar);
    await waitFor(() => expect(registrarGestionMock).toHaveBeenCalledWith(364, "LLAMADA"));
    expect(window.open).toHaveBeenCalledWith("tel:+56956827600", "_blank");
  });
});
