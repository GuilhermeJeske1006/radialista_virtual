import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { useLiveEngine } from "../useLiveEngine";
import { PROGRAMA_VAZIO } from "../../lib/types";

const mocks = vi.hoisted(() => ({ api: vi.fn(), proxima: vi.fn(), tts: vi.fn(), arquivo: vi.fn() }));
vi.mock("../../lib/api", () => ({
  apiFetch: mocks.api, apiFetchComTimeout: mocks.proxima,
  apiFetchBlob: mocks.arquivo, apiFetchBlobComTimeout: mocks.tts,
  ApiError: class extends Error {},
}));
vi.mock("../../lib/radialistas", () => ({ setRadialistaAtualId: vi.fn() }));

function pendente<T>() {
  let resolve!: (valor: T) => void;
  const promise = new Promise<T>((r) => { resolve = r; });
  return { promise, resolve };
}

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
const musicas: MusicaTeste[] = [];
class MusicaTeste {
  constructor(_id: string, public config: { events: { onStateChange: (evento: { data: number }) => void } }) {
    musicas.push(this);
  }
  stopVideo() {}
  destroy() {}
  terminar() { this.config.events.onStateChange({ data: 0 }); }
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.resetAllMocks();
  players.length = 0;
  musicas.length = 0;
  mocks.api.mockImplementation((path: string) => {
    if (path === "/config/radialistas") return Promise.resolve([{ id: 1, nome_locutor: "Ana", timezone: "UTC" }]);
    if (path === "/config/radialistas/1/programas") return Promise.resolve([
      { ...PROGRAMA_VAZIO, id: 1, radio_config_id: 1, ativo: false },
      { ...PROGRAMA_VAZIO, id: 2, radio_config_id: 1, ativo: false },
    ]);
    if (path === "/config/radio") return Promise.resolve({});
    return Promise.reject(new Error("Sem cama musical neste teste"));
  });
  mocks.proxima.mockImplementation(() => new Promise(() => {}));
  mocks.tts.mockImplementation(() => new Promise(() => {}));
  mocks.arquivo.mockResolvedValue(new Blob(["vinheta"]));
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
});

const segmento = (fala: string, extra = {}) => ({
  tipo: "comentario", fala, criado_em: new Date().toISOString(),
  audio_status: "pendente", tom: "calmo", pausa_antes_ms: 0, ...extra,
});

async function iniciar() {
  const hook = renderHook(() => useLiveEngine());
  await act(async () => {});
  act(() => hook.result.current.selecionarPrograma(hook.result.current.programasTodos[0]));
  await act(async () => { hook.result.current.iniciarPrograma(); });
  return hook;
}

it("prepara texto e voz seguintes antes de acabar o primeiro TTS e reaproveita o áudio pronto", async () => {
  const primeiroAudio = pendente<Blob>();
  mocks.proxima.mockResolvedValueOnce(segmento("Primeira")).mockResolvedValueOnce(segmento("Segunda"));
  mocks.tts.mockReturnValueOnce(primeiroAudio.promise).mockResolvedValueOnce(new Blob(["segunda"]));
  const { result } = await iniciar();

  expect(players).toHaveLength(0);
  expect(mocks.tts).toHaveBeenCalledTimes(2);
  expect(mocks.proxima).toHaveBeenCalledTimes(3);
  const pedidos = mocks.proxima.mock.calls.map(([, opcoes]) => JSON.parse(opcoes.body));
  expect(pedidos.map((p) => p.total_falas)).toEqual([0, 1, 2]);
  expect(pedidos.every((p) => p.incluir_audio === false)).toBe(true);
  expect(pedidos[2].historico).toEqual(["comentario: Primeira", "comentario: Segunda"]);
  expect(JSON.parse(mocks.tts.mock.calls[0][1].body)).toMatchObject({ tom: "calmo", perfil_pos_producao: "radio_fm" });

  await act(async () => { primeiroAudio.resolve(new Blob(["primeira"])); });
  expect(players[0].src).toBe("blob:2"); // A segunda voz ficou pronta primeiro.
  expect(result.current.falasPrograma[0].fala).toBe("Primeira");
  await act(async () => { players[0].terminar(); await vi.advanceTimersByTimeAsync(1); });
  expect(players[1].src).toBe("blob:1");
  expect(result.current.falasPrograma[0].fala).toBe("Segunda");
  expect(mocks.tts).toHaveBeenCalledTimes(2);
});

