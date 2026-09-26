import { beforeEach, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ModelosConsumo from "../ModelosConsumo";

const api = vi.hoisted(() => vi.fn());
vi.mock("../../lib/api", () => ({ apiFetch: api }));

const tarifa = { moeda: "USD", cambio: "5.5", acrescimo: "100", descricao: "", limitacoes: "", exemplos: [], unidades: {} };
const catalogo = [
  { ...tarifa, id: "t1", tipo: "llm", modelo: "claude-opus-5" },
  { ...tarifa, id: "t2", tipo: "llm", modelo: "claude-sonnet-5" },
  { ...tarifa, id: "t3", tipo: "tts", modelo: "eleven_v3" },
];
const combo = (id: string, nome: string, texto: string, recomendada = false) =>
  ({ id, nome, descricao: "", limitacoes: "-", recomendada, modelo_texto: texto, modelo_voz: "eleven_v3", preco_hora_brl: 8 });
const combinacoes = { mensalidade_brl: 69.9, minutos_fala_por_hora: 6, premissas: "", padrao: { texto: "claude-opus-5", voz: "eleven_v3" },
  combinacoes: [combo("premium", "Premium", "claude-opus-5", true), combo("equilibrada", "Equilibrada", "claude-sonnet-5")] };
const programa = (id: number, nome: string, radio_config_id = 1) =>
  ({ id, nome, radio_config_id, horario_inicio: "06:00:00", horario_fim: "09:00:00", dias_semana: [], data_especifica: null });

let programas = [programa(9, "Manhã"), programa(10, "Tarde", 2), programa(11, "Noite")];
let escolhas: Record<string, object> = {};

beforeEach(() => {
  programas = [programa(9, "Manhã"), programa(10, "Tarde", 2), programa(11, "Noite")];
  escolhas = {
    whatsapp: { texto: "claude-sonnet-5" },
    "11": { texto: "claude-sonnet-5", voz: "eleven_v3", combinacao: "equilibrada", programa_id: 11 },
    "radialista:2": { texto: "claude-sonnet-5", voz: "eleven_v3", combinacao: "equilibrada" },
  };
  api.mockReset();
  api.mockImplementation((path: string, init?: { method?: string; body?: string }) => {
    if (path === "/billing/catalogo-modelos") return Promise.resolve(catalogo);
    if (path === "/config/programas") return Promise.resolve(programas);
    if (path === "/billing/modelos" && !init?.method) return Promise.resolve(escolhas);
    if (path === "/billing/combinacoes") return Promise.resolve(combinacoes);
    if (path === "/billing/combinacao" && init?.method === "PUT") {
      const { combinacao_id, programa_id } = JSON.parse(init.body!);
      escolhas = { ...escolhas, [programa_id]: { texto: "claude-sonnet-5", voz: "eleven_v3", combinacao: combinacao_id, programa_id } };
      return Promise.resolve(escolhas);
    }
    if (path === "/billing/modelos" && init?.method === "PUT") {
      escolhas = { ...escolhas, whatsapp: { texto: JSON.parse(init.body!).texto } };
      return Promise.resolve(escolhas);
    }
    return Promise.reject(new Error("inesperado " + path));
  });
});

const linha = async (nome: string) => (await screen.findByText(nome, { selector: "p" })).closest("li")!;

it("mostra o modelo em uso de cada configuração e de onde ele vem", async () => {
  render(<ModelosConsumo />);
  const whatsapp = await linha("Atendimento WhatsApp");
  expect(within(whatsapp).getByText("Claude Sonnet 5")).toBeInTheDocument();
  // Sem escolha própria nem do locutor: padrão do sistema, reconhecido como Premium.
  const manha = await linha("Manhã");
  expect(within(manha).getByText("Premium")).toBeInTheDocument();
  expect(within(manha).getByText("Padrão do Locufy")).toBeInTheDocument();
  expect(within(await linha("Tarde")).getByText("Herdada do locutor")).toBeInTheDocument();
  expect(within(await linha("Noite")).getByText("Escolha sua")).toBeInTheDocument();
});

it("troca a combinação de um programa pelo modal", async () => {
  render(<ModelosConsumo />);
  await userEvent.click(await screen.findByRole("button", { name: "Trocar modelo de Manhã" }));
  const modal = screen.getByRole("heading", { name: "Trocar modelo · Manhã" }).parentElement!.parentElement!;
  await userEvent.click(within(modal).getByRole("radio", { name: /Equilibrada/ }));
  await userEvent.click(within(modal).getByRole("button", { name: "Usar Equilibrada neste programa" }));
  await waitFor(() => expect(api).toHaveBeenCalledWith("/billing/combinacao", {
    method: "PUT", body: JSON.stringify({ combinacao_id: "equilibrada", programa_id: 9 }) }));
  expect(await screen.findByRole("status")).toHaveTextContent("Manhã agora usa Equilibrada");
  expect(screen.queryByRole("heading", { name: "Trocar modelo · Manhã" })).not.toBeInTheDocument();
  expect(within(await linha("Manhã")).getByText("Escolha sua")).toBeInTheDocument();
});

it("aplica a mesma combinação a todos os programas", async () => {
  render(<ModelosConsumo />);
  await userEvent.click(await screen.findByRole("button", { name: "Trocar modelo de Tarde" }));
  await userEvent.click(screen.getByRole("radio", { name: /Premium/ }));
  await userEvent.click(screen.getByRole("button", { name: "Usar em todos os programas (3)" }));
  await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Todos os 3 programas agora usam Premium"));
  const puts = api.mock.calls.filter(([path]) => path === "/billing/combinacao").map(([, init]) => JSON.parse(init.body).programa_id);
  expect(puts).toEqual([9, 10, 11]);
});

it("avisa quantos programas trocaram quando um falha no meio", async () => {
  const padrao = api.getMockImplementation()!;
  api.mockImplementation((path: string, init?: { method?: string; body?: string }) =>
    path === "/billing/combinacao" && JSON.parse(init!.body!).programa_id === 10
      ? Promise.reject(new Error("Combinação de modelos indisponível.")) : padrao(path, init));
  render(<ModelosConsumo />);
  await userEvent.click(await screen.findByRole("button", { name: "Trocar modelo de Manhã" }));
  await userEvent.click(screen.getByRole("button", { name: "Usar em todos os programas (3)" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Trocado em 1 de 3 programas. Combinação de modelos indisponível.");
});

it("troca o modelo de texto do atendimento WhatsApp", async () => {
  render(<ModelosConsumo />);
  await userEvent.click(await screen.findByRole("button", { name: "Trocar modelo de Atendimento WhatsApp" }));
  expect(screen.getByRole("button", { name: "Salvar modelo" })).toBeDisabled();
  await userEvent.click(screen.getByRole("radio", { name: /Claude Opus 5/ }));
  await userEvent.click(screen.getByRole("button", { name: "Salvar modelo" }));
  await waitFor(() => expect(api).toHaveBeenCalledWith("/billing/modelos", {
    method: "PUT", body: JSON.stringify({ texto: "claude-opus-5", voz: null, programa_id: null }) }));
  expect(within(await linha("Atendimento WhatsApp")).getByText("Claude Opus 5")).toBeInTheDocument();
});

it("pagina a lista quando há muitos programas", async () => {
  programas = Array.from({ length: 8 }, (_, i) => programa(i + 1, `Programa ${i + 1}`));
  render(<ModelosConsumo />);
  expect(await screen.findByText("Programa 5")).toBeInTheDocument();
  expect(screen.queryByText("Programa 6")).not.toBeInTheDocument();
  const nav = screen.getByRole("navigation", { name: "Páginas dos modelos em uso" });
  expect(nav).toHaveTextContent("Página 1 de 2");
  await userEvent.click(within(nav).getByRole("button", { name: "Próxima ›" }));
  expect(screen.getByText("Programa 8")).toBeInTheDocument();
  expect(screen.queryByText("Atendimento WhatsApp")).not.toBeInTheDocument();
});
