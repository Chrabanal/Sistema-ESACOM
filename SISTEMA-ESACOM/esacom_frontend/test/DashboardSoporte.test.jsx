import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import DashboardSoporte from "../src/pages/DashboardSoporte";

vi.mock("../src/context/AuthContext", () => ({
  useAuth: () => ({ user: { id: 1, nombre: "Soporte", cargo: "SOPORTE" }, logout: vi.fn() }),
}));

vi.mock("../src/api/soporte", () => ({
  fetchUsuarios: vi.fn(async (params) => params?.cargo === "SUPERVISOR" ? [] : [{ id: 2, rut: "19784357-8", nombre: "Ejecutivo Demo", correo: "", cargo: "EJECUTIVO", supervisor: null, equipo: "", is_active: true, ultimo_acceso: null }]),
  fetchResumenUsuarios: vi.fn(async () => ({ total: 2, activos: 2, inactivos: 0, ejecutivos: 1, supervisores: 0, gerencia: 0, soporte: 1 })),
  fetchAuditoria: vi.fn(async () => []),
  crearUsuario: vi.fn(), editarUsuario: vi.fn(), activarUsuario: vi.fn(), desactivarUsuario: vi.fn(), resetPassword: vi.fn(),
  fetchDotacion: vi.fn(async () => ({ resumen: {}, filas: [] })), sincronizarGoogleSheets: vi.fn(),
  fetchMetasKpiCalidad: vi.fn(async () => [{ id: 1, vigente_desde: "2026-07", meta_b1: "85.00", meta_b2: "83.00", meta_b3: "80.00", motivo: "Confirmado Gerencia", creado_por_nombre: "Soporte" }]),
  crearMetaKpiCalidad: vi.fn(),
}));

describe("DashboardSoporte", () => {
  it("muestra resumen y usuarios", async () => {
    render(<MemoryRouter><DashboardSoporte /></MemoryRouter>);
    expect(screen.getByText("Dashboard Soporte")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Ejecutivo Demo")).toBeInTheDocument());
    expect(screen.getByText("+ Crear usuario")).toBeInTheDocument();
  });
});
