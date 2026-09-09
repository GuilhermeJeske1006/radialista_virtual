import { act, renderHook, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { useLiveEngine } from "../useLiveEngine";
import { PROGRAMA_VAZIO } from "../../lib/types";

const mocks = vi.hoisted(() => ({ api: vi.fn(), proxima: vi.fn(), tts: vi.fn(), audio: vi.fn() }));
vi.mock("../../lib/api", () => ({
  apiFetch: mocks.api,
  apiFetchComTimeout: mocks.proxima,
  apiFetchBlob: mocks.tts,
  apiFetchBlobComTimeout: mocks.tts,
  ApiError: class extends Error {},
}));
vi.mock("../../lib/radialistas", () => ({ setRadialistaAtualId: vi.fn() }));

beforeEach(() => {
  vi.useFakeTimers();
  vi.clearAllMocks();
  mocks.api.mockImplementation((path: string) => {
    if (path === "/config/radialistas") return Promise.resolve([{ id: 1, nome_locutor: "Ana", timezone: "UTC" }]);
    if (path === "/config/radialistas/1/programas") return Promise.resolve([
      { ...PROGRAMA_VAZIO, id: 1, radio_config_id: 1, ativo: false, perfil_programacao: "musical_companhia" },
    ]);
    if (path === "/config/radio") return Promise.resolve({});
    return Promise.reject(new Error("Sem cama musical neste teste"));
  });
  vi.stubGlobal("Audio", class { constructor() { mocks.audio(); } });
  vi.stubGlobal("YT", { Player: class {} });
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: vi.fn(() => "blob:teste"), revokeObjectURL: vi.fn() }));
  mocks.proxima.mockImplementation(() => new Promise(() => {}));
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

async function iniciar(resposta: Record<string, unknown>) {
  mocks.proxima.mockResolvedValueOnce({ criado_em: new Date().toISOString(), ...resposta });
  const hook = renderHook(() => useLiveEngine());
  await act(async () => {});
  act(() => hook.result.current.selecionarPrograma(hook.result.current.programasTodos[0]));
  await act(async () => { hook.result.current.iniciarPrograma(); });
  return hook;
}

it("música sem locução não solicita TTS e a pausa pode ser cancelada", async () => {
  const { result } = await iniciar({ tipo: "musica", fala: "", video_id: "faixa123", audio_status: "nao_aplicavel", pausa_antes_ms: 800 });
  expect(result.current.totalFalas).toBe(1);
  expect(mocks.tts).not.toHaveBeenCalled();
  act(() => result.current.pausarPrograma());
  await act(async () => { await vi.advanceTimersByTimeAsync(1500); });
  expect(mocks.audio).not.toHaveBeenCalled();
  expect(result.current.programaAtivo).toBe(false);
});

it("pausar durante a espera impede que uma fala pronta comece depois", async () => {
  const { result } = await iniciar({ tipo: "retomada", fala: "Boa companhia!", audio_status: "pronto", audio_base64: btoa("mp3"), pausa_antes_ms: 800 });
  expect(result.current.totalFalas).toBe(1);
  await act(async () => { await vi.advanceTimersByTimeAsync(300); });
  act(() => result.current.pausarPrograma());
  await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
  expect(mocks.audio).not.toHaveBeenCalled();
  expect(mocks.tts).not.toHaveBeenCalled();
});
