import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RoteiroBlocosEditor from "../RoteiroBlocosEditor";
import { BibliotecaAudioItem } from "../../lib/bibliotecaAudio";
import { Patrocinador } from "../../lib/types";

const apiFetchBlobMock = vi.fn();

vi.mock("../../lib/api", () => ({
  apiFetchBlob: (...args: unknown[]) => apiFetchBlobMock(...args),
  ApiError: class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  },
}));

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

const patrocinadorFixture: Patrocinador = {
  id: 3,
  nome: "Loja X",
  categoria_id: null,
  tipo_conteudo: "texto",
  ativo: true,
};

function renderEditor(overrides: Partial<Parameters<typeof RoteiroBlocosEditor>[0]> = {}) {
  const onChange = vi.fn();
  render(
    <RoteiroBlocosEditor
      blocos={[]}
      onChange={onChange}
      patrocinadores={[]}
      vinhetas={[]}
      categorias={[]}
      {...overrides}
    />
  );
  return onChange;
}

describe("RoteiroBlocosEditor", () => {
  it("mostra estado vazio quando nao tem estrutura", () => {
    renderEditor();
    expect(screen.getByText(/Sequência vazia/)).toBeInTheDocument();
  });

  it("adiciona bloco preset ao clicar (paleta e' clicavel, nao so' arrastavel)", async () => {
    const onChange = renderEditor();
    await userEvent.click(screen.getByRole("button", { name: "+ Abertura" }));
    expect(onChange).toHaveBeenCalledWith(["abertura"]);
  });

  it("calcula a duracao total do ciclo somando os blocos", () => {
    renderEditor({ blocos: ["abertura", "musica"] });
    // abertura(40s) + musica(15s chamada + 180s faixa = 195s) = 235s = 3min 55s
    expect(screen.getByText(/1 volta completa da estrutura ≈ 3min 55s/)).toBeInTheDocument();
  });

  it("remove bloco ao clicar no x", async () => {
    const onChange = renderEditor({ blocos: ["abertura", "musica"] });
    const removerBotoes = screen.getAllByTitle("Remover");
    await userEvent.click(removerBotoes[0]);
    expect(onChange).toHaveBeenCalledWith(["musica"]);
  });

  it("reordena bloco ao clicar na seta", async () => {
    const onChange = renderEditor({ blocos: ["abertura", "musica"] });
    const setasDireita = screen.getAllByTitle("Mover pra baixo");
    await userEvent.click(setasDireita[0]);
    expect(onChange).toHaveBeenCalledWith(["musica", "abertura"]);
  });

  it("adiciona bloco customizado via texto livre", async () => {
    const onChange = renderEditor();
    await userEvent.type(
      screen.getByPlaceholderText("Bloco personalizado e pressione Enter"),
      "Trecho de humor{Enter}"
    );
    expect(onChange).toHaveBeenCalledWith(["Trecho de humor"]);
  });

  it("mostra vinhetas e propagandas agrupadas por categoria na paleta", () => {
    renderEditor({ vinhetas: [vinhetaFixture], patrocinadores: [patrocinadorFixture] });
    expect(screen.getByText("Vinheta QA")).toBeInTheDocument();
    expect(screen.getByText("Loja X")).toBeInTheDocument();
  });

  it("busca na paleta filtra por nome, escondendo o que nao bate", async () => {
    renderEditor({ vinhetas: [vinhetaFixture], patrocinadores: [patrocinadorFixture] });
    await userEvent.type(screen.getByPlaceholderText("Buscar na paleta..."), "Loja");
    expect(screen.queryByText("Vinheta QA")).not.toBeInTheDocument();
    expect(screen.getByText("Loja X")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "+ Abertura" })).not.toBeInTheDocument();
  });

  it("botao de preview toca a vinheta sem inserir na sequencia", async () => {
    apiFetchBlobMock.mockResolvedValue(new Blob());
    const originalAudio = window.HTMLMediaElement.prototype.play;
    window.HTMLMediaElement.prototype.play = vi.fn().mockResolvedValue(undefined);
    const onChange = renderEditor({ vinhetas: [vinhetaFixture] });

    await userEvent.click(screen.getByTitle("Ouvir"));

    expect(apiFetchBlobMock).toHaveBeenCalledWith("/biblioteca-audio/9/audio");
    expect(onChange).not.toHaveBeenCalled();
    window.HTMLMediaElement.prototype.play = originalAudio;
  });

  it("arrastar um item da paleta pra sequencia insere na posicao solta", () => {
    const onChange = renderEditor({ blocos: ["comentario"], vinhetas: [vinhetaFixture] });

    const origem = screen.getByTestId("vinheta-paleta-9");
    const alvo = screen.getByText("Comentário").closest("li")!;
    const dataTransfer = criarDataTransfer();

    fireEvent.dragStart(origem, { dataTransfer });
    fireEvent.dragOver(alvo, { dataTransfer });
    fireEvent.drop(alvo, { dataTransfer });

    expect(onChange).toHaveBeenCalledWith(["vinheta:9", "comentario"]);
  });

  it("arrastar um bloco dentro da propria sequencia reordena", () => {
    const onChange = renderEditor({ blocos: ["abertura", "musica", "comentario"] });

    const origem = screen.getByText("Abertura").closest("li")!;
    const alvo = screen.getByText("Comentário").closest("li")!;
    const dataTransfer = criarDataTransfer();

    fireEvent.dragStart(origem, { dataTransfer });
    fireEvent.dragOver(alvo, { dataTransfer });
    fireEvent.drop(alvo, { dataTransfer });

    expect(onChange).toHaveBeenCalledWith(["musica", "abertura", "comentario"]);
  });
});
