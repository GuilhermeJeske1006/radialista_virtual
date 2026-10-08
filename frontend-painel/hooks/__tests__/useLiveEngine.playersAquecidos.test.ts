import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { useLiveEngine } from "../useLiveEngine";
import { PROGRAMA_VAZIO } from "../../lib/types";

// Fundo e música do bloco com o painel em segundo plano (ver aquecerPlayer em useLiveEngine.ts):
// o Chrome não carrega mídia de um iframe que nunca tocou nada enquanto a página está oculta,
// então cada player do YouTube é criado e "aquecido" uma vez com a página visível, e a
// transmissão só troca a faixa nele (loadVideoById) -- nunca cria iframe novo no meio dela.

const mocks = vi.hoisted(() => ({ api: vi.fn(), proxima: vi.fn(), tts: vi.fn(), arquivo: vi.fn() }));
vi.mock("../../lib/api", () => ({
  apiFetch: mocks.api, apiFetchComTimeout: mocks.proxima,
  apiFetchBlob: mocks.arquivo, apiFetchBlobComTimeout: mocks.tts,
  ApiError: class extends Error {},
}));
vi.mock("../../lib/radialistas", () => ({ setRadialistaAtualId: vi.fn() }));

class AudioTeste {
  volume = 0;
  muted = false;
  addEventListener() {}
  // sondagem de autoplay (silencio com som): so' passa se a pagina ja' "pode" tocar som
  play = vi.fn(() => (interagiu ? Promise.resolve() : Promise.reject(new Error("NotAllowedError"))));
  pause() {}
  constructor(public src: string) {}
}

type EventosYT = {
  onReady: (e: { target: PlayerTeste }) => void;
  onStateChange: (e: { data: number; target: PlayerTeste }) => void;
  onError: (e: { data: number }) => void;
};
const criados: PlayerTeste[] = [];
class PlayerTeste {
  playVideo = vi.fn();
  pauseVideo = vi.fn();
  stopVideo = vi.fn();
  mute = vi.fn();
  unMute = vi.fn();
  setVolume = vi.fn();
  loadVideoById = vi.fn();
  seekTo = vi.fn();
  destroy = vi.fn();
  getVolume() { return 0; }
  getCurrentTime() { return 0; }
  constructor(public id: string, public config: { videoId: string; events: EventosYT }) { criados.push(this); }
  pronto() { this.config.events.onReady({ target: this }); }
  estado(data: number) { this.config.events.onStateChange({ data, target: this }); }
  falhar(codigo: number) { this.config.events.onError({ data: codigo }); }
}
const doId = (id: string) => criados.filter((p) => p.id === id);
const fundo = () => doId("yt-bg-player");
const musica = () => doId("yt-live-player");

const PLAYING = 1;
const ENDED = 0;
let interagiu = false;
let oculta = false;

const blocoMusica = (videoId: string) => ({
  tipo: "musica", fala: "", video_id: videoId, titulo_musica: `Canção ${videoId}`,
  criado_em: new Date().toISOString(), audio_status: "nao_aplicavel", pausa_antes_ms: 0,
});

beforeEach(() => {
  vi.useFakeTimers();
  vi.resetAllMocks();
  criados.length = 0;
  interagiu = false;
  oculta = false;
  vi.spyOn(document, "hidden", "get").mockImplementation(() => oculta);
  Object.defineProperty(navigator, "userActivation", {
    configurable: true, get: () => ({ hasBeenActive: interagiu }),
  });
  document.body.innerHTML = '<div id="yt-players-root"><div id="yt-live-player"></div><div id="yt-bg-player"></div></div>';
  mocks.api.mockImplementation((path: string) => {
    if (path === "/config/radialistas") return Promise.resolve([{ id: 1, nome_locutor: "Ana", timezone: "UTC" }]);
    if (path === "/config/radialistas/1/programas") return Promise.resolve([
      { ...PROGRAMA_VAZIO, id: 1, radio_config_id: 1, ativo: false },
    ]);
    if (path === "/config/radio") return Promise.resolve({});
    if (path.endsWith("/preparo")) return Promise.resolve({ disponivel: false });
    if (path.endsWith("/musica-fundo")) return Promise.resolve({ video_id: "fundo-1", titulo: "Cama", inicio_segundos: 5 });
    if (path.endsWith("/musica-substituta")) return Promise.resolve({ video_id: "musica-sub", titulo: "Outra", inicio_segundos: 0 });
    return Promise.reject(new Error("nao usado neste teste"));
  });
  mocks.proxima.mockImplementation(() => new Promise(() => {}));
  mocks.tts.mockImplementation(() => new Promise(() => {}));
  vi.stubGlobal("Audio", AudioTeste);
  vi.stubGlobal("YT", { Player: PlayerTeste, PlayerState: { ENDED, PLAYING } });
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  delete (navigator as { userActivation?: unknown }).userActivation;
  document.body.innerHTML = "";
});

