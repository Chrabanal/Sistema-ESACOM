import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Historico from "../src/pages/Historico";

vi.mock("../src/context/AuthContext", () => ({
  useAuth: () => ({ user: { nombre: "Prueba", cargo: "GERENCIA" }, logout: vi.fn() }),
}));

// Forma EXACTA de GET /api/dashboard/historico/ (probado contra el backend real).
const CAMADAS_REALES = [
  { camada: "2025-08", ventas: 1, rgu: 2, clientes: 1, pagadas: 0, pendientes: 1, no_pago: 0, fuera_plazo: 0, sin_boleta: 0, pct_cumplimiento: 0.0 },
  { camada: "2026-07", ventas: 63, rgu: 91, clientes: 63, pagadas: 0, pendientes: 61, no_pago: 0, fuera_plazo: 0, sin_boleta: 0, pct_cumplimiento: 0.0 },
  { camada: "2026-08", ventas: 350, rgu: 535, clientes: 327, pagadas: 0, pendientes: 282, no_pago: 0, fuera_plazo: 0, sin_boleta: 0, pct_cumplimiento: 0.0 },
];

vi.mock("../src/api/dashboard", () => ({
  fetchHistorico: () => Promise.resolve(CAMADAS_REALES),
}));

vi.mock("../src/api/apelaciones", () => ({
  fetchHistorialCargas: () => Promise.resolve([]),
}));

function conRouter(ui) {
  return <MemoryRouter>{ui}</MemoryRouter>;
}

describe("Historico con datos reales", () => {
  it("pinta el gráfico y la tabla comparativa sin explotar", async () => {
    render(conRouter(<Historico />));
    expect(await screen.findByText("Ago 2026")).toBeInTheDocument();
    expect(screen.getByText("Jul 2026")).toBeInTheDocument();
    expect(screen.getByText("Ago 2025")).toBeInTheDocument();

    // Delta entre Jul 2026 (63) y Ago 2026 (350): +287
    expect(screen.getByText("(+287)")).toBeInTheDocument();
  });
});
