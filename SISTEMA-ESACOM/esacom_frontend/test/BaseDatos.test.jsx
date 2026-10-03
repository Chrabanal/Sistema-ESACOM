import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import BaseDatos from "../src/pages/BaseDatos";

vi.mock("../src/context/AuthContext", () => ({
  useAuth: () => ({ user: { nombre: "Prueba", cargo: "GERENCIA" }, logout: vi.fn() }),
}));

// Forma EXACTA de GET /api/ventas/?page=1 (probado contra el backend real).
const PAGINA_REAL = {
  count: 398,
  next: "http://localhost:8000/api/ventas/?page=2",
  previous: null,
  results: [
    {
      id: 1, rut_cliente: "18704767-6", nombre_cliente: "NATALIE ROSSANA FILIPPI IRARRAZABAL",
      n_pedido: "1-284603936816", telefono_cliente: "999997549",
      ejecutivo: { id: 5, rut: "13011613-2", nombre: "RAUL SANTIS", equipo: "Quilpué" },
      promocion: { id: 1, nombre: "VTR 1P INTERNET", rgu: 1 },
      comuna: { id: 1, nombre: "Limache", region: "V Valparaíso" },
      estado_instalacion: "PENDIENTE_INSTALACION",
      camada: "2026-07", fecha_venta: "2026-07-21", precio_venta: "15990",
    },
  ],
};

const fetchVentasPaginadoMock = vi.fn(() => Promise.resolve(PAGINA_REAL));

vi.mock("../src/api/apelaciones", () => ({
  fetchVentasPaginado: (...args) => fetchVentasPaginadoMock(...args),
  fetchTodasVentas: vi.fn(() => Promise.resolve(PAGINA_REAL.results)),
}));

function conRouter(ui) {
  return <MemoryRouter>{ui}</MemoryRouter>;
}

describe("BaseDatos con datos reales", () => {
  it("pinta la tabla, el total y respeta la paginación", async () => {
    render(conRouter(<BaseDatos />));
    expect(await screen.findByText("NATALIE ROSSANA FILIPPI IRARRAZABAL")).toBeInTheDocument();
    expect(screen.getByText("398 registros encontrados")).toBeInTheDocument();
    expect(screen.getByText("VTR 1P INTERNET")).toBeInTheDocument();

    // Botón "Anterior" debe estar deshabilitado en la primera página (previous: null)
    const anterior = screen.getByText("← Anterior");
    expect(anterior).toBeDisabled();
  });

  it("busca y vuelve a pedir la página 1 con el término correcto", async () => {
    render(conRouter(<BaseDatos />));
    await screen.findByText("NATALIE ROSSANA FILIPPI IRARRAZABAL");

    const input = screen.getByPlaceholderText(/Buscar por cliente/);
    fireEvent.change(input, { target: { value: "FILIPPI" } });
    fireEvent.click(screen.getByText("Buscar"));

    await waitFor(() =>
      expect(fetchVentasPaginadoMock).toHaveBeenCalledWith(
        expect.objectContaining({ page: 1, search: "FILIPPI" })
      )
    );
  });
});
