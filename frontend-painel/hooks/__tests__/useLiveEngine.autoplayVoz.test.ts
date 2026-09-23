import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { useLiveEngine } from "../useLiveEngine";
import { PROGRAMA_VAZIO } from "../../lib/types";

// Cobre a política de autoplay do navegador na voz do locutor (ver reproduzirAudioPreparado em
// useLiveEngine.ts): o áudio começa mudo (mute:1 é o único jeito de garantir que o autoplay
// passe sem gesto do usuário, ex. início agendado) e só deve desmutar depois do evento
// "playing" confirmar que a reprodução de fato começou -- desmutar assim que a Promise de
// play() resolve (só confirma que o pedido foi aceito) faz o Chrome cancelar o autoplay de
// volta pra pausado, deixando a fala muda pro resto da vida do elemento (o bug relatado:
// "o texto é processado mas a voz não").

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
  // sondagem de autoplay (silencio em data:) nao conta como fala tocada
  constructor(public src: string) { if (!src.startsWith("data:")) players.push(this); }
  disparar(evento: string) {
    this.ouvintes[evento]?.forEach((cb) => cb());
  }
  terminar() { this.ended = true; this.onended?.(); }
  errar() { this.onerror?.(); }
}

const segmento = (fala: string, extra = {}) => ({
  tipo: "comentario", fala, criado_em: new Date().toISOString(),
  audio_status: "pendente", tom: "calmo", pausa_antes_ms: 0, ...extra,
});

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
    return Promise.reject(new Error("Sem cama musical neste teste"));
  });
  mocks.proxima.mockImplementation(() => new Promise(() => {}));
  mocks.tts.mockImplementation(() => new Promise(() => {}));
  mocks.arquivo.mockResolvedValue(new Blob(["vinheta"]));
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

it("começa mudo e só desmuta quando o evento playing confirma reprodução real", async () => {
  mocks.proxima.mockResolvedValueOnce(segmento("Primeira"));
  mocks.tts.mockResolvedValueOnce(new Blob(["primeira"]));
  await iniciar();

  expect(players).toHaveLength(1);
  expect(players[0].play).toHaveBeenCalledTimes(1);
  // play() já resolveu (mock), mas sem o evento "playing" ainda não deve desmutar.
  expect(players[0].muted).toBe(true);

  await act(async () => { players[0].disparar("playing"); });
  expect(players[0].muted).toBe(false);
});

it("bloqueio silencioso (sem playing/ended/error) não trava a transmissão pra sempre", async () => {
  mocks.proxima.mockResolvedValueOnce(segmento("Primeira")).mockResolvedValueOnce(segmento("Segunda"));
  mocks.tts.mockResolvedValueOnce(new Blob(["primeira"])).mockResolvedValueOnce(new Blob(["segunda"]));
  const { result } = await iniciar();

  expect(players).toHaveLength(1);
  // nenhum evento disparado -- só a rede de segurança deve desbloquear.
  await act(async () => { await vi.advanceTimersByTimeAsync(3 * 60 * 1000); });

  expect(result.current.falhasAudioConsecutivas).toBeGreaterThan(0);
  expect(result.current.erro).toMatch(/Falha ao reproduzir/);
  // sem pausar explicitamente aqui, o audio antigo continuaria tocando por baixo do
  // próximo bloco -- é exatamente isso que soa como "uma fala por cima da outra".
  expect(players[0].paused).toBe(true);
});

it("onerror pausa o audio explicitamente, sem deixar ele tocando por baixo do próximo bloco", async () => {
  mocks.proxima.mockResolvedValueOnce(segmento("Primeira")).mockResolvedValueOnce(segmento("Segunda"));
  mocks.tts.mockResolvedValueOnce(new Blob(["primeira"])).mockResolvedValueOnce(new Blob(["segunda"]));
  await iniciar();

  expect(players).toHaveLength(1);
  expect(players[0].paused).toBe(false);

  await act(async () => { players[0].errar(); });

  expect(players[0].paused).toBe(true);
});

