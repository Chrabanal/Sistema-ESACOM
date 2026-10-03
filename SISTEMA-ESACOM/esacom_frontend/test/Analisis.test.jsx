import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Analisis from "../src/pages/Analisis";

vi.mock("../src/context/AuthContext", () => ({
  useAuth: () => ({ user: { nombre: "Gerencia", cargo: "GERENCIA" }, logout: vi.fn() }),
}));

vi.mock("../src/api/dashboard", () => ({
  fetchDashboardKpi: vi.fn(() => Promise.resolve([
    { mes_ano: "2026-06", boleta: "B1", pct_cumplimiento: 80, pagadas: 80, pendientes: 10, no_pago: 10 },
  ])),
  fetchHistorico: vi.fn(() => Promise.resolve([
    { camada: "2026-05", pagadas: 70, pendientes: 10, no_pago: 20, fuera_plazo: 0 },
    { camada: "2026-06", pagadas: 80, pendientes: 10, no_pago: 10, fuera_plazo: 0 },
  ])),
  fetchKpiPorEjecutivo: vi.fn(() => Promise.resolve([
    { ejecutivo: { id: 1, nombre: "Ejecutivo Riesgo", equipo: "Quilpué" }, cortes: [{ total: 10, pct_cumplimiento: 50 }] },
  ])),
}));

vi.mock("../src/api/apelaciones", () => ({
  fetchHistorialCargas: vi.fn(() => Promise.resolve([{ id: 7, fecha_corte: "2026-07-31" }])),
  fetchResumenAuditoriaKPI: vi.fn(() => Promise.resolve({
    cruzados: 6225, sin_cruce: 31, filas_con_inconsistencia: 1200,
    diferencia_rut: 0, diferencia_rgu: 114, diferencia_propietario: 1266,
    diferencia_estado: 228, fuera_medicion: 1195, ejecutivo_no_resuelto: 0,
  })),
}));

describe("Análisis gerencial", () => {
  it("muestra auditoría y ejecutivo de riesgo", async () => {
    render(<MemoryRouter><Analisis /></MemoryRouter>);
    expect(await screen.findByText("Ejecutivo Riesgo")).toBeInTheDocument();
    expect(screen.getByText("6.225")).toBeInTheDocument();
    expect(screen.getByText("31")).toBeInTheDocument();
    expect(screen.getByText("Análisis Gerencial")).toBeInTheDocument();
  });
});
