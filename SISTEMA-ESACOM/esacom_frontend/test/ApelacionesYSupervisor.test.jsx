import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Apelaciones from "../src/pages/Apelaciones";
import PortalSupervisor from "../src/pages/PortalSupervisor";

vi.mock("../src/context/AuthContext", () => ({
  useAuth: () => ({ user: { nombre: "Prueba", cargo: "GERENCIA" }, logout: vi.fn() }),
}));

// Recorte EXACTO de lo que devolvió GET /api/apelaciones/ contra el backend real.
const APELACION_REAL = {
  id: 3,
  corte: {
    id: 319,
    venta: {
      id: 396,
      n_pedido: "1-285616934130",
      rut_cliente: "13654964-2",
      ejecutivo: { id: 2, rut: "19776727-8", nombre: "CAMILO IGNACIO BASCUÑAN PEÑALOZA", cargo: "EJECUTIVO", equipo: "Quilpué" },
      estado_instalacion: "PENDIENTE_INSTALACION",
    },
    boleta: "B2",
    mes_ano: "2026-08",
    meta_pct: "83.00",
    estado_pago: "SIN_BOLETA",
    fecha_vencimiento: null,
    fecha_pago: null,
    dias_diferencia: null,
  },
  motivo: "APROVISIONAMIENTO",
  estado: "DETECTADA",
  observacion: "Cliente sin 2ª Boleta generada (S/B), con las boletas previas pagadas en plazo.",
  bill_no: "",
  fecha_deteccion: "2026-08-14T20:00:00-04:00",
  fecha_envio: null,
  fecha_respuesta: null,
  excluida_por: null,
};

// EXACTO de lo que devolvió GET /api/equipo/resumen/ (Gerencia)
const RESUMEN_EQUIPO_REAL = {
  clientes: 373, rgu: 606, ejecutivos: 37,
  pendiente_instalacion: 95, pendiente_comercial: 50, anulados: 71,
};

const VENTA_REAL = {
  id: 1, rut_cliente: "18704767-6", n_pedido: "1-284603936816",
  ejecutivo: { id: 5, rut: "13011613-2", nombre: "RAUL SANTIS", equipo: "Quilpué" },
  promocion: { id: 1, nombre: "VTR 1P INTERNET", rgu: 1 },
  comuna: { id: 1, nombre: "Limache", region: "V Valparaíso" },
  estado_instalacion: "PENDIENTE_INSTALACION",
  fecha_venta: "2026-07-21", primera_agenda: "2026-07-25", fecha_cierre: null,
};


vi.mock("../src/api/dashboard", () => ({
  fetchDashboardKpiCompleto: vi.fn(() => Promise.resolve({
    cortes: [
      { mes_ano: "2026-07", boleta: "B1", pct_cumplimiento: 47.2, meta_pct: 85, cumplimiento_meta_pct: 55.5, faltan_para_meta: 14, pagadas: 17, pendientes: 17, no_pago: 2, fuera_plazo: 0, sin_boleta: 1, total: 36, gestion: {} },
    ],
    ultima_carga: { archivo_nombre: "KPI10082026 ESACOM.xlsx", fecha_corte: "2026-08-10", dia_reporte: "LUNES", foco_b1: "2026-07", foco_b2: "2026-06", foco_b3: "2026-05" },
  })),
  fetchKpiPorEjecutivoCompleto: vi.fn(() => Promise.resolve({
    ejecutivos: [{
      ejecutivo: { id: 5, rut: "13011613-2", nombre: "RAUL SANTIS", equipo: "Quilpué" },
      promedio_focos: 47.2,
      cortes: [{ mes_ano: "2026-07", boleta: "B1", pct_cumplimiento: 47.2, meta_pct: 85, cumplimiento_meta_pct: 55.5, faltan_para_meta: 14, pendientes: 17 }],
    }],
    snapshot: { fecha_corte: "2026-08-10" },
  })),
}));
vi.mock("../src/api/apelaciones", () => ({
  fetchApelaciones: vi.fn(() => Promise.resolve([APELACION_REAL])),
  detectarApelaciones: vi.fn(() => Promise.resolve({ apelaciones_nuevas: 0, cortes_revisados: 319 })),
  excluirApelacion: vi.fn(() => Promise.resolve({})),
  enviarApelacion: vi.fn(() => Promise.resolve({})),
  fetchResumenEquipo: vi.fn(() => Promise.resolve(RESUMEN_EQUIPO_REAL)),
  fetchVentas: vi.fn(() => Promise.resolve([VENTA_REAL])),
}));

function conRouter(ui) {
  return <MemoryRouter>{ui}</MemoryRouter>;
}

describe("Apelaciones con datos reales", () => {
  it("pinta la tabla y permite excluir/enviar sin explotar", async () => {
    render(conRouter(<Apelaciones />));
    expect(await screen.findByText("1-285616934130")).toBeInTheDocument();
    expect(screen.getByText("13654964-2")).toBeInTheDocument();
    expect(screen.getByText("Aprovisionamiento")).toBeInTheDocument();

    const botonExcluir = screen.getByText("Excluir");
    fireEvent.click(botonExcluir);
    await waitFor(() => expect(screen.getByText("1-285616934130")).toBeInTheDocument());
  });
});

describe("PortalSupervisor con datos reales", () => {
  it("pinta el resumen y la lista de clientes sin explotar", async () => {
    render(conRouter(<PortalSupervisor />));
    expect(await screen.findByText("373")).toBeInTheDocument(); // clientes
    expect(screen.getByText("606")).toBeInTheDocument(); // rgu
    expect(screen.getByText("18704767-6")).toBeInTheDocument();
    expect(screen.getByText("VTR 1P INTERNET")).toBeInTheDocument();
  });
});
