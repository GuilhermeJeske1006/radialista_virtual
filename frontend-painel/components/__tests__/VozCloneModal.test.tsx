import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import VozCloneModal, { arquivoGravado, formatoGravacao } from "../VozCloneModal";
import { apiFetchForm, ApiError } from "../../lib/api";

vi.mock("../../lib/api", async (original) => ({ ...await original<typeof import("../../lib/api")>(), apiFetchForm: vi.fn() }));
const analisar = { duracao_segundos: 65, fala_segundos: 61, clipping_percentual: 0, avisos: [] };
const stopTrack = vi.fn();
let instance: FakeRecorder;
class FakeRecorder {
  static isTypeSupported = vi.fn((tipo: string) => tipo === "audio/mp4");
  mimeType = "audio/mp4";
  state = "inactive";
  ondataavailable?: (event: { data: Blob }) => void;
  onstop?: () => void;
  onerror?: () => void;
  constructor() { instance = this; }
  start() { this.state = "recording"; }
  stop() {
    this.state = "inactive";
    this.ondataavailable?.({ data: new Blob(["sample"], { type: this.mimeType }) });
    this.onstop?.();
  }
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal("MediaRecorder", FakeRecorder);
  Object.defineProperty(URL, "createObjectURL", { configurable: true, value: vi.fn(() => "blob:sample") });
  Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() });
  Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia: vi.fn(async () => ({ getTracks: () => [{ stop: stopTrack }] })) } });
});
afterEach(() => vi.unstubAllGlobals());

describe("Clonagem de voz", () => {
  it("negocia MP4 e preserva MIME/extensão reais", () => {
    expect(formatoGravacao()).toEqual({ mimeType: "audio/mp4", audioBitsPerSecond: 192000 });
    const file = arquivoGravado(new Blob(["audio"], { type: "audio/mp4" }));
    expect(file.name).toBe("gravacao.m4a"); expect(file.type).toBe("audio/mp4");
  });
  it("exige análise e invalida resultado ao trocar arquivos", async () => {
    vi.mocked(apiFetchForm).mockResolvedValue(analisar);
    render(<VozCloneModal onCriada={vi.fn()} onFechar={vi.fn()} />);
    await userEvent.type(screen.getByLabelText("Nome da voz"), "Locutor");
    const file = new File(["sample"], "amostra.wav", { type: "audio/wav" });
    await userEvent.upload(screen.getByLabelText("Arquivos de voz"), file);
    expect(screen.getByRole("button", { name: "Clonar voz" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Analisar amostras" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Clonar voz" })).toBeEnabled());
    await userEvent.upload(screen.getByLabelText("Arquivos de voz"), new File(["other"], "outra.wav", { type: "audio/wav" }));
    expect(screen.getByRole("button", { name: "Clonar voz" })).toBeDisabled();
    expect(URL.revokeObjectURL).toHaveBeenCalled();
  });
  it("mostra rejeição de silêncio e não libera clonagem", async () => {
    vi.mocked(apiFetchForm).mockRejectedValue(new ApiError(400, "Detectamos apenas 0s de fala."));
    render(<VozCloneModal onCriada={vi.fn()} onFechar={vi.fn()} />);
    await userEvent.upload(screen.getByLabelText("Arquivos de voz"), new File(["zero"], "silencio.wav", { type: "audio/wav" }));
    await userEvent.click(screen.getByText("Analisar amostras"));
    expect(await screen.findByRole("alert")).toHaveTextContent("0s de fala");
    expect(screen.getByRole("button", { name: "Clonar voz" })).toBeDisabled();
  });
  it("envia vários arquivos e entrega estado de verificação ao seletor", async () => {
    const criada = { id: 1, voz_id: "pendente", nome: "Locutor", requer_verificacao: true };
    vi.mocked(apiFetchForm).mockResolvedValueOnce(analisar).mockResolvedValueOnce(criada);
    const onCriada = vi.fn();
    render(<VozCloneModal onCriada={onCriada} onFechar={vi.fn()} />);
    await userEvent.type(screen.getByLabelText("Nome da voz"), "Locutor");
    await userEvent.upload(screen.getByLabelText("Arquivos de voz"), [new File(["a"], "a.wav", { type: "audio/wav" }), new File(["b"], "b.wav", { type: "audio/wav" })]);
    await userEvent.click(screen.getByText("Analisar amostras"));
    await waitFor(() => expect(screen.getByRole("button", { name: "Clonar voz" })).toBeEnabled());
    await userEvent.click(screen.getByRole("button", { name: "Clonar voz" }));
    await waitFor(() => expect(onCriada).toHaveBeenCalledWith(criada));
    expect(vi.mocked(apiFetchForm).mock.calls[1][1].getAll("arquivos")).toHaveLength(2);
  });
  it("libera microfone e timer ao desmontar gravando", async () => {
    const { unmount } = render(<VozCloneModal onCriada={vi.fn()} onFechar={vi.fn()} />);
    await userEvent.click(screen.getByText("Gravar pelo microfone"));
    await screen.findByText("Parar gravação");
    unmount();
    expect(stopTrack).toHaveBeenCalled(); expect(instance.state).toBe("inactive");
  });
  it("grava e envia M4A em navegador que não suporta WebM", async () => {
    vi.mocked(apiFetchForm).mockResolvedValue(analisar);
    render(<VozCloneModal onCriada={vi.fn()} onFechar={vi.fn()} />);
    await userEvent.click(screen.getByText("Gravar pelo microfone"));
    await userEvent.click(await screen.findByText("Parar gravação"));
    expect(await screen.findByText("gravacao.m4a")).toBeInTheDocument();
    await userEvent.click(screen.getByText("Analisar amostras"));
    const file = vi.mocked(apiFetchForm).mock.calls[0][1].get("arquivos") as File;
    expect(file.name).toBe("gravacao.m4a"); expect(file.type).toBe("audio/mp4");
  });
  it("bloqueia excesso de arquivos", () => {
    render(<VozCloneModal onCriada={vi.fn()} onFechar={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Arquivos de voz"), { target: { files: Array.from({ length: 6 }, (_, i) => new File(["a"], `${i}.wav`)) } });
    expect(screen.getByRole("alert")).toHaveTextContent("até 5 arquivos");
    expect(screen.getByText("Analisar amostras")).toBeDisabled();
  });
});

it("preserva o erro e descarta a gravação parcial quando o gravador falha", async () => {
  render(<VozCloneModal onCriada={vi.fn()} onFechar={vi.fn()} />);
  await userEvent.click(screen.getByText("Gravar pelo microfone"));
  act(() => { instance.onerror?.(); instance.stop(); });
  expect(await screen.findByRole("alert")).toHaveTextContent("Falha na gravação");
  expect(screen.queryByText("gravacao.m4a")).not.toBeInTheDocument();
  expect(screen.getByText("Analisar amostras")).toBeDisabled();
});
