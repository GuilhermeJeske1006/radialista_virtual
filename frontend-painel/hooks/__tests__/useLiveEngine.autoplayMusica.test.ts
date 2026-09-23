import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { useLiveEngine } from "../useLiveEngine";
import { PROGRAMA_VAZIO } from "../../lib/types";

// Página aberta/recarregada e programa iniciado sem nenhum clique (ex.: início agendado): o
// YouTube toca mudo (mute:1 sempre passa), mas unMute() sem interação faz o Chrome parar o vídeo.
// A faixa segue muda e o som só é liberado no primeiro clique/tecla na página ("Ativar som").

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
  addEventListener(evento: string, cb: () => void) { (this.ouvintes[evento] ??= []).push(cb); }
  play = vi.fn(() => { this.paused = false; return Promise.resolve(); });
  pause() { this.paused = true; }
  constructor(public src: string) {
    // sondagem de autoplay (silencio com som): so' passa se a pagina ja' "pode" tocar som
    if (src.startsWith("data:")) {
      this.play = vi.fn(() => (autoplayLiberado || interagiu ? Promise.resolve() : Promise.reject(new Error("NotAllowedError"))));
      return;
    }
    players.push(this);
  }
  disparar(evento: string) { this.ouvintes[evento]?.forEach((cb) => cb()); }
  terminar() { this.ended = true; this.onended?.(); }
}

type EventosYT = { onReady?: (e: { target: MusicaTeste }) => void; onStateChange: (e: { data: number; target: MusicaTeste }) => void };
const musicas: MusicaTeste[] = [];
class MusicaTeste {
  unMute = vi.fn();
  setVolume = vi.fn();
  playVideo = vi.fn();
  stopVideo() {}
  destroy() {}
  getVolume() { return 0; }
  constructor(_id: string, public config: { events: EventosYT }) { musicas.push(this); }
  tocando() { this.config.events.onStateChange({ data: 1, target: this }); }
  terminar() { this.config.events.onStateChange({ data: 0, target: this }); }
}

let interagiu = false;
let autoplayLiberado = false;

beforeEach(() => {
  vi.useFakeTimers();
  vi.resetAllMocks();
  players.length = 0;
  musicas.length = 0;
  interagiu = false;
  autoplayLiberado = false;
  Object.defineProperty(navigator, "userActivation", {
    configurable: true, get: () => ({ hasBeenActive: interagiu }),
  });
  mocks.api.mockImplementation((path: string) => {
    if (path === "/config/radialistas") return Promise.resolve([{ id: 1, nome_locutor: "Ana", timezone: "UTC" }]);
    if (path === "/config/radialistas/1/programas") return Promise.resolve([
      { ...PROGRAMA_VAZIO, id: 1, radio_config_id: 1, ativo: false },
    ]);
    if (path === "/config/radio") return Promise.resolve({});
    if (path.endsWith("/preparo")) return Promise.resolve({ disponivel: false });
    return Promise.reject(new Error("Sem cama musical neste teste"));
  });
  mocks.proxima.mockImplementation(() => new Promise(() => {}));
  mocks.tts.mockImplementation(() => new Promise(() => {}));
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

const musica = () => ({
  tipo: "musica", fala: "", video_id: "musica-1", titulo_musica: "Canção",
  criado_em: new Date().toISOString(), audio_status: "nao_aplicavel", pausa_antes_ms: 0,
});

async function iniciar() {
  const hook = renderHook(() => useLiveEngine());
  await act(async () => {});
  act(() => hook.result.current.selecionarPrograma(hook.result.current.programasTodos[0]));
  await act(async () => { hook.result.current.iniciarPrograma(); });
  return hook;
}

it("sem interação na página: música segue muda e desmuta no primeiro clique", async () => {
  mocks.proxima.mockResolvedValueOnce(musica());
  const { result } = await iniciar();

  expect(musicas).toHaveLength(1);
  await act(async () => { musicas[0].tocando(); });
  expect(musicas[0].unMute).not.toHaveBeenCalled();
  expect(result.current.audioBloqueado).toBe(true);

  // buffering -> playing de novo nao duplica o pendente nem desmuta sozinho
  await act(async () => { musicas[0].tocando(); });
  expect(musicas[0].unMute).not.toHaveBeenCalled();

  interagiu = true;
  await act(async () => { document.body.click(); });
  expect(musicas[0].unMute).toHaveBeenCalledTimes(1);
  expect(result.current.audioBloqueado).toBe(false);
});

it("com interação na página: música desmuta assim que começa a tocar", async () => {
  interagiu = true;
  mocks.proxima.mockResolvedValueOnce(musica());
  const { result } = await iniciar();

  await act(async () => { musicas[0].tocando(); });
  expect(musicas[0].unMute).toHaveBeenCalledTimes(1);
  expect(result.current.audioBloqueado).toBe(false);
});

it("música que acaba ainda bloqueada tira o aviso e não desmuta depois", async () => {
  mocks.proxima.mockResolvedValueOnce(musica());
  const { result } = await iniciar();

  await act(async () => { musicas[0].tocando(); });
  expect(result.current.audioBloqueado).toBe(true);
  await act(async () => { musicas[0].terminar(); });
  expect(result.current.audioBloqueado).toBe(false);

  await act(async () => { document.body.click(); });
  expect(musicas[0].unMute).not.toHaveBeenCalled();
});

it("fala bloqueada também é liberada por um clique em qualquer lugar da página", async () => {
  mocks.proxima.mockResolvedValueOnce({ ...musica(), tipo: "comentario", fala: "Olá", video_id: undefined });
  mocks.tts.mockResolvedValueOnce(new Blob(["ola"]));
  const bloqueio = Object.assign(new Error("user didn't interact"), { name: "NotAllowedError" });
  const play = vi.fn().mockImplementationOnce(() => Promise.reject(bloqueio)).mockImplementation(() => Promise.resolve());
  vi.stubGlobal("Audio", class extends AudioTeste { play = this.src.startsWith("data:") ? vi.fn(() => Promise.reject(bloqueio)) : play; });
  const { result } = await iniciar();

  expect(result.current.audioBloqueado).toBe(true);
  await act(async () => { document.dispatchEvent(new KeyboardEvent("keydown", { key: "a" })); });
  expect(play).toHaveBeenCalledTimes(2);
  expect(result.current.audioBloqueado).toBe(false);
});

// Navegador configurado pra liberar autoplay (flag/politica/permissao do site): a sondagem com
// silencio passa e tudo sai com som sozinho, sem clique nenhum -- o modo "painel so' aberto".
it("autoplay liberado no navegador: música sai com som sem nenhum clique", async () => {
  autoplayLiberado = true;
  mocks.proxima.mockResolvedValueOnce(musica());
  const { result } = await iniciar();

  await act(async () => { musicas[0].tocando(); });
  expect(musicas[0].unMute).toHaveBeenCalledTimes(1);
  expect(result.current.audioBloqueado).toBe(false);
});
