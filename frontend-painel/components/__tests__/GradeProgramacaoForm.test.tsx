import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
  await screen.findByText(/Roteiro do programa/);
}

describe("GradeProgramacaoForm", () => {
  it("carrega o programa e mostra a estrutura salva", async () => {
    await renderComPrograma({ programa: programaFixture({ estrutura_blocos: ["abertura", "musica"] }) });
    expect(await screen.findByText("Abertura")).toBeInTheDocument();
    expect(screen.getAllByText("Música").length).toBeGreaterThan(0);
  });

  it("mostra erro quando o programa nao carrega", async () => {
    apiFetchMock.mockImplementation((path: string) => {
      if (path === `/config/programas/5`) return Promise.reject(new Error("Erro ao carregar programa"));
      return Promise.resolve([]);
    });
    render(<GradeProgramacaoForm programaId={5} />);
    expect(await screen.findByText("Erro ao carregar programa")).toBeInTheDocument();
  });

  it("salva a programação chamando PUT com a estrutura atual", async () => {
    await renderComPrograma({ programa: programaFixture({ estrutura_blocos: ["abertura"] }) });
    apiFetchMock.mockClear();
    apiFetchMock.mockResolvedValue(programaFixture({ estrutura_blocos: ["abertura"] }));

    await userEvent.click(screen.getByRole("button", { name: "Salvar programação" }));

    expect(apiFetchMock).toHaveBeenCalledWith(
      "/config/programas/5",
      expect.objectContaining({ method: "PUT" })
    );
    expect(await screen.findByText("Programação salva.")).toBeInTheDocument();
  });

  it("mostra a secao de elenco do programa", async () => {
    await renderComPrograma({ programa: programaFixture({ estrutura_blocos: [] }) });
    expect(screen.getByText("Elenco do programa")).toBeInTheDocument();
  });
});
