import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

const apiFetch = vi.fn();
vi.mock("../../lib/api", async () => {
  const real = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return { ...real, apiFetch: (...args: unknown[]) => apiFetch(...args) };
});

import RelatorioProgramaPanel, { type RelatorioPrograma } from "../RelatorioProgramaPanel";

beforeEach(() => apiFetch.mockReset());
afterEach(() => cleanup());

const RELATORIO: RelatorioPrograma = {
  data: "2026-11-10",
  as_run: { enviados: 6, confirmados: 4, falharam: 1, sem_relato: 1 },
  nao_medido: ["orcamento", "hard_time"],
  secoes: {
    promessas: { cumpridas: 1, vencidas: 1, canceladas_com_contingencia: 1, abertas_no_fim: 0 },
    pedidos: { recebidos: 3, executados: 1, nao_atendidos: 1, expirados: 0, pendentes_fim: 1 },
    oralidade: { avisos: 2 },
    repeticao: { estrutura: 1 },
  },
  alertas: ["promessa vencida: 1"],
  sugestoes: ["Variar as aberturas: 1 janelas com a mesma construção."],
};

describe("RelatorioProgramaPanel (F11)", () => {
  it("mostra o dia de hoje do backend, o as-run, as seções, alertas e sugestões", async () => {
    apiFetch.mockResolvedValueOnce(RELATORIO);
    render(<RelatorioProgramaPanel programaId={3} />);
    expect(await screen.findByText(/4 de 6 blocos confirmados/)).toBeTruthy();
    expect(apiFetch).toHaveBeenCalledWith("/config/programas/3/relatorio");
    expect(screen.getByText(/1 cumpridas, 1 vencidas/)).toBeTruthy();
    expect(screen.getByRole("list", { name: "Alertas" })).toHaveTextContent("promessa vencida: 1");
    expect(screen.getByRole("list", { name: "Sugestões para a próxima edição" })).toHaveTextContent("Variar");
    expect(screen.getByText(/Não medido no ar/)).toBeTruthy();
  });

  it("trocar o dia busca o relatório daquele dia", async () => {
    apiFetch.mockResolvedValueOnce(RELATORIO).mockResolvedValueOnce({
      ...RELATORIO, data: "2026-11-09", as_run: { enviados: 0, confirmados: 0, falharam: 0, sem_relato: 0 },
    });
    render(<RelatorioProgramaPanel programaId={3} />);
    await screen.findByText(/4 de 6 blocos confirmados/);
    fireEvent.change(screen.getByLabelText("Dia"), { target: { value: "2026-11-09" } });
    await waitFor(() => expect(apiFetch).toHaveBeenLastCalledWith("/config/programas/3/relatorio?data=2026-11-09"));
    expect(await screen.findByText("Nada foi ao ar neste dia.")).toBeTruthy();
  });
});
