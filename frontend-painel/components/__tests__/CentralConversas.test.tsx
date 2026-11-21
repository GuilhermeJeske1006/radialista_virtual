import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import CentralConversas from "../CentralConversas";

const api = vi.hoisted(() => vi.fn());
let atualizar = () => {};
vi.mock("../../lib/api", () => ({ apiFetch: api, apiFetchDownload: vi.fn() }));
vi.mock("../../hooks/useEventosOuvintes", () => ({ useEventosOuvintes: (callback: () => void) => { atualizar = callback; return "conectado"; } }));
vi.mock("../WhatsAppConexao", () => ({ default: () => <p>WhatsApp conectado</p> }));
let humano = false;
let enviadas: { id: string; log_id: number; origem: string; texto: string; status: string; em: string }[];
const conversa = (id = 1) => ({ id, nome: id === 1 ? "Carla" : "Bruno", telefone: `55119999000${id}`, humano, nao_lidas: 1, ultima_mensagem: "Olá" });
const msg = (id: number, texto: string) => ({ id: String(id), log_id: id, origem: "ouvinte", texto, status: "guardado", em: `2026-11-12T12:${String(id).padStart(2, "0")}:00Z` });

beforeEach(() => {
  api.mockReset(); humano = false; enviadas = [];
  api.mockImplementation(async (path: string, init?: RequestInit) => {
    if (path.startsWith("/ouvintes/central")) return { conversas: [conversa(), conversa(2)], total_paginas: 1 };
    if (path.endsWith("/contexto")) return { programa_id: 1, publico: { pergunta: "Qual música marcou sua infância?" }, pedidos: [], notas: [], contribuicoes: [] };
    if (path.endsWith("/mensagens") && init?.method === "POST") {
      const { texto } = JSON.parse(init.body as string);
      enviadas.push({ ...msg(22, texto), origem: "radio", status: "pendente" }); return { id: 22, estado: "pendente" };
    }
    if (path.endsWith("/mensagens?antes=20")) return { conversa: conversa(), mensagens: [msg(10, "Mensagem anterior")], antes: null, ultimo_log_id: 10 };
    if (path.endsWith("/mensagens")) return { conversa: conversa(path.includes("/2/") ? 2 : 1), mensagens: [msg(20, "Minha música preferida é Oceano"), ...enviadas], antes: 20, ultimo_log_id: 20 };
    if (init?.method === "PATCH") { humano = JSON.parse(init.body as string).humano; return { humano }; }
    return {};
  });
});

it("exige assumir e envia mensagem com chave idempotente, mostrando o estado de envio", async () => {
  render(<CentralConversas />);
  await userEvent.click(await screen.findByRole("button", { name: /Carla/ }));
  const campo = await screen.findByLabelText("Assuma a conversa para responder pessoalmente");
  expect(campo).toBeDisabled();
  await userEvent.click(screen.getByRole("button", { name: "Assumir conversa" }));
  const resposta = await screen.findByLabelText("Resposta da equipe");
  await userEvent.type(resposta, "Olá, aqui é a equipe!");
  await userEvent.click(screen.getByRole("button", { name: "Enviar mensagem" }));
  expect(await screen.findByText("Olá, aqui é a equipe!")).toBeInTheDocument();
  expect(screen.getByText("Aguardando envio")).toBeInTheDocument();
  const chamada = api.mock.calls.find(([path, init]) => path === "/ouvintes/conversas/1/mensagens" && init?.method === "POST");
  expect(JSON.parse(chamada![1].body).chave).toMatch(/.{8,}/);
});

it("acrescenta mensagens anteriores e mantém as recentes após evento", async () => {
  render(<CentralConversas />);
  await userEvent.click(await screen.findByRole("button", { name: /Carla/ }));
  await userEvent.click(await screen.findByRole("button", { name: "Carregar mensagens anteriores" }));
  expect(await screen.findByText("Mensagem anterior")).toBeInTheDocument();
  expect(screen.getByText("Minha música preferida é Oceano")).toBeInTheDocument();
  act(() => atualizar());
  await waitFor(() => expect(screen.queryByRole("button", { name: "Carregar mensagens anteriores" })).not.toBeInTheDocument());
  expect(screen.getByText("Mensagem anterior")).toBeInTheDocument();
});

it("ignora a resposta atrasada da conversa anterior", async () => {
  let resolver: (valor: unknown) => void = () => {};
  const anterior = api.getMockImplementation()!;
  api.mockImplementation((path: string, init?: RequestInit) => path === "/ouvintes/conversas/1/mensagens" ? new Promise(r => { resolver = r; }) : anterior(path, init));
  render(<CentralConversas />);
  await userEvent.click(await screen.findByRole("button", { name: /Carla/ }));
  await userEvent.click(screen.getByRole("button", { name: /Bruno/ }));
  await screen.findByText("Minha música preferida é Oceano");
  await act(async () => resolver({ conversa: conversa(1), mensagens: [msg(1, "Conteúdo antigo da Carla")], antes: null, ultimo_log_id: 1 }));
  expect(screen.queryByText("Conteúdo antigo da Carla")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Bruno/ })).toHaveAttribute("aria-pressed", "true");
});

it("torna falha de busca visível em vez de mostrar uma conversa vazia sem explicação", async () => {
  api.mockRejectedValue(new Error("Servidor indisponível"));
  render(<CentralConversas />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Servidor indisponível");
  fireEvent.change(screen.getByLabelText("Buscar conversa"), { target: { value: "Carla" } });
});
