import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ReactNode } from "react";
import RadialistasPage from "../page";
import { PROGRAMA_VAZIO, RADIALISTA_VAZIO } from "../../../lib/types";

const api = vi.fn();
vi.mock("../../../lib/api", () => ({
  apiFetch: (...args: unknown[]) => api(...args), ApiError: class ApiError extends Error {},
}));
vi.mock("../../../components/AppShell", () => ({ default: ({ children }: { children: ReactNode }) => <>{children}</> }));
vi.mock("../../../components/AssinaturaGate", () => ({
  AvisoPagamento: () => null,
  useExigirAssinatura: () => ({ exigir: (acao: () => void) => acao(), modal: null }),
}));
vi.mock("../../../components/VoiceSelect", () => ({ default: () => null }));
vi.mock("../../../components/CombinacaoSelect", () => ({ default: () => null }));

afterEach(() => { vi.useRealTimers(); });

it("descobre fontes durante a revisão da criação com IA e envia a seleção na confirmação", async () => {
  vi.useFakeTimers();
  api.mockImplementation((path: string) => {
    if (path === "/config/radio") return Promise.resolve({ tipo_radio: "popular" });
    if (path === "/config/radialistas/gerar-ia/preview") return Promise.resolve({
      radialista: RADIALISTA_VAZIO,
      programa: { ...PROGRAMA_VAZIO, nome: "Cultura local", generos_musicais: ["MPB"], assuntos_ao_vivo: ["agenda cultural"] },
      geracao_id: 7, campos_corrigidos: [], avisos: [],
    });
    if (path === "/config/programas/fontes/descobrir") return Promise.resolve({ status: "ok", fontes: [
      { nome: "Agenda da cidade", dominio: "cultura.example.com", url: "https://cultura.example.com/agenda", motivo: "Agenda cultural local" },
    ] });
    // Interrompe a confirmação antes da navegação; verifica abaixo o payload enviado.
    if (path === "/config/radialistas/gerar-ia/commit") return Promise.reject(new Error("Confirmação interceptada pelo teste"));
    return Promise.resolve([]);
  });
  await act(async () => { render(<RadialistasPage />); });
  fireEvent.click(screen.getByRole("button", { name: "✨ Gerar com IA" }));
  await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Gerar" })); });
  expect(screen.getByRole("button", { name: "Buscando fontes…" })).toBeDisabled();
  await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
  expect(screen.getByRole("checkbox", { name: "Agenda da cidade" })).toBeChecked();
  const busca = api.mock.calls.find(([p]) => p === "/config/programas/fontes/descobrir");
  expect(JSON.parse(busca![1].body)).toMatchObject({ generos_musicais: ["MPB"], assuntos_ao_vivo: ["agenda cultural"] });
  await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Criar radialista e programa" })); });
  const commit = api.mock.calls.find(([p]) => p === "/config/radialistas/gerar-ia/commit");
  expect(JSON.parse(commit![1].body).programa).toMatchObject({
    fontes_noticias: ["https://cultura.example.com/agenda"],
    fontes_pesquisa: ["https://cultura.example.com/agenda"], pode_pesquisar: true,
  });
});
