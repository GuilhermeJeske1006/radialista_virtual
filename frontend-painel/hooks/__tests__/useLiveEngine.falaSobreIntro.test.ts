import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { useLiveEngine } from "../useLiveEngine";
import { PROGRAMA_VAZIO } from "../../lib/types";

// "Ramp" de rádio: fala curta do locutor por cima da introdução instrumental da música, quando o backend
// informa onde o vocal entra (inicio_vocal_segundos) e a fala cabe antes dele. Sem isso, a fala toca inteira
// antes da música, como sempre tocou.

const mocks = vi.hoisted(() => ({ api: vi.fn(), proxima: vi.fn(), tts: vi.fn(), arquivo: vi.fn() }));
vi.mock("../../lib/api", () => ({
  apiFetch: mocks.api, apiFetchComTimeout: mocks.proxima,
  apiFetchBlob: mocks.arquivo, apiFetchBlobComTimeout: mocks.tts,
  ApiError: class extends Error {},
}));
vi.mock("../../lib/radialistas", () => ({ setRadialistaAtualId: vi.fn() }));

let duracaoDaFala = 6;
const audios: AudioTeste[] = [];
class AudioTeste {
  private ouvintes: Record<string, (() => void)[]> = {};
  onended: (() => void) | null = null;
  onerror: (() => void) | null = null;
  volume = 0;
  muted = false;
  ended = false;
  paused = true;
  preload = "";
  duration = Number.NaN;
  tocou = false;
  pausada = false;
  addEventListener(evento: string, cb: () => void) { (this.ouvintes[evento] ??= []).push(cb); }
  play = vi.fn(() => { this.paused = false; this.tocou = true; return Promise.resolve(); });
  pause() { this.paused = true; this.pausada = true; }
  constructor(public src: string) {
    if (src.startsWith("data:")) return; // sondagem de autoplay
    audios.push(this);
    queueMicrotask(() => { this.duration = duracaoDaFala; this.disparar("loadedmetadata"); });
  }
  disparar(evento: string) { this.ouvintes[evento]?.forEach((cb) => cb()); }
  terminar() { this.ended = true; this.onended?.(); }
}
const tocadas = () => audios.filter((a) => a.tocou);

type EventosYT = {
  onReady: (e: { target: MusicaTeste }) => void;
  onStateChange: (e: { data: number; target: MusicaTeste }) => void;
  onError?: (e: { data: number }) => void;
};
const musicas: MusicaTeste[] = [];
let posicao = 0;
class MusicaTeste {
  unMute = vi.fn();
  setVolume = vi.fn();
  playVideo = vi.fn();
  mute = vi.fn();
  loadVideoById = vi.fn();
  stopVideo() {}
  destroy() {}
  getVolume() { return 100; }
  getCurrentTime() { return posicao; }
  constructor(_id: string, public config: { videoId: string; events: EventosYT }) { musicas.push(this); }
  pronto() { this.config.events.onReady({ target: this }); }
  tocando() { this.config.events.onStateChange({ data: 1, target: this }); }
  terminar() { this.config.events.onStateChange({ data: 0, target: this }); }
  falhar(codigo: number) { this.config.events.onError?.({ data: codigo }); }
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.resetAllMocks();
  audios.length = 0;
  musicas.length = 0;
  posicao = 0;
  duracaoDaFala = 6;
  Object.defineProperty(navigator, "userActivation", { configurable: true, get: () => ({ hasBeenActive: true }) });
  mocks.api.mockImplementation((path: string) => {
    if (path === "/config/radialistas") return Promise.resolve([{ id: 1, nome_locutor: "Ana", timezone: "UTC" }]);
    if (path === "/config/radialistas/1/programas") return Promise.resolve([
      { ...PROGRAMA_VAZIO, id: 1, radio_config_id: 1, ativo: false },
    ]);
    if (path === "/config/radio") return Promise.resolve({});
    if (path.endsWith("/preparo")) return Promise.resolve({ disponivel: false });
    if (path.endsWith("/musica-substituta")) {
      return Promise.resolve({ video_id: "musica-2", titulo: "Outra", inicio_segundos: 0, fim_segundos: null });
    }
    return Promise.reject(new Error("Sem cama musical neste teste"));
  });
  mocks.proxima.mockImplementation(() => new Promise(() => {}));
  mocks.tts.mockResolvedValue(new Blob(["voz"]));
  vi.stubGlobal("Audio", AudioTeste);
  vi.stubGlobal("YT", { Player: MusicaTeste, PlayerState: { ENDED: 0, PLAYING: 1 } });
  let id = 0;
  vi.stubGlobal("URL", Object.assign(URL, {
    createObjectURL: vi.fn(() => `blob:${++id}`), revokeObjectURL: vi.fn(),
  }));
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  delete (navigator as { userActivation?: unknown }).userActivation;
});

function bloco(vocal: number | null | undefined, extra: Record<string, unknown> = {}) {
  return {
    tipo: "musica", fala: "Agora, uma canção que você conhece.", video_id: "musica-1", titulo_musica: "Canção",
    criado_em: new Date().toISOString(), audio_status: "pendente", pausa_antes_ms: 0,
    musicas: [{ video_id: "musica-1", titulo: "Canção", inicio_segundos: 0, fim_segundos: null, inicio_vocal_segundos: vocal }],
    ...extra,
  };
}

