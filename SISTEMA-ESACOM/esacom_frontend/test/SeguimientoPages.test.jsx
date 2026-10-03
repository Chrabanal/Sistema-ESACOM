import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import SeguimientoEjecutivos from "../src/pages/SeguimientoEjecutivos";
import SeguimientoBoletas from "../src/pages/SeguimientoBoletas";

// Mock del AuthContext -- estas pantallas solo necesitan un usuario logueado.
vi.mock("../src/context/AuthContext", () => ({
  useAuth: () => ({ user: { nombre: "Prueba", cargo: "GERENCIA" }, logout: vi.fn() }),
}));

// Datos EXACTOS devueltos por GET /api/dashboard/kpi-ejecutivos/ (recorte real)
const EJECUTIVOS_REALES = [
  {
    ejecutivo: { id: 83, rut: "20502216-3", nombre: "BENJAMIN ALONSO MORALES ZAMORA", equipo: "Quilpué" },
    cortes: [
      {
        pagadas: 1, pendientes: 0, no_pago: 0, fuera_plazo: 0, sin_boleta: 0, total: 1,
        meta_pct: 85.0, pct_cumplimiento: 100.0, pct_proyectado: 100.0, faltan_para_meta: 0,
        semaforo: "verde", mes_ano: "2026-08", boleta: "B1",
      },
    ],
  },
];

// Datos EXACTOS devueltos por GET /api/dashboard/accionables/
const ACCIONABLES_REALES = {
  hoy: { rgu: 17, clientes: 12, camadas: [{ nombre: "2026-08 · 1ª Boleta", rgu: 17, clientes: 12 }] },
  manana: { rgu: 15, clientes: 10, camadas: [{ nombre: "2026-08 · 1ª Boleta", rgu: 15, clientes: 10 }] },
  prox_3d: { rgu: 25, clientes: 16, camadas: [{ nombre: "2026-08 · 1ª Boleta", rgu: 25, clientes: 16 }] },
};

vi.mock("../src/api/dashboard", () => ({
  fetchKpiPorEjecutivo: () => Promise.resolve(EJECUTIVOS_REALES),
  fetchAccionables: () => Promise.resolve(ACCIONABLES_REALES),
}));

function conRouter(ui) {
  return <MemoryRouter>{ui}</MemoryRouter>;
}

describe("SeguimientoEjecutivos con datos reales", () => {
  it("pinta la matriz sin explotar", async () => {
    render(conRouter(<SeguimientoEjecutivos />));
    expect(await screen.findByText("BENJAMIN ALONSO MORALES ZAMORA")).toBeInTheDocument();
    expect(screen.getByText("100.0%")).toBeInTheDocument();
    expect(screen.getByText("1/1")).toBeInTheDocument();
  });
});

describe("SeguimientoBoletas (Accionables) con datos reales", () => {
  it("pinta los 3 buckets sin explotar", async () => {
    render(conRouter(<SeguimientoBoletas />));
    expect(await screen.findByText("17")).toBeInTheDocument(); // RGU de hoy
    expect(screen.getByText("15")).toBeInTheDocument(); // RGU de mañana
    expect(screen.getByText("25")).toBeInTheDocument(); // RGU próx. 3d
    expect(screen.getAllByText("2026-08 · 1ª Boleta")).toHaveLength(3);
  });
});
