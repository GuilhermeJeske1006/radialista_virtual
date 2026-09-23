import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import VinhetasProgramaSection, { marcarVinhetasCriadas } from "../VinhetasProgramaSection";
import { Vinheta } from "../../lib/bibliotecaAudio";

const apiFetchMock = vi.fn();

vi.mock("../../lib/api", () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
  apiFetchBlob: vi.fn(),
  apiFetchForm: vi.fn(),
  ApiError: class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  },
}));

function vinheta(parcial: Partial<Vinheta>): Vinheta {
  return {
    id: 1,
    nome: "Abertura – Manhã",
    programa_id: 5,
    categoria_id: null,
    papel: "abertura",
    texto: "Começa agora o Manhã.",
    voz_id: null,
    trilha_id: 3,
    trilha_origem: "ia",
    volume_trilha_db: -14,
    usar_trilha: true,
    status: "pronta",
    erro_msg: null,
    origem: "auto",
    ativo: true,
    tem_audio: true,
    duracao_segundos: 6,
    ...parcial,
  };
}

function responderCom(lista: Vinheta[]) {
  apiFetchMock.mockImplementation((caminho: string, opcoes?: RequestInit) => {
    if (caminho.startsWith("/vinhetas?")) return Promise.resolve(lista);
    if (caminho === "/trilhas/estilos") return Promise.resolve({ generico: 0 });
    if (caminho.endsWith("/remixar")) {
      const corpo = JSON.parse(String(opcoes?.body));
      return Promise.resolve({ ...lista[0], ...corpo });
    }
    return Promise.resolve([]);
  });
}

describe("VinhetasProgramaSection", () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
    window.sessionStorage.clear();
  });

  it("mostra as 3 vinhetas, o selo da trilha e o estado de geração", async () => {
    responderCom([
      vinheta({ id: 1, papel: "abertura" }),
      vinheta({ id: 2, papel: "passagem", status: "gerando", tem_audio: false }),
      vinheta({ id: 3, papel: "encerramento", status: "erro", erro_msg: "Voz IA indisponível", tem_audio: false }),
    ]);
    render(<VinhetasProgramaSection programaId={5} />);

    expect(await screen.findByText("Abertura")).toBeInTheDocument();
    expect(screen.getByText("Trilha gerada por IA")).toBeInTheDocument();
    expect(screen.getByText("Gerando trilha e mixando...")).toBeInTheDocument();
    expect(screen.getByText("Voz IA indisponível")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Ouvir/ })).toBeInTheDocument();
    // banco vazio: botao desabilitado
    expect(screen.getByRole("button", { name: "Escolher do banco" })).toBeDisabled();
  });

  it("mostra o aviso uma vez depois de criar o programa", async () => {
    responderCom([vinheta({})]);
    marcarVinhetasCriadas(5);
    render(<VinhetasProgramaSection programaId={5} />);

    expect(
      await screen.findByText("Criamos 3 vinhetas com trilha para este programa e colocamos na programação.")
    ).toBeInTheDocument();
    expect(window.sessionStorage.getItem("locufy:vinhetas-criadas:5")).toBeNull();
  });

  it("desligar a trilha chama remixar", async () => {
    responderCom([vinheta({})]);
    render(<VinhetasProgramaSection programaId={5} />);

    await userEvent.click(await screen.findByRole("checkbox", { name: "Usar trilha" }));

    await waitFor(() =>
      expect(apiFetchMock).toHaveBeenCalledWith(
        "/vinhetas/1/remixar",
        expect.objectContaining({ method: "POST", body: JSON.stringify({ usar_trilha: false }) })
      )
    );
  });
});