const ultimaChamada = (fn: { mock: { invocationCallOrder: number[] } }) => fn.mock.invocationCallOrder.at(-1) ?? -1;

async function montarAquecido() {
  const hook = renderHook(() => useLiveEngine());
  await act(async () => {});
  expect(criados).toHaveLength(2);
  for (const player of criados) {
    act(() => player.pronto());
    act(() => player.estado(PLAYING));
  }
  return hook;
}

async function iniciar(hook: Awaited<ReturnType<typeof montarAquecido>>) {
  act(() => hook.result.current.selecionarPrograma(hook.result.current.programasTodos[0]));
  await act(async () => { hook.result.current.iniciarPrograma(); });
}

it("aquece fundo e música com a página visível: toca mudo um instante e pausa", async () => {
  await montarAquecido();

  for (const player of [fundo()[0], musica()[0]]) {
    expect(player.config.videoId).toBe("M7lc1UVf-VE");
    expect(player.playVideo).toHaveBeenCalledTimes(1);
    expect(player.pauseVideo).toHaveBeenCalledTimes(1);
    expect(player.loadVideoById).not.toHaveBeenCalled();
  }
});

it("página oculta na montagem: só aquece quando ela aparecer", async () => {
  oculta = true;
  renderHook(() => useLiveEngine());
  await act(async () => {});
  expect(criados).toHaveLength(0);

  oculta = false;
  act(() => { document.dispatchEvent(new Event("visibilitychange")); });
  expect(fundo()).toHaveLength(1);
  expect(musica()).toHaveLength(1);
});

it("início com a página oculta reusa o fundo aquecido e já carrega a faixa com som", async () => {
  interagiu = true;
  const hook = await montarAquecido();
  oculta = true;
  await iniciar(hook);

  const [player] = fundo();
  expect(fundo()).toHaveLength(1);
  expect(player.loadVideoById).toHaveBeenCalledWith({ videoId: "fundo-1", startSeconds: 5 });
  // desmutado ANTES de carregar: midia muda com a pagina oculta o Chrome pausa
  expect(ultimaChamada(player.unMute)).toBeLessThan(ultimaChamada(player.loadVideoById));
  expect(ultimaChamada(player.mute)).toBeLessThan(ultimaChamada(player.unMute));
  // a faixa da transmissao nao e' pausada como o aquecimento
  act(() => player.estado(PLAYING));
  expect(player.pauseVideo).toHaveBeenCalledTimes(1);
});

it("sem interação: fundo carrega mudo e só desmuta no primeiro clique", async () => {
  const hook = await montarAquecido();
  await iniciar(hook);

  const [player] = fundo();
  expect(ultimaChamada(player.mute)).toBeLessThan(ultimaChamada(player.loadVideoById));
  expect(player.unMute).not.toHaveBeenCalled();
  act(() => player.estado(PLAYING));
  expect(hook.result.current.audioBloqueado).toBe(true);

  interagiu = true;
  await act(async () => { document.body.click(); });
  expect(player.unMute).toHaveBeenCalledTimes(1);
});

