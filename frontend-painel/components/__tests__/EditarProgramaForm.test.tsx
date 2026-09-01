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
