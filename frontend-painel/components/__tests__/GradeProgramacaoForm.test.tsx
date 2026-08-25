import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { fireEvent } from "@testing-library/react";
import GradeProgramacaoForm from "../GradeProgramacaoForm";
import { PROGRAMA_VAZIO, Programa } from "../../lib/types";
import { BibliotecaAudioItem } from "../../lib/bibliotecaAudio";

function programaFixture(overrides: Partial<Programa> = {}): Programa {
  return {
    ...PROGRAMA_VAZIO,
    id: 5,
    radio_config_id: 1,
    horario_inicio: "08:00:00",
    horario_fim: "10:00:00",
    ...overrides,
  };
}

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

type MockDados = {
  programa: Programa;
  patrocinadores?: unknown[];
  vinhetas?: BibliotecaAudioItem[];
  categorias?: unknown[];
  roster?: unknown[];
  radialistas?: unknown[];
};

async function renderComPrograma({
  programa,
  patrocinadores = [],
  vinhetas = [],
  categorias = [],
  roster = [],
  radialistas = [],
}: MockDados) {
  apiFetchMock.mockImplementation((path: string) => {
    if (path === "/patrocinadores") return Promise.resolve(patrocinadores);
    if (path === "/biblioteca-audio") return Promise.resolve(vinhetas);
    if (path === "/categorias-vinheta") return Promise.resolve(categorias);
    if (path === "/config/radialistas") return Promise.resolve(radialistas);
    if (path === `/config/programas/${programa.id}/radialistas`) return Promise.resolve(roster);
    if (path === `/config/programas/${programa.id}`) return Promise.resolve(programa);
    return Promise.resolve(programa);
  });
  render(<GradeProgramacaoForm programaId={programa.id} />);
  await screen.findByText(/Montagem de blocos/);
}

function criarDataTransfer() {
  const dados: Record<string, string> = {};
  return {
    effectAllowed: "",
    setData: (tipo: string, valor: string) => {
      dados[tipo] = valor;
    },
    getData: (tipo: string) => dados[tipo] ?? "",
  };
}

describe("GradeProgramacaoForm", () => {
  it("mostra estado vazio quando o programa nao tem estrutura customizada", async () => {
    await renderComPrograma({ programa: programaFixture({ estrutura_blocos: [] }) });
    expect(screen.getByText(/Sequência vazia/)).toBeInTheDocument();
  });

  it("adiciona bloco preset ao clicar (paleta e' clicavel, nao so' arrastavel)", async () => {
    await renderComPrograma({ programa: programaFixture({ estrutura_blocos: [] }) });

    await userEvent.click(screen.getByRole("button", { name: "+ Abertura" }));

    expect(await screen.findByText("Abertura")).toBeInTheDocument();
    expect(screen.getByText(/~40s/)).toBeInTheDocument();
  });

  it("calcula a duracao total do ciclo somando os blocos", async () => {
    await renderComPrograma({ programa: programaFixture({ estrutura_blocos: ["abertura", "musica"] }) });
    // abertura(40s) + musica(15s chamada + 180s faixa = 195s) = 235s = 3min 55s
    expect(await screen.findByText(/1 volta completa da estrutura ≈ 3min 55s/)).toBeInTheDocument();
  });

  it("remove bloco ao clicar no x", async () => {
    await renderComPrograma({ programa: programaFixture({ estrutura_blocos: ["abertura", "musica"] }) });
    await screen.findByText("Abertura");

    const removerBotoes = screen.getAllByTitle("Remover");
    await userEvent.click(removerBotoes[0]);

    expect(screen.queryByText("Abertura")).not.toBeInTheDocument();
    expect(screen.getByText("Música")).toBeInTheDocument();
  });

  it("reordena bloco ao clicar na seta", async () => {
    await renderComPrograma({ programa: programaFixture({ estrutura_blocos: ["abertura", "musica"] }) });
    await screen.findByText("Abertura");

    const setasDireita = screen.getAllByTitle("Mover pra baixo");
    await userEvent.click(setasDireita[0]);

    const itens = screen.getAllByRole("listitem").map((li) => li.textContent ?? "");
    expect(itens[0]).toContain("Música");
    expect(itens[1]).toContain("Abertura");
  });

  it("adiciona bloco customizado via texto livre", async () => {
    await renderComPrograma({ programa: programaFixture({ estrutura_blocos: [] }) });

    await userEvent.type(
      screen.getByPlaceholderText("Bloco personalizado e pressione Enter"),
      "Trecho de humor{Enter}"
    );

    expect(await screen.findByText("Trecho de humor")).toBeInTheDocument();
  });

  it("mostra vinhetas e propagandas da conta agrupadas por categoria na paleta", async () => {
    await renderComPrograma({
      programa: programaFixture({ estrutura_blocos: [] }),
      vinhetas: [
        { id: 9, nome: "Vinheta QA", categoria_id: null, audio_nome_original: "x.mp3", duracao_segundos: 12, cor: null, ordem: 0, ativo: true },
      ],
      patrocinadores: [{ id: 3, nome: "Loja X", categoria_id: null, tipo_conteudo: "texto", ativo: true }],
    });

    expect(await screen.findByText("Vinheta QA")).toBeInTheDocument();
    expect(screen.getByText("Loja X")).toBeInTheDocument();
  });

  it("arrastar um item da paleta pra sequencia insere na posicao solta", async () => {
    await renderComPrograma({
      programa: programaFixture({ estrutura_blocos: ["comentario"] }),
      vinhetas: [
        { id: 9, nome: "Vinheta QA", categoria_id: null, audio_nome_original: "x.mp3", duracao_segundos: 12, cor: null, ordem: 0, ativo: true },
      ],
    });
    await screen.findByText("Vinheta QA");

    const origem = screen.getByText("Vinheta QA").closest("button")!;
    const alvo = screen.getByText("Comentário").closest("li")!;
    const dataTransfer = criarDataTransfer();

    fireEvent.dragStart(origem, { dataTransfer });
    fireEvent.dragOver(alvo, { dataTransfer });
    fireEvent.drop(alvo, { dataTransfer });

    const itens = screen.getAllByRole("listitem").map((li) => li.textContent ?? "");
    expect(itens[0]).toContain("Vinheta: Vinheta QA");
    expect(itens[1]).toContain("Comentário");
  });

  it("arrastar um bloco dentro da propria sequencia reordena", async () => {
    await renderComPrograma({ programa: programaFixture({ estrutura_blocos: ["abertura", "musica", "comentario"] }) });
    await screen.findByText("Abertura");

    const origem = screen.getByText("Abertura").closest("li")!;
    const alvo = screen.getByText("Comentário").closest("li")!;
    const dataTransfer = criarDataTransfer();

    fireEvent.dragStart(origem, { dataTransfer });
    fireEvent.dragOver(alvo, { dataTransfer });
    fireEvent.drop(alvo, { dataTransfer });

    const itens = screen.getAllByRole("listitem").map((li) => li.textContent ?? "");
    expect(itens[0]).toContain("Música");
    expect(itens[1]).toContain("Abertura");
    expect(itens[2]).toContain("Comentário");
  });
});
