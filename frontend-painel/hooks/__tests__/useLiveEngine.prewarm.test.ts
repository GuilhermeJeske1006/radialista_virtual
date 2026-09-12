import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { useLiveEngine } from "../useLiveEngine";
import { PROGRAMA_VAZIO } from "../../lib/types";

// Cobre o fast-path do preparo antecipado feito pelo backend (ver GET
// .../programas/:id/preparo e app.live.prewarm no backend): quando o primeiro bloco da sessao
// ja veio pronto (LLM+TTS resolvidos uns segundos antes do horario_inicio, ver ANTECEDENCIA_
// PREPARO_SEGUNDOS/janela de 90s), o painel deve usa-lo direto, sem chamar /proxima nem /tts
// pra esse bloco -- e' exatamente o que resolve o inicio pontual quando ninguem abriu o painel
// com antecedencia suficiente pro prefetch client-side de FilaPreparo rodar sozinho.

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
  constructor(public src: string) { players.push(this); }
  terminar() { this.ended = true; this.onended?.(); }
}

const segmento = (fala: string, extra = {}) => ({
  tipo: "comentario", fala, criado_em: new Date().toISOString(),
  audio_status: "pendente", tom: "calmo", pausa_antes_ms: 0, ...extra,
});

const PREPARO_URL = "/live/1/programas/1/preparo";

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
    if (path === PREPARO_URL) return Promise.resolve({ disponivel: false });
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
  vi.stubGlobal("atob", (b64: string) => Buffer.from(b64, "base64").toString("binary"));
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

it("usa o preparo antecipado do backend pro primeiro bloco, sem chamar /proxima nem /tts pra ele", async () => {
  mocks.api.mockImplementation((path: string) => {
    if (path === "/config/radialistas") return Promise.resolve([{ id: 1, nome_locutor: "Ana", timezone: "UTC" }]);
    if (path === "/config/radialistas/1/programas") return Promise.resolve([
      { ...PROGRAMA_VAZIO, id: 1, radio_config_id: 1, ativo: false },
    ]);
    if (path === "/config/radio") return Promise.resolve({});
    if (path === PREPARO_URL) return Promise.resolve({
      disponivel: true,
      tipo: "abertura",
      fala: "Bom dia, radio!",
      criado_em: new Date().toISOString(),
      audio_status: "pronto",
      audio_base64: Buffer.from("audio-pronto").toString("base64"),
      tom: "calmo",
      pausa_antes_ms: 0,
    });
    return Promise.reject(new Error("Sem cama musical neste teste"));
  });
  // segundo item da fila (total_falas=1) segue o fluxo normal
  mocks.proxima.mockResolvedValueOnce(segmento("Segunda"));
  mocks.tts.mockResolvedValueOnce(new Blob(["segunda"]));

  const { result } = await iniciar();

  expect(result.current.falasPrograma[0].fala).toBe("Bom dia, radio!");
  expect(players[0]?.src).toBe("blob:1");
  // so' a chamada do segundo bloco (nunca com total_falas=0) foi feita
  const pedidos = mocks.proxima.mock.calls.map(([, opcoes]) => JSON.parse(opcoes.body));
  expect(pedidos.every((p) => p.total_falas !== 0)).toBe(true);
  expect(mocks.tts).toHaveBeenCalledTimes(1);
});

it("cai no /proxima normal quando o preparo antecipado nao esta disponivel", async () => {
  mocks.proxima
    .mockResolvedValueOnce(segmento("Primeira"))
    .mockResolvedValueOnce(segmento("Segunda"))
    .mockResolvedValueOnce(segmento("Terceira"));
  mocks.tts
    .mockResolvedValueOnce(new Blob(["primeira"]))
    .mockResolvedValueOnce(new Blob(["segunda"]))
    .mockResolvedValueOnce(new Blob(["terceira"]));

  const { result } = await iniciar();

  expect(result.current.falasPrograma[0].fala).toBe("Primeira");
  const pedidos = mocks.proxima.mock.calls.map(([, opcoes]) => JSON.parse(opcoes.body));
  expect(pedidos.map((p) => p.total_falas)).toEqual([0, 1, 2]);
});
