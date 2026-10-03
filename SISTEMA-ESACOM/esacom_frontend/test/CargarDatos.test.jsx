import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import CargarDatos from "../src/pages/CargarDatos";

vi.mock("../src/context/AuthContext", () => ({
  useAuth: () => ({ user: { nombre: "Prueba", cargo: "GERENCIA" }, logout: vi.fn() }),
}));

// Forma EXACTA de la respuesta de POST /api/integraciones/cargar-excel/
// (probado contra el backend real, subiendo Ingreso_de_Ventas.xlsx).
const RESUMEN_REAL = {
  dotacion: { creados: 89, actualizados: 0, supervisor_sin_match: 12 },
  comunas: { regiones: 5, comunas_creadas: 147 },
  promociones: { creadas: 16, actualizadas: 0 },
  base_claro: { filas_importadas: 821, con_num_pedido: 821 },
  base_ventas: { ventas_creadas: 398, ventas_actualizadas: 0, sin_ejecutivo_valido: 1, sin_promocion_valida: 0 },
};

const cargarExcelMock = vi.fn(() => Promise.resolve({ carga_id: 2, resumen: RESUMEN_REAL }));

// Forma EXACTA de GET /api/cargas-excel/ (results)
const HISTORIAL_REAL = [
  { id: 2, origen: "MANUAL", tipo_base: "BASE_MATRIZ", archivo_nombre: "Ingreso_de_Ventas.xlsx", filas_totales: 398, creado_en: "2026-08-15T01:50:00-04:00" },
];

vi.mock("../src/api/apelaciones", () => ({
  cargarExcel: (...args) => cargarExcelMock(...args),
  fetchHistorialCargas: () => Promise.resolve(HISTORIAL_REAL),
}));

function conRouter(ui) {
  return <MemoryRouter>{ui}</MemoryRouter>;
}

describe("CargarDatos con datos reales", () => {
  it("pinta el historial sin explotar", async () => {
    render(conRouter(<CargarDatos />));
    expect(await screen.findByText("Ingreso_de_Ventas.xlsx")).toBeInTheDocument();
  });

  it("ofrece cierres Fijo y Móvil como formatos separados", async () => {
    render(conRouter(<CargarDatos />));
    const tipo = screen.getAllByRole("combobox")[0];
    fireEvent.change(tipo, { target: { value: "REPORTE_KPI" } });
    expect(await screen.findByRole("option", { name: /Cierre oficial Fijo/i })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /Cierre oficial Móvil/i })).toBeInTheDocument();
  });

  it("sube un archivo y muestra el resumen real", async () => {
    render(conRouter(<CargarDatos />));

    const archivo = new File(["contenido"], "Ingreso_de_Ventas.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    const input = document.querySelector('input[type="file"]');
    fireEvent.change(input, { target: { files: [archivo] } });

    fireEvent.click(screen.getByRole("button", { name: "Cargar bases" }));

    await waitFor(() => expect(cargarExcelMock).toHaveBeenCalledWith(archivo, "BASE_MATRIZ"));
    expect(await screen.findByText("Importación completada")).toBeInTheDocument();
    expect(screen.getByText(/ventas_creadas/)).toBeInTheDocument();
  });
});