async function iniciar() {
  const hook = renderHook(() => useLiveEngine());
  await act(async () => {});
  act(() => hook.result.current.selecionarPrograma(hook.result.current.programasTodos[0]));
  await act(async () => { hook.result.current.iniciarPrograma(); });
  return hook;
}

const avancar = (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });
const volumes = () => musicas[0].setVolume.mock.calls.map(([v]) => v as number);

it("introdução longa e fala curta: a música entra primeiro e a fala toca por cima, com a música abaixada", async () => {
  mocks.proxima.mockResolvedValueOnce(bloco(30));
  await iniciar();
  await avancar(50);

  // a música é carregada ANTES da fala: nada de fala tocando antes dela
  expect(tocadas()).toHaveLength(0);
  expect(musicas).toHaveLength(1);
  act(() => musicas[0].pronto());
  expect(musicas[0].loadVideoById).toHaveBeenLastCalledWith({ videoId: "musica-1", startSeconds: 0 });
  await act(async () => { musicas[0].tocando(); });

  // 1 s de música sozinha: a voz ainda não entrou (entra em 2 s)
  posicao = 1;
  await avancar(300);
  expect(tocadas()).toHaveLength(0);

  posicao = 2.1;
  await avancar(300);
  expect(tocadas()).toHaveLength(1);
  // música abaixada pra 30% enquanto o locutor fala (rampa até o alvo)
  await avancar(800);
  expect(Math.min(...volumes())).toBeLessThanOrEqual(30);
  expect(volumes().at(-1)).toBe(30);

  // fala termina: volume cheio volta
  await act(async () => { tocadas()[0].terminar(); });
  await avancar(1200);
  expect(volumes().at(-1)).toBe(100);
});

it("sem início do vocal conhecido: fala inteira ANTES da música, como sempre", async () => {
  mocks.proxima.mockResolvedValueOnce(bloco(null));
  await iniciar();
  await avancar(50);

  expect(tocadas()).toHaveLength(1);
  expect(musicas).toHaveLength(0); // música só depois da fala
  await act(async () => { tocadas()[0].terminar(); });
  await avancar(50);
  expect(musicas).toHaveLength(1);
});

it("fala longa demais pra introdução: fala antes da música", async () => {
  duracaoDaFala = 12; // 2 + 12 + 1,5 > 12 (vocal em 12 s)
  mocks.proxima.mockResolvedValueOnce(bloco(12));
  await iniciar();
  await avancar(50);

  expect(tocadas()).toHaveLength(1);
  expect(musicas).toHaveLength(0);
});

it("sem como medir a duração da fala: fala antes da música", async () => {
  duracaoDaFala = Number.NaN;
  mocks.proxima.mockResolvedValueOnce(bloco(60));
  await iniciar();
  await avancar(2500); // estoura o tempo de medir os metadados

  expect(tocadas()).toHaveLength(1);
  expect(musicas).toHaveLength(0);
});

it("página sem interação: não fala por cima da música (ela ainda estaria muda)", async () => {
  Object.defineProperty(navigator, "userActivation", { configurable: true, get: () => ({ hasBeenActive: false }) });
  mocks.proxima.mockResolvedValueOnce(bloco(30));
  await iniciar();
  await avancar(50);

  // fluxo de sempre: a fala vem primeiro (aqui segurada pelo bloqueio de autoplay) e a música só carrega
  // depois dela; a duração da fala nem chega a ser medida
  expect(audios).toHaveLength(1);
  musicas.forEach((m) => expect(m.loadVideoById).not.toHaveBeenCalled());
});

it("nunca fala por cima do vocal: se a fala passa da posição de corte, é parada", async () => {
  mocks.proxima.mockResolvedValueOnce(bloco(30));
  await iniciar();
  await avancar(50);
  act(() => musicas[0].pronto());
  await act(async () => { musicas[0].tocando(); });
  posicao = 2.1;
  await avancar(300);
  expect(tocadas()).toHaveLength(1);

  // a fala "travou" no ar e a música chegou perto do vocal (30 s - 0,4 s)
  posicao = 29.7;
  await avancar(400);
  expect(tocadas()[0].pausada).toBe(true);
});

it("música com erro antes de ficar audível: a fala não se perde e toca antes da substituta", async () => {
  mocks.proxima.mockResolvedValueOnce(bloco(30));
  await iniciar();
  await avancar(50);
  act(() => musicas[0].pronto());

  await act(async () => { musicas[0].falhar(150); });
  await avancar(50);
  // fala inteira (fluxo normal) e só depois a substituta
  expect(tocadas()).toHaveLength(1);
  expect(musicas[0].loadVideoById).toHaveBeenLastCalledWith({ videoId: "musica-1", startSeconds: 0 });
  await act(async () => { tocadas()[0].terminar(); });
  await avancar(50);
  expect(musicas[0].loadVideoById).toHaveBeenLastCalledWith({ videoId: "musica-2", startSeconds: 0 });
});

it("música pulada no meio da fala sobre a introdução: a fala também para", async () => {
  mocks.proxima.mockResolvedValueOnce(bloco(30));
  await iniciar();
  await avancar(50);
  act(() => musicas[0].pronto());
  await act(async () => { musicas[0].tocando(); });
  posicao = 2.1;
  await avancar(300);
  expect(tocadas()).toHaveLength(1);

  await act(async () => { musicas[0].terminar(); });
  await avancar(400);
  expect(tocadas()[0].pausada).toBe(true);
});
