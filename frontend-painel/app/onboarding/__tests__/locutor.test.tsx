import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

const api = vi.hoisted(() => vi.fn());
vi.mock("../../../lib/api", async (importOriginal) => ({ ...(await importOriginal<object>()), apiFetch: api }));
vi.mock("../../../components/AppShell", () => ({ default: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }));
vi.mock("../../../lib/useConfiguracaoInicial", () => ({ invalidarConfiguracaoInicial: vi.fn() }));

import LocutorOnboardingPage from "../locutor/page";

const agil = { id: "agil", nome: "Ágil", descricao: "Voz rápida", limitacoes: "Sem direção vocal", recomendada: false,
  modelo_texto: "claude-sonnet-5", modelo_voz: "eleven_flash_v2_5", preco_hora_brl: 1 };
const premium = { ...agil, id: "premium", nome: "Premium", recomendada: true, modelo_texto: "claude-opus-5",
  modelo_voz: "eleven_v3", preco_hora_brl: 2.5 };
const criado = {
  radialista: { id: 7, nome_locutor: "Duda", voz_id: "v1" },
  programa: { id: 9, nome: "Manhã Duda", dias_semana: [], data_especifica: null, horario_inicio: "06:00:00",
    horario_fim: "09:00:00", generos_musicais: [] },
  combinacao: agil, custo_geracao_brl: 0.0321,
};

beforeEach(() => {
  api.mockReset();
  api.mockImplementation((path: string) => {
    if (path === "/billing/combinacoes") return Promise.resolve({ combinacoes: [premium, agil], mensalidade_brl: 69.9, minutos_fala_por_hora: 6, premissas: "" });
    if (path === "/config/radialistas/gerar-ia") return Promise.resolve(criado);
    if (path === "/config/radio") return Promise.resolve({ tipo_radio: "" });
    return Promise.resolve([]);
  });
});
afterEach(cleanup);

it("gera o locutor com a combinação escolhida e mostra os valores", async () => {
  render(<LocutorOnboardingPage />);
  await userEvent.click(await screen.findByRole("radio", { name: /Ágil/ }));
  // Resumo da escolha antes de gerar, para o cliente validar.
  expect(screen.getByText(/Seu radialista vai usar/)).toHaveTextContent(
    /Ágil: texto Claude Sonnet 5 e voz ElevenLabs Flash 2.5 · ≈ R\$\s1,00 por hora de programa/,
  );
  await userEvent.click(screen.getByRole("button", { name: "Gerar agora com Ágil →" }));
  await waitFor(() => expect(api).toHaveBeenCalledWith("/config/radialistas/gerar-ia", {
    method: "POST", body: JSON.stringify({ descricao: "", combinacao_id: "agil" }),
  }));
  expect(await screen.findByText(/Ágil · Texto Claude Sonnet 5 · Voz ElevenLabs Flash 2.5/)).toBeInTheDocument();
  // 3 h × 30 dias × R$ 1/h
  expect(screen.getByText(/Uso estimado deste programa: ≈ R\$\s90,00\/mês/)).toBeInTheDocument();
  expect(screen.getByText(/0,0321/)).toBeInTheDocument();
});
