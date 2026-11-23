import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { useLiveEngine } from "../useLiveEngine";
import { PROGRAMA_VAZIO } from "../../lib/types";

// F11 item 1: todo bloco que o /proxima entrega (fala, vinheta, patrocinador, multi-voz) é relatado ao as-run
// quando termina de tocar. Antes só o bloco de fala com música e voz única era confirmado, e o resto ficava
// "enviado" para sempre (os cortes da F14 saíam vazios).

const mocks = vi.hoisted(() => ({ api: vi.fn(), proxima: vi.fn(), tts: vi.fn(), arquivo: vi.fn() }));
vi.mock("../../lib/api", () => ({
  apiFetch: mocks.api, apiFetchComTimeout: mocks.proxima,
  apiFetchBlob: mocks.arquivo, apiFetchBlobComTimeout: mocks.tts,
  ApiError: class extends Error {},
}));
vi.mock("../../lib/radialistas", () => ({ setRadialistaAtualId: vi.fn() }));

const players: AudioTeste[] = [];
class AudioTeste {
  private ouvintes: Record<string, (() => void)[]> = {};
  onended: (() => void) | null = null;
  onerror: (() => void) | null = null;
  volume = 0;
  muted = false;
  ended = false;
  paused = true;
  addEventListener(evento: string, cb: () => void) {
    (this.ouvintes[evento] ??= []).push(cb);
  }
  play = vi.fn(() => { this.paused = false; return Promise.resolve(); });
  pause() { this.paused = true; }
  constructor(public src: string) { if (!src.startsWith("data:")) players.push(this); }
  terminar() {
    this.ended = true;
    this.ouvintes.ended?.forEach((cb) => cb());
    this.onended?.();
  }
}

const segmento = (extra = {}) => ({
  tipo: "comentario", fala: "Hoje tem feira na praça.", criado_em: new Date().toISOString(),
  audio_status: "pendente", pausa_antes_ms: 0, as_run_evento_id: 42, ...extra,
});

const relatos = () => mocks.api.mock.calls.filter(([path]) => String(path).includes("/as-run/"));

beforeEach(() => {
  vi.useFakeTimers();
  vi.resetAllMocks();
  players.length = 0;
  mocks.api.mockImplementation((path: string) => {
    if (path === "/config/radialistas") return Promise.resolve([{ id: 1, nome_locutor: "Ana", timezone: "UTC" }]);
    if (path === "/config/radialistas/1/programas") return Promise.resolve([
      { ...PROGRAMA_VAZIO, id: 1, radio_config_id: 1, ativo: false },
    ]);
    if (path === "/config/radio") return Promise.resolve({});
    if (path.endsWith("/preparo")) return Promise.resolve({ disponivel: false });
    if (path.includes("/as-run/")) return Promise.resolve({ id: 42, status: "confirmado" });
    return Promise.reject(new Error("Sem cama musical neste teste"));
  });
  mocks.proxima.mockImplementation(() => new Promise(() => {}));
  mocks.tts.mockResolvedValue(new Blob(["voz"]));
  mocks.arquivo.mockResolvedValue(new Blob(["arquivo"]));
  vi.stubGlobal("Audio", AudioTeste);
  vi.stubGlobal("YT", { Player: class {}, PlayerState: { ENDED: 0, PLAYING: 1 } });
  let id = 0;
  vi.stubGlobal("URL", Object.assign(URL, {
    createObjectURL: vi.fn(() => `blob:${++id}`), revokeObjectURL: vi.fn(),
  }));
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

async function iniciar() {
  const hook = renderHook(() => useLiveEngine());
  await act(async () => {});
  act(() => hook.result.current.selecionarPrograma(hook.result.current.programasTodos[0]));
  await act(async () => { hook.result.current.iniciarPrograma(); });
  return hook;
}

async function terminarPrimeiroAudio() {
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  expect(players.length).toBeGreaterThan(0);
  await act(async () => { players[0].terminar(); });
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
}

it("fala sem música tocada até o fim é confirmada no as-run", async () => {
  mocks.proxima.mockResolvedValueOnce(segmento());
  await iniciar();
  await terminarPrimeiroAudio();

  expect(relatos()).toEqual([
    ["/live/1/programas/1/as-run/42", { method: "POST", body: JSON.stringify({ status: "confirmado" }) }],
  ]);
});

it("vinheta tocada até o fim também é confirmada", async () => {
  mocks.proxima.mockResolvedValueOnce(segmento({
    tipo: "vinheta", fala: "Rádio Teste, a sua companhia.", vinheta_id: 3, audio_status: "nao_aplicavel",
    as_run_evento_id: 43,
  }));
  await iniciar();
  await terminarPrimeiroAudio();

  expect(relatos().map(([path, init]) => [path, JSON.parse(String(init.body)).status]))
    .toEqual([["/live/1/programas/1/as-run/43", "confirmado"]]);
});

it("bloco que não chega ao fim por pausa não é relatado", async () => {
  mocks.proxima.mockResolvedValueOnce(segmento());
  const hook = await iniciar();
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  await act(async () => { hook.result.current.pausarPrograma(); });
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });

  expect(relatos()).toEqual([]);
});