it("faixa de fundo terminou: volta pro ponto de início em loop", async () => {
  interagiu = true;
  const hook = await montarAquecido();
  await iniciar(hook);

  const [player] = fundo();
  act(() => player.estado(ENDED));
  expect(player.seekTo).toHaveBeenCalledWith(5, true);
  expect(player.playVideo).toHaveBeenCalledTimes(2);
});

it("pausar para a cama mas mantém o iframe aquecido pro próximo programa", async () => {
  interagiu = true;
  const hook = await montarAquecido();
  await iniciar(hook);

  act(() => hook.result.current.pausarPrograma());
  const [player] = fundo();
  expect(player.stopVideo).toHaveBeenCalled();
  expect(player.destroy).not.toHaveBeenCalled();

  oculta = true;
  await act(async () => { hook.result.current.iniciarPrograma(); });
  expect(fundo()).toHaveLength(1);
  expect(player.loadVideoById).toHaveBeenCalledTimes(2);
});

it("início antes do fundo ficar pronto: aplica a faixa no onReady", async () => {
  interagiu = true;
  const hook = renderHook(() => useLiveEngine());
  await act(async () => {});
  await iniciar(hook);
  const [player] = fundo();
  expect(player.loadVideoById).not.toHaveBeenCalled();

  act(() => player.pronto());
  expect(player.loadVideoById).toHaveBeenCalledWith({ videoId: "fundo-1", startSeconds: 5 });
  // com a transmissao ja' rolando, o onReady nao dispara o aquecimento por cima da faixa
  expect(player.playVideo).not.toHaveBeenCalled();
});

it("músicas do bloco com a página oculta tocam no player aquecido, sem iframe novo", async () => {
  interagiu = true;
  mocks.proxima
    .mockResolvedValueOnce(blocoMusica("musica-1"))
    .mockResolvedValueOnce(blocoMusica("musica-2"))
    .mockImplementation(() => new Promise(() => {}));
  const hook = await montarAquecido();
  oculta = true;
  await iniciar(hook);

  const [player] = musica();
  expect(player.loadVideoById).toHaveBeenLastCalledWith({ videoId: "musica-1", startSeconds: 0 });
  expect(ultimaChamada(player.unMute)).toBeLessThan(ultimaChamada(player.loadVideoById));
  act(() => player.estado(PLAYING));
  expect(player.pauseVideo).toHaveBeenCalledTimes(1);

  await act(async () => { player.estado(ENDED); await vi.advanceTimersByTimeAsync(1); });
  expect(player.stopVideo).toHaveBeenCalled();
  expect(musica()).toHaveLength(1);
  expect(player.loadVideoById).toHaveBeenLastCalledWith({ videoId: "musica-2", startSeconds: 0 });
});

it("página oculta com o player aquecido: vigia de início não espera a aba voltar", async () => {
  interagiu = true;
  mocks.proxima.mockResolvedValueOnce(blocoMusica("musica-1")).mockImplementation(() => new Promise(() => {}));
  const hook = await montarAquecido();
  oculta = true;
  await iniciar(hook);

  await act(async () => { await vi.advanceTimersByTimeAsync(24000); });
  const chamada = mocks.api.mock.calls.find(([path]) => String(path).endsWith("/musica-substituta"));
  expect(JSON.parse(String(chamada?.[1]?.body)).motivo).toBe("nao_iniciou");
  expect(musica()[0].loadVideoById).toHaveBeenLastCalledWith({ videoId: "musica-sub", startSeconds: 0 });
});

it("erro do aquecimento não conta como erro de música", async () => {
  mocks.proxima.mockResolvedValueOnce(blocoMusica("musica-1")).mockImplementation(() => new Promise(() => {}));
  const erro = vi.spyOn(console, "error").mockImplementation(() => {});
  renderHook(() => useLiveEngine());
  await act(async () => {});

  act(() => musica()[0].falhar(150));
  expect(erro).toHaveBeenCalledWith("Erro ao aquecer o player do YouTube:", "yt-live-player", 150);
  expect(mocks.api.mock.calls.some(([path]) => String(path).endsWith("/musica-substituta"))).toBe(false);
});
