import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { useLiveEngine } from "../useLiveEngine";
import { PROGRAMA_VAZIO } from "../../lib/types";

// F1 (relógio da hora): o painel informa ao backend quando cada bloco vai ao ar (inicio_previsto),
// encadeando a duração prevista e corrigindo pelo desvio real; e o programa agendado começa no
// horario_inicio, não no próximo tick de 15 s do polling.

const mocks = vi.hoisted(() => ({ api: vi.fn(), proxima: vi.fn(), tts: vi.fn(), arquivo: vi.fn() }));
vi.mock("../../lib/api", () => ({
  apiFetch: mocks.api, apiFetchComTimeout: mocks.proxima,
  apiFetchBlob: mocks.arquivo, apiFetchBlobComTimeout: mocks.tts,
  ApiError: class extends Error {},
}));
vi.mock("../../lib/radialistas", () => ({ setRadialistaAtualId: vi.fn() }));

const players: AudioTeste[] = [];
class AudioTeste {
  onended: (() => void) | null = null;
  volume = 0;
  ended = false;
  addEventListener() {}
  play = vi.fn(() => Promise.resolve());
  pause() {}
  constructor(public src: string) { if (!src.startsWith("data:")) players.push(this); }
  terminar() { this.ended = true; this.onended?.(); }
}

function pendente<T>() {
  let resolve!: (valor: T) => void;
  const promise = new Promise<T>((r) => { resolve = r; });
  return { promise, resolve };
}

const segmento = (fala: string, duracao: number) => ({
  tipo: "comentario", fala, criado_em: new Date().toISOString(), audio_status: "pendente", tom: "calmo",
  pausa_antes_ms: 0, duracao_prevista_s: duracao,
});

function programasNaApi(programa: object) {
  mocks.api.mockImplementation((path: string) => {
    if (path === "/config/radialistas") return Promise.resolve([{ id: 1, nome_locutor: "Ana", timezone: "UTC" }]);
    if (path === "/config/radialistas/1/programas") return Promise.resolve([{ ...PROGRAMA_VAZIO, id: 1, radio_config_id: 1, ...programa }]);
    if (path === "/config/radio") return Promise.resolve({});
    if (path === "/live/1/programas/1/preparo") return Promise.resolve({ disponivel: false });
    return Promise.reject(new Error("Sem cama musical neste teste"));
  });
}

const enviados = () => mocks.proxima.mock.calls.map(([, opcoes]) => JSON.parse(opcoes.body).inicio_previsto);

beforeEach(() => {
  vi.useFakeTimers();
  vi.resetAllMocks();
  players.length = 0;
  mocks.proxima.mockImplementation(() => new Promise(() => {}));
  mocks.tts.mockImplementation(() => new Promise(() => {}));
  vi.stubGlobal("Audio", AudioTeste);
  vi.stubGlobal("YT", { Player: class {}, PlayerState: { ENDED: 0, PLAYING: 1 } });
  let id = 0;
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: vi.fn(() => `blob:${++id}`), revokeObjectURL: vi.fn() }));
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

it("inicio_previsto cresce com a duração prevista e avança com o atraso real", async () => {
  vi.setSystemTime(new Date("2026-11-10T15:00:00.000Z"));
  programasNaApi({ ativo: false });
  const primeiroAudio = pendente<Blob>();
  mocks.proxima
    .mockResolvedValueOnce(segmento("Primeira", 20))
    .mockResolvedValueOnce(segmento("Segunda", 30))
    .mockResolvedValueOnce(segmento("Terceira", 40))
    .mockResolvedValueOnce(segmento("Quarta", 50));
  mocks.tts.mockReturnValueOnce(primeiroAudio.promise).mockResolvedValue(new Blob(["voz"]));

  const { result } = renderHook(() => useLiveEngine());
  await act(async () => {});
  act(() => result.current.selecionarPrograma(result.current.programasTodos[0]));
  await act(async () => { result.current.iniciarPrograma(); });
  expect(enviados()).toEqual(["2026-11-10T15:00:00.000Z", "2026-11-10T15:00:20.000Z", "2026-11-10T15:00:50.000Z"]);

  // A voz do primeiro bloco atrasa 10 s: o próximo pedido corrige pelo desvio medido.
  await act(async () => { await vi.advanceTimersByTimeAsync(10_000); primeiroAudio.resolve(new Blob(["primeira"])); });
  expect(result.current.falasPrograma[0].fala).toBe("Primeira");
  await act(async () => { players[0].terminar(); await vi.advanceTimersByTimeAsync(1); });
  expect(enviados()[3]).toBe("2026-11-10T15:01:40.000Z");
});

it("programa agendado começa no horario_inicio e o primeiro pedido usa esse horário", async () => {
  vi.setSystemTime(new Date("2026-11-10T11:59:20.000Z"));
  programasNaApi({ ativo: true, horario_inicio: "12:00:00", horario_fim: "13:00:00" });
  const { result } = renderHook(() => useLiveEngine());
  await act(async () => {});
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  expect(result.current.programaAtivo).toBe(false);
  expect(enviados()[0]).toBe("2026-11-10T12:00:00.000Z");

  await act(async () => { await vi.advanceTimersByTimeAsync(39_500); });
  expect(result.current.programaAtivo).toBe(false);
  await act(async () => { await vi.advanceTimersByTimeAsync(1_000); });
  // Sem o timer pontual, o próximo tick de 15 s só viria às 12:00:05.
  expect(result.current.programaAtivo).toBe(true);
});
