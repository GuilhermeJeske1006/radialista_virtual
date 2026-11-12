import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import EditarProgramaForm from "../EditarProgramaForm";
import { Programa, PROGRAMA_VAZIO } from "../../lib/types";

const api = vi.fn();
vi.mock("../../lib/api", () => ({
  apiFetch: (...args: unknown[]) => api(...args),
  ApiError: class ApiError extends Error {},
}));

const fontes = [
  { nome: "Jornal da cidade", dominio: "jornal.example.com", url: "https://jornal.example.com/materia", motivo: "Cobertura local" },
  { nome: "Prefeitura", dominio: "cidade.example.gov.br", url: "https://cidade.example.gov.br/noticias", motivo: "Serviços públicos" },
];
const inicial = { ...PROGRAMA_VAZIO, nome: "Jornal da manhã", descricao: "Notícias locais", fontes_noticias: ["manual.example.com"] };
let descobrir: () => Promise<unknown>;
let programaSalvo: Programa | null;

beforeEach(() => {
  vi.useFakeTimers();
  programaSalvo = null;
  descobrir = async () => ({ status: "ok", fontes });
  api.mockReset();
  api.mockImplementation((path: string, options?: RequestInit) => {
    if (path === "/config/radio") return Promise.resolve({ tipo_radio: "popular", nome_radio: "Rádio da cidade" });
    if (path === "/config/programas/fontes/descobrir") return descobrir();
    if (path === "/config/radialistas/1/programas" && options?.method === "POST") {
      programaSalvo = { ...JSON.parse(options.body as string), id: 5, radio_config_id: 1 };
      return Promise.resolve(programaSalvo);
    }
    if (path === "/config/programas/5") return Promise.resolve(programaSalvo ?? { ...inicial, id: 5, radio_config_id: 1 });
    return Promise.resolve([]);
  });
});

afterEach(() => { vi.useRealTimers(); });

async function abrir(criando = true, valoresIniciais = inicial) {
  await act(async () => {
    render(<EditarProgramaForm programaId={criando ? null : 5} radioConfigId={1} valoresIniciais={valoresIniciais} />);
  });
}

async function avancar() {
  await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
}

const buscas = () => api.mock.calls.filter(([p]) => p === "/config/programas/fontes/descobrir");