it.each(["musica", "vinheta"])("finaliza a próxima voz enquanto %s está tocando", async (tipo) => {
  const proximoTexto = pendente<ReturnType<typeof segmento>>();
  const extra = tipo === "musica"
    ? { tipo, fala: "", video_id: "musica-1", titulo_musica: "Canção" }
    : { tipo, fala: "Vinheta", vinheta_id: 7 };
  mocks.proxima.mockResolvedValueOnce(segmento("", extra)).mockReturnValueOnce(proximoTexto.promise);
  mocks.tts.mockResolvedValueOnce(new Blob(["voz seguinte"]));
  const { result } = await iniciar();
  expect(tipo === "musica" ? musicas : players).toHaveLength(1);

  await act(async () => { proximoTexto.resolve(segmento("Depois do áudio")); });
  expect(mocks.tts).toHaveBeenCalledTimes(1);
  expect(URL.createObjectURL).toHaveBeenCalledTimes(tipo === "musica" ? 1 : 2);
  expect(result.current.totalFalas).toBe(1);
  await act(async () => {
    if (tipo === "musica") musicas[0].terminar(); else players[0].terminar();
    await vi.advanceTimersByTimeAsync(1);
  });
  expect(result.current.falasPrograma[0].fala).toBe("Depois do áudio");
  expect(mocks.tts).toHaveBeenCalledTimes(1);
});

it("prepara a fala depois de duas vinhetas enquanto a música anterior ainda toca", async () => {
  const primeiraVinheta = pendente<Blob>();
  const segundaVinheta = pendente<Blob>();
  mocks.proxima
    .mockResolvedValueOnce(segmento("", { tipo: "musica", video_id: "musica-1" }))
    .mockResolvedValueOnce(segmento("Vinheta 1", { tipo: "vinheta", vinheta_id: 7 }))
    .mockResolvedValueOnce(segmento("Vinheta 2", { tipo: "vinheta", vinheta_id: 8 }))
    .mockResolvedValueOnce(segmento("Fala depois das vinhetas"));
  mocks.arquivo.mockReturnValueOnce(primeiraVinheta.promise).mockReturnValueOnce(segundaVinheta.promise);
  mocks.tts.mockResolvedValueOnce(new Blob(["fala pronta"]));
  const { result } = await iniciar();

  expect(musicas).toHaveLength(1);
  expect(players).toHaveLength(0);
  expect(mocks.tts).toHaveBeenCalledTimes(1);
  expect(JSON.parse(mocks.tts.mock.calls[0][1].body).texto).toBe("Fala depois das vinhetas");
  expect(URL.createObjectURL).toHaveBeenCalledTimes(1);
  const contexto = JSON.parse(mocks.proxima.mock.calls[3][1].body);
  expect(contexto.total_falas).toBe(3);
  expect(contexto.historico.slice(-2)).toEqual(["vinheta: Vinheta 1", "vinheta: Vinheta 2"]);

  await act(async () => {
    primeiraVinheta.resolve(new Blob(["vinheta 1"]));
    segundaVinheta.resolve(new Blob(["vinheta 2"]));
  });
  await act(async () => { musicas[0].terminar(); await vi.advanceTimersByTimeAsync(1); });
  expect(result.current.falasPrograma[0].fala).toBe("Vinheta 1");
  await act(async () => { players[0].terminar(); await vi.advanceTimersByTimeAsync(1); });
  expect(result.current.falasPrograma[0].fala).toBe("Vinheta 2");
  await act(async () => { players[1].terminar(); await vi.advanceTimersByTimeAsync(1); });
  expect(result.current.falasPrograma[0].fala).toBe("Fala depois das vinhetas");
  expect(players[2].src).toBe("blob:1");
  expect(mocks.tts).toHaveBeenCalledTimes(1);
});

it("pausar e selecionar outro programa descarta texto atrasado sem sintetizar na nova seleção", async () => {
  const antigo = pendente<ReturnType<typeof segmento>>();
  mocks.proxima.mockReturnValueOnce(antigo.promise);
  const { result } = await iniciar();
  act(() => result.current.selecionarPrograma(result.current.programasTodos[1]));
  await act(async () => { result.current.iniciarPrograma(); });
  expect(mocks.proxima.mock.calls[1][0]).toContain("/programas/2/proxima");
  await act(async () => { antigo.resolve(segmento("Fala do programa anterior")); });
  expect(mocks.tts).not.toHaveBeenCalled();
  expect(players).toHaveLength(0);
  expect(result.current.gerandoFala).toBe(true);
});

