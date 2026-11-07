import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import EditarProgramaForm from "../EditarProgramaForm";
import { BibliotecaAudioItem } from "../../lib/bibliotecaAudio";

const apiFetchMock = vi.fn();

vi.mock("../../lib/api", () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
  ApiError: class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  },
}));

const vinhetaFixture: BibliotecaAudioItem = {
  id: 9,
  nome: "Vinheta QA",
  categoria_id: null,
  audio_nome_original: "x.mp3",
  duracao_segundos: 12,
  cor: null,
  ordem: 0,
  ativo: true,
};

async function renderCriacao() {
  apiFetchMock.mockImplementation((path: string) => {
    if (path === "/config/radio") return Promise.reject(new Error("sem radio configurado"));
    if (path === "/config/tipos-radio") return Promise.resolve([]);
    if (path === "/patrocinadores") return Promise.resolve([]);
    if (path === "/biblioteca-audio") return Promise.resolve([vinhetaFixture]);
    if (path === "/categorias-vinheta") return Promise.resolve([]);
    if (path === "/config/fontes-noticia") return Promise.resolve([]);
    return Promise.resolve({});
  });
  render(<EditarProgramaForm programaId={null} radioConfigId={1} />);
  await screen.findByText("Novo programa");
}

describe("EditarProgramaForm (criação)", () => {
  it("mostra a paleta completa (com vinhetas) desde a criação, sem o aviso de tela dedicada", async () => {
    await renderCriacao();

    expect(await screen.findByText("Vinheta QA")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "+ Abertura" })).toBeInTheDocument();
    expect(screen.queryByText(/reordenar essa sequência arrastando os blocos numa tela dedicada/)).not.toBeInTheDocument();
  });

  it("adicionar um bloco pela paleta atualiza a sequência na prévia", async () => {
    await renderCriacao();

    expect(screen.getByText(/Sequência vazia/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "+ Abertura" }));

    expect(await screen.findByText("Abertura")).toBeInTheDocument();
    expect(screen.queryByText(/Sequência vazia/)).not.toBeInTheDocument();
  });
});

it("permite selecionar o formato musical e aplicar seu roteiro sem comentários extras", async () => {
  await renderCriacao();
  await userEvent.selectOptions(screen.getByLabelText("Formato do programa"), "musical_companhia");
  expect(screen.getByText(/Pedidos reais continuam recebendo anúncio/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Usar sequência musical sugerida" }));
  expect(screen.queryByText(/Sequência vazia/)).not.toBeInTheDocument();
  const extras = screen.getByRole("checkbox", { name: /O formato musical segue a sequência/ });
  expect(extras).toBeDisabled();
  expect(extras).not.toBeChecked();
  expect(screen.getByLabelText("Formato do programa")).toHaveValue("musical_companhia");
  await userEvent.selectOptions(screen.getByLabelText("Formato do programa"), "padrao");
  expect(screen.getByRole("checkbox", { name: /IA pode inserir blocos extras/ })).toBeEnabled();
});

it("permite selecionar o perfil jornalismo e aplicar a estrutura sugerida", async () => {
  await renderCriacao();
  expect(screen.queryByRole("button", { name: "Usar estrutura de jornalismo sugerida" })).not.toBeInTheDocument();

  await userEvent.selectOptions(screen.getByLabelText("Perfil do programa"), "jornalismo");
  await userEvent.click(screen.getByRole("button", { name: "Usar estrutura de jornalismo sugerida" }));

  expect(await screen.findByText("Escalada (manchetes)")).toBeInTheDocument();
  expect(screen.getAllByText("Notícia").length).toBeGreaterThan(0);
  expect(screen.getByText("Giro de notícias")).toBeInTheDocument();
});

describe("EditarProgramaForm (relógio da hora)", () => {
  async function renderEdicao(comRelogio: boolean) {
    const { PROGRAMA_VAZIO } = await import("../../lib/types");
    const { presetsFixture, relogioA } = await import("../../lib/__tests__/relogioFixtures");
    const programa = { ...PROGRAMA_VAZIO, id: 5, radio_config_id: 1, nome: "Tarde", relogio_hora: comRelogio ? relogioA() : null };
    apiFetchMock.mockReset();
    apiFetchMock.mockImplementation((path: string, opcoes?: { method?: string; body?: string }) => {
      if (path === "/config/relogios/presets") return Promise.resolve(presetsFixture());
      if (path === "/config/radio") return Promise.reject(new Error("sem radio configurado"));
      if (path === "/config/programas/5" && opcoes?.method === "PUT") return Promise.resolve(programa);
      if (path === "/config/programas/5") return Promise.resolve(programa);
      if (path === "/config/programas/5/relogio" && opcoes?.method === "PUT") {
        return Promise.resolve({ ...programa, relogio_hora: JSON.parse(opcoes.body!) });
      }
      if (path === "/config/programas/5/relogio") return Promise.resolve({ ...programa, relogio_hora: null });
      return Promise.resolve([]);
    });
    render(<EditarProgramaForm programaId={5} />);
    await screen.findByText("Editar programa");
    await screen.findByRole("option", { name: "A: Musical com companhia" });
  }

  const chamadas = () => apiFetchMock.mock.calls
    .filter(([, opcoes]) => opcoes?.method)
    .map(([path, opcoes]) => `${opcoes.method} ${path}`);

  it("salvar com o relógio alterado chama PUT do programa e depois PUT do relógio", async () => {
    await renderEdicao(false);
    await userEvent.selectOptions(screen.getByLabelText("Relógio da hora"), "A");
    await userEvent.click(screen.getByRole("button", { name: "Salvar programa" }));
    expect((await screen.findAllByText("Programa salvo.")).length).toBeGreaterThan(0);
    expect(chamadas()).toEqual(["PUT /config/programas/5", "PUT /config/programas/5/relogio"]);
    const corpo = JSON.parse(apiFetchMock.mock.calls.find(([p, o]) => p === "/config/programas/5/relogio" && o)![1].body);
    expect(corpo.preset).toBe("A");
    expect(corpo.eventos).toHaveLength(12);
  });

  it("'Sem relógio' num programa com relógio chama DELETE", async () => {
    await renderEdicao(true);
    expect(screen.getByLabelText("Relógio da hora")).toHaveValue("A");
    await userEvent.selectOptions(screen.getByLabelText("Relógio da hora"), "");
    await userEvent.click(screen.getByRole("button", { name: "Salvar programa" }));
    expect((await screen.findAllByText("Programa salvo.")).length).toBeGreaterThan(0);
    expect(chamadas()).toEqual(["PUT /config/programas/5", "DELETE /config/programas/5/relogio"]);
  });

  it("programa sem relógio e sem mudança não chama a rota do relógio", async () => {
    await renderEdicao(false);
    await userEvent.click(screen.getByRole("button", { name: "Salvar programa" }));
    expect((await screen.findAllByText("Programa salvo.")).length).toBeGreaterThan(0);
    expect(chamadas()).toEqual(["PUT /config/programas/5"]);
  });
});
