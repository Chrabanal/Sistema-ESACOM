import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import KpiCard from "../src/components/KpiCard";

const CORTE_REAL = {
  pagadas: 151, pendientes: 37, no_pago: 40, fuera_plazo: 26, sin_boleta: 0,
  total: 254, meta_pct: 85.0, pct_cumplimiento: 59.45, pct_proyectado: 68.1,
  faltan_para_meta: 65, semaforo: "rojo",
  mes_ano: "2026-08", boleta: "B1", tiene_datos: true, gestion: {},
  estado_medicion: "AVANCE", valor_informado_claro: 61.2, tendencia_pp: 2.35,
  dia_reporte: "MIERCOLES", fecha_corte: "2026-09-01",
};

const CORTE_SIN_DATOS = {
  pagadas: 0, pendientes: 0, no_pago: 0, fuera_plazo: 0, sin_boleta: 0,
  total: 0, meta_pct: 85.0, pct_cumplimiento: 0, pct_proyectado: 0,
  faltan_para_meta: 0, semaforo: "sin_datos",
  mes_ano: "2026-09", boleta: "B1", tiene_datos: false, gestion: {},
};

describe("KpiCard amigable para Ejecutivo", () => {
  it("muestra si cumple, meta, RGU faltantes y tendencia", () => {
    render(<KpiCard corte={CORTE_REAL} />);
    expect(screen.getByText("59.45%")).toBeInTheDocument();
    expect(screen.getByText(/Meta ESACOM 85.0%/)).toBeInTheDocument();
    expect(screen.getByText("Aún no cumples")).toBeInTheDocument();
    expect(screen.getByText("65 RGU")).toBeInTheDocument();
    expect(screen.getByText(/↑ 2.35 pp/)).toBeInTheDocument();
    expect(screen.getByText("Último reporte Claro")).toBeInTheDocument();
    expect(screen.getByText(/Referencia Claro \(avance\):/)).toBeInTheDocument();
    expect(screen.getByText(/Proyección según tasa actual/)).toBeInTheDocument();
  });

  it("mantiene la boleta visible sin inventar un KPI cuando no hay datos", () => {
    render(<KpiCard corte={CORTE_SIN_DATOS} />);
    expect(screen.getByText("Sin datos")).toBeInTheDocument();
    expect(screen.getByText(/Sin medición para tu cartera/)).toBeInTheDocument();
    expect(screen.queryByText("0.00%")).not.toBeInTheDocument();
  });
});
