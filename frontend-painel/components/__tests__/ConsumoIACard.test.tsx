import { beforeEach, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ConsumoIACard from "../ConsumoIACard";
const api = vi.hoisted(() => vi.fn());
vi.mock("../../lib/api", () => ({ apiFetch: api }));
const consumo = { consumo_brl: 10, reservado_brl: 2, comprometido_brl: 12, orcamento_brl: 100, previsao_brl: 79.9, regra_cambio: "Câmbio congelado por vigência." };
function respostas() { api.mockImplementation((path: string) => Promise.resolve(path === "/billing/consumo-ia" ? consumo : [])); }
beforeEach(() => { api.mockReset(); respostas(); });
it("mostra consumo, previsão e exposição em reais", async () => {
  render(<ConsumoIACard plano="flex" />);
  expect(await screen.findByText(/79,90/)).toBeInTheDocument();
  expect(screen.getByText(/Total comprometido/)).toHaveTextContent("12,00");
  expect(screen.queryByText(/pacotes/i)).not.toBeInTheDocument();
});
it("erro de consulta não vira consumo zero e permite tentar novamente", async () => {
  api.mockRejectedValue(new Error("rede"));
  render(<ConsumoIACard />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível consultar");
  expect(screen.queryByText(/79,90/)).not.toBeInTheDocument();
  respostas(); await userEvent.click(screen.getByRole("button", {name:"Atualizar"}));
  expect(await screen.findByText(/79,90/)).toBeInTheDocument();
});
it("salva o limite escolhido explicitamente", async () => {
  render(<ConsumoIACard />);
  const input = await screen.findByRole("spinbutton", {name:/Limite financeiro/});
  await userEvent.clear(input); await userEvent.type(input,"250");
  await userEvent.click(screen.getByRole("button", {name:"Salvar limite"}));
  await waitFor(() => expect(api).toHaveBeenCalledWith("/billing/limite-financeiro", {method:"PUT",body:JSON.stringify({limite_brl:"250"})}));
});
const uso = (i: number) => ({ id: `u${i}`, funcionalidade: "locucao", modelo: "claude-opus-5", unidades: { entrada: "1" }, preco_brl: 0.01, estado: "concluido",
  iniciado_em: "2026-09-25T12:00:00Z", tarifa: { versao: "v1", cambio: "5.5", acrescimo: "100" } });
it("pagina o extrato no servidor pedindo um item a mais", async () => {
  const usos = Array.from({ length: 13 }, (_, i) => uso(i));
  api.mockImplementation((path: string) => {
    if (path === "/billing/consumo-ia") return Promise.resolve(consumo);
    if (path.startsWith("/billing/extrato")) {
      const q = new URLSearchParams(path.split("?")[1]);
      return Promise.resolve(usos.slice(Number(q.get("offset")), Number(q.get("offset")) + Number(q.get("limite"))));
    }
    return Promise.resolve([]);
  });
  render(<ConsumoIACard />);
  const nav = await screen.findByRole("navigation", { name: "Páginas dos últimos usos" });
  expect(api).toHaveBeenCalledWith("/billing/extrato?offset=0&limite=11", expect.anything());
  expect(screen.getAllByText("Locução")).toHaveLength(20); // 10 usos: cartão (celular) + linha (tabela)
  await userEvent.click(within(nav).getByRole("button", { name: "Próxima ›" }));
  await waitFor(() => expect(screen.getAllByText("Locução")).toHaveLength(6));
  expect(api).toHaveBeenCalledWith("/billing/extrato?offset=10&limite=11", expect.anything());
  expect(within(nav).getByRole("button", { name: "Próxima ›" })).toBeDisabled();
  expect(nav).toHaveTextContent("Página 2");
});
it("pagina o histórico de faturas", async () => {
  const faturas = Array.from({ length: 8 }, (_, i) => ({ id: `f${i}`, inicio: `2026-0${i + 1}-02T12:00:00Z`, fim: `2026-0${i + 1}-28T12:00:00Z`, estado: "paga", total_brl: 70 + i, url: null }));
  api.mockImplementation((path: string) => Promise.resolve(path === "/billing/consumo-ia" ? consumo : path === "/billing/faturas" ? faturas : []));
  render(<ConsumoIACard />);
  const nav = await screen.findByRole("navigation", { name: "Páginas do histórico de faturas" });
  expect(nav).toHaveTextContent("Página 1 de 2");
  expect(screen.queryAllByText(/77,00/)).toHaveLength(0);
  await userEvent.click(within(nav).getByRole("button", { name: "Próxima ›" }));
  expect(screen.getAllByText(/77,00/).length).toBeGreaterThan(0);
  expect(screen.queryAllByText(/70,00/)).toHaveLength(0);
});
