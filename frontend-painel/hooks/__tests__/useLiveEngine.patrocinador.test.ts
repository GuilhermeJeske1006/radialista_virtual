import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { useLiveEngine } from "../useLiveEngine";
import { PROGRAMA_VAZIO } from "../../lib/types";

// Patrocinador (texto ou audio pre-gravado) e' conteudo fixo por contrato: um spot de radio de
// verdade e' sempre a MESMA gravacao. O audio (inclusive a sintese TTS do texto) agora e' servido
// e cacheado pelo backend num unico endpoint (ver obter_audio_patrocinador em
// app/patrocinadores/router.py) -- o front so' busca esse arquivo, sem mandar texto/tom/voz_id
// pra' sintetizar de novo a cada exibicao.

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
  constructor(public src: string) { players.push(this); }
  disparar(evento: string) {
    this.ouvintes[evento]?.forEach((cb) => cb());
  }
  terminar() { this.ended = true; this.onended?.(); }
}

const segmento = (extra = {}) => ({
  tipo: "patrocinador", fala: "Compre na loja X", criado_em: new Date().toISOString(),
  audio_status: "nao_aplicavel", pausa_antes_ms: 0, ...extra,
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
  mocks.arquivo.mockResolvedValue(new Blob(["anuncio"]));
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

it("busca o audio do patrocinador no endpoint dedicado, com a voz do radialista no ar", async () => {
  mocks.proxima.mockResolvedValueOnce(segmento({ patrocinador_id: 7 }));
  await iniciar();

  expect(mocks.arquivo).toHaveBeenCalledWith("/patrocinadores/7/audio?radialista_id=1");
  // conteudo de patrocinador e' fixo por contrato -- nao chama /tts pra sintetizar de novo.
  expect(mocks.tts).not.toHaveBeenCalled();
  expect(players).toHaveLength(1);
});

it("patrocinador com audio pre-gravado usa o mesmo endpoint, mesmo com fala vazia", async () => {
  mocks.proxima.mockResolvedValueOnce(segmento({ patrocinador_id: 8, patrocinador_audio: true, fala: "" }));
  await iniciar();

  expect(mocks.arquivo).toHaveBeenCalledWith("/patrocinadores/8/audio?radialista_id=1");
  expect(players).toHaveLength(1);
});