// Aba do ao vivo em segundo plano (operador em outra aba/janela minimizada): o navegador não roda
// requestAnimationFrame, e o fade de entrada (volume 0 -> 1) congelava em 0 -- a fala tocava
// inteira muda, com o texto no histórico e nenhum erro na tela.
it("aba oculta: fala sai no volume cheio mesmo sem requestAnimationFrame rodar", async () => {
  vi.stubGlobal("requestAnimationFrame", vi.fn(() => 0));
  vi.spyOn(document, "hidden", "get").mockReturnValue(true);
  mocks.proxima.mockResolvedValueOnce(segmento("Primeira"));
  mocks.tts.mockResolvedValueOnce(new Blob(["primeira"]));
  await iniciar();

  await act(async () => { players[0].disparar("playing"); });

  expect(players[0].muted).toBe(false);
  expect(players[0].volume).toBe(1);
});

it("aba sai de foco no meio do fade: timer de segurança completa o volume", async () => {
  // aba visivel quando o fade comeca, mas o rAF congela logo depois (aba foi pro fundo).
  vi.stubGlobal("requestAnimationFrame", vi.fn(() => 0));
  mocks.proxima.mockResolvedValueOnce(segmento("Primeira"));
  mocks.tts.mockResolvedValueOnce(new Blob(["primeira"]));
  await iniciar();

  await act(async () => { players[0].disparar("playing"); });
  expect(players[0].volume).toBe(0);

  await act(async () => { await vi.advanceTimersByTimeAsync(200); });
  expect(players[0].volume).toBe(1);
});

// Pagina aberta/recarregada e programa iniciado sem nenhum clique (ex.: agendamento): o Chrome
// rejeita o play() com NotAllowedError. A fala nao pode ser pulada -- espera o "Ativar som".
it("autoplay bloqueado sem interação: fala espera o 'Ativar som' em vez de ser pulada", async () => {
  mocks.proxima.mockResolvedValueOnce(segmento("Primeira"));
  mocks.tts.mockResolvedValueOnce(new Blob(["primeira"]));
  const bloqueio = Object.assign(new Error("user didn't interact"), { name: "NotAllowedError" });
  const play = vi.fn()
    .mockImplementationOnce(() => Promise.reject(bloqueio))
    .mockImplementation(() => Promise.resolve());
  vi.stubGlobal("Audio", class extends AudioTeste { play = this.src.startsWith("data:") ? vi.fn(() => Promise.reject(bloqueio)) : play; });
  const { result } = await iniciar();

  expect(result.current.audioBloqueado).toBe(true);
  expect(result.current.erro).toBe("");
  // nem a rede de seguranca de 3 min pode pular a fala enquanto espera o clique
  await act(async () => { await vi.advanceTimersByTimeAsync(5 * 60 * 1000); });
  expect(result.current.audioBloqueado).toBe(true);
  expect(result.current.falhasAudioConsecutivas).toBe(0);

  await act(async () => { result.current.liberarAudio(); });
  expect(play).toHaveBeenCalledTimes(2);
  expect(result.current.audioBloqueado).toBe(false);

  await act(async () => { players[0].disparar("playing"); players[0].terminar(); });
  expect(result.current.erro).toBe("");
});

it("outros erros de play() continuam pulando a fala com o motivo na tela", async () => {
  mocks.proxima.mockResolvedValueOnce(segmento("Primeira"));
  mocks.tts.mockResolvedValueOnce(new Blob(["primeira"]));
  const erro = Object.assign(new Error("formato"), { name: "NotSupportedError" });
  vi.stubGlobal("Audio", class extends AudioTeste { play = vi.fn(() => Promise.reject(erro)); });
  const { result } = await iniciar();

  expect(result.current.audioBloqueado).toBe(false);
  expect(result.current.erro).toMatch(/Motivo: play\(\) rejeitado: NotSupportedError/);
});
