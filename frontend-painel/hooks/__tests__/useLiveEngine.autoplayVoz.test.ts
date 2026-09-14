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
  addEventListener(evento: string, cb: () => void) {
    (this.ouvintes[evento] ??= []).push(cb);
  }
  play = vi.fn(() => Promise.resolve());
  pause() {}
  constructor(public src: string) { players.push(this); }
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
});