describe("descoberta de fontes no cadastro de programa", () => {
  it("busca automaticamente, permite revisar e salva a seleção junto com fontes manuais", async () => {
    await abrir();
    expect(screen.getByRole("button", { name: "Buscando fontes…" })).toBeDisabled();
    await avancar();
    expect(buscas()).toHaveLength(1);
    const briefing = JSON.parse(buscas()[0][1].body);
    expect(briefing.nome).toBe(inicial.nome);
    expect(briefing.descricao).toBe(inicial.descricao);
    expect(screen.getByRole("checkbox", { name: "Jornal da cidade" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Pode pesquisar" })).toBeChecked();
    fireEvent.click(screen.getByRole("checkbox", { name: "Prefeitura" }));
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Criar programa" })); });
    const salvo = api.mock.calls.find(([p, o]) => p === "/config/radialistas/1/programas" && o?.method === "POST");
    expect(JSON.parse(salvo![1].body)).toMatchObject({
      fontes_noticias: ["manual.example.com", fontes[0].url], fontes_pesquisa: [fontes[0].url], pode_pesquisar: true,
    });
    // O POST virou GET de edição: o link continua visível sem depender da busca transitória.
    expect(screen.getAllByRole("link", { name: `${fontes[0].url} ↗` }).length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText(/da rádio Rádio da cidade/)).toBeInTheDocument();
  });

  it("descarta resposta de um perfil anterior e substitui só fontes automáticas", async () => {
    await abrir();
    await avancar();
    let resolver!: (valor: unknown) => void;
    descobrir = () => new Promise((resolve) => { resolver = resolve; });
    fireEvent.change(screen.getByLabelText("Sobre o programa"), { target: { value: "Notícias esportivas" } });
    await avancar();
    fireEvent.change(screen.getByLabelText("Sobre o programa"), { target: { value: "Agenda cultural" } });
    await act(async () => { resolver({ status: "ok", fontes: [{ ...fontes[0], nome: "Resposta antiga", dominio: "antiga.example.com" }] }); });
    expect(screen.queryByText("Resposta antiga")).not.toBeInTheDocument();
    descobrir = async () => ({ status: "ok", fontes: [{ ...fontes[0], nome: "Cultura", dominio: "cultura.example.com", url: "https://cultura.example.com/agenda" }] });
    await avancar();
    expect(screen.getByRole("checkbox", { name: "Cultura" })).toBeChecked();
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Criar programa" })); });
    const salvo = api.mock.calls.find(([p, o]) => p === "/config/radialistas/1/programas" && o?.method === "POST");
    expect(JSON.parse(salvo![1].body).fontes_noticias).toEqual(["manual.example.com", "https://cultura.example.com/agenda"]);
    expect(JSON.parse(salvo![1].body).fontes_pesquisa).toEqual(["https://cultura.example.com/agenda"]);
  });

  it("permite desmarcar uma sugestão que já estava cadastrada manualmente", async () => {
    await abrir(true, { ...inicial, fontes_noticias: ["manual.example.com", fontes[0].dominio] });
    await avancar();
    fireEvent.click(screen.getByRole("checkbox", { name: "Jornal da cidade" }));
    expect(screen.getByRole("checkbox", { name: "Jornal da cidade" })).not.toBeChecked();
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Criar programa" })); });
    const salvo = api.mock.calls.find(([p, o]) => p === "/config/radialistas/1/programas" && o?.method === "POST");
    expect(JSON.parse(salvo![1].body).fontes_noticias).toEqual(["manual.example.com", fontes[1].url]);
    expect(JSON.parse(salvo![1].body).fontes_pesquisa).toEqual([fontes[1].url]);
  });

  it("permite salvar se a busca falhar e oferece nova tentativa", async () => {
    descobrir = async () => ({ status: "indisponivel", fontes: [] });
    await abrir();
    await avancar();
    expect(screen.getByText(/A busca de fontes está indisponível/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Criar programa" })).toBeEnabled();
    descobrir = async () => ({ status: "ok", fontes });
    fireEvent.click(screen.getByRole("button", { name: "Buscar fontes" }));
    await avancar();
    expect(screen.getByRole("checkbox", { name: "Prefeitura" })).toBeChecked();
    expect(JSON.parse(buscas().at(-1)![1].body).atualizar).toBe(true);
  });

  it("pode pausar a busca automática e preenche pesquisa externa em programas sem notícias", async () => {
    await abrir();
    fireEvent.click(screen.getByRole("checkbox", { name: "Buscar fontes automaticamente durante a criação" }));
    await avancar();
    expect(buscas()).toHaveLength(0);
    expect(screen.getByRole("button", { name: "Criar programa" })).toBeEnabled();
    fireEvent.change(screen.getByLabelText("Dosagem de notícia"), { target: { value: "nenhuma" } });
    fireEvent.click(screen.getByRole("checkbox", { name: "Buscar fontes automaticamente durante a criação" }));
    await avancar();
    expect(buscas()).toHaveLength(1);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Criar programa" })); });
    expect(programaSalvo!.fontes_pesquisa).toEqual(fontes.map((f) => f.url));
    expect(programaSalvo!.fontes_noticias).toEqual(["manual.example.com"]);
  });

  it("na edição, busca somente quando solicitada", async () => {
    await abrir(false);
    await avancar();
    expect(buscas()).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "Buscar fontes" }));
    await avancar();
    expect(buscas()).toHaveLength(1);
    fireEvent.change(screen.getByLabelText("Sobre o programa"), { target: { value: "Outra proposta" } });
    await avancar();
    expect(buscas()).toHaveLength(1);
  });

  it("exibe e permite revisar os links que já vieram associados ao programa, sem outra busca", async () => {
    await abrir(true, { ...inicial, fontes_noticias: [fontes[0].url], fontes_pesquisa: [fontes[1].url] });
    await avancar();
    expect(buscas()).toHaveLength(0);
    expect(screen.getAllByRole("link", { name: `${fontes[0].url} ↗` }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: `${fontes[1].url} ↗` }).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: `Fontes de notícias do programa: remover ${fontes[0].url}` }));
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Criar programa" })); });
    expect(programaSalvo!.fontes_noticias).toEqual([]);
    expect(programaSalvo!.fontes_pesquisa).toEqual([fontes[1].url]);
  });
});