it("pular usa a próxima voz já preparada sem repetir a síntese", async () => {
  mocks.proxima.mockResolvedValueOnce(segmento("Primeira")).mockResolvedValueOnce(segmento("Segunda"));
  mocks.tts.mockResolvedValue(new Blob(["audio"]));
  const { result } = await iniciar();
  expect(players).toHaveLength(1);
  await act(async () => { result.current.pularFala(); });
  expect(players).toHaveLength(2);
  expect(result.current.falasPrograma[0].fala).toBe("Segunda");
  expect(mocks.tts).toHaveBeenCalledTimes(2);
});

it("retomar após pausar um TTS lento não toca a voz da execução anterior", async () => {
  const vozAntiga = pendente<Blob>();
  mocks.proxima.mockResolvedValueOnce(segmento("Antiga"));
  mocks.tts.mockReturnValueOnce(vozAntiga.promise);
  const { result } = await iniciar();
  act(() => result.current.pausarPrograma());
  mocks.proxima.mockResolvedValueOnce(segmento("Nova"));
  mocks.tts.mockResolvedValueOnce(new Blob(["nova"]));
  await act(async () => { result.current.iniciarPrograma(); });
  expect(result.current.falasPrograma[0].fala).toBe("Nova");
  expect(players).toHaveLength(1);
  await act(async () => { vozAntiga.resolve(new Blob(["antiga"])); });
  expect(players).toHaveLength(1);
  expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:2");
  expect(result.current.programaAtivo).toBe(true);
});

it("diálogo só entra com todas as vozes prontas e já libera a escrita do bloco seguinte", async () => {
  const segundaVoz = pendente<Blob>();
  mocks.proxima.mockResolvedValueOnce(segmento("Ana e Bia", { falas: [
    { radio_config_id: 1, nome_locutor: "Ana", voz_id: "ana", texto: "Bom dia, Bia!" },
    { radio_config_id: 2, nome_locutor: "Bia", voz_id: "bia", texto: "Bom dia, Ana!" },
  ] }));
  mocks.tts.mockResolvedValueOnce(new Blob(["ana"])).mockReturnValueOnce(segundaVoz.promise);
  await iniciar();
  expect(mocks.proxima).toHaveBeenCalledTimes(2);
  expect(mocks.tts.mock.calls.map(([, opcoes]) => JSON.parse(opcoes.body).voz_id)).toEqual(["ana", "bia"]);
  expect(players).toHaveLength(0);
  await act(async () => { segundaVoz.resolve(new Blob(["bia"])); });
  expect(players).toHaveLength(1);
  await act(async () => { players[0].terminar(); });
  expect(players).toHaveLength(2);
  expect(mocks.tts).toHaveBeenCalledTimes(2);
});

it("vinheta manual invalida a fila antiga e prepara a nova sequência durante sua reprodução", async () => {
  const textoAntigo = pendente<ReturnType<typeof segmento>>();
  mocks.proxima.mockResolvedValueOnce(segmento("Primeira")).mockReturnValueOnce(textoAntigo.promise);
  mocks.tts.mockResolvedValue(new Blob(["audio"]));
  const { result } = await iniciar();
  mocks.proxima.mockResolvedValueOnce(segmento("Depois da vinheta"));
  await act(async () => { void result.current.inserirNaTransmissao({ id: 8, nome: "Identificação" }); });
  expect(players).toHaveLength(2);
  expect(result.current.falasPrograma[0].origem).toBe("manual");
  expect(mocks.tts).toHaveBeenCalledTimes(2);
  const contextoNovo = JSON.parse(mocks.proxima.mock.calls[2][1].body);
  expect(contextoNovo.ultima_fala).toBe("Identificação");
  await act(async () => { textoAntigo.resolve(segmento("Não deve ir ao ar")); });
  expect(mocks.tts).toHaveBeenCalledTimes(2);
  await act(async () => { players[1].terminar(); await vi.advanceTimersByTimeAsync(1); });
  expect(result.current.falasPrograma[0].fala).toBe("Depois da vinheta");
});
