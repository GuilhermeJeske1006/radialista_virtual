import { afterEach, describe, expect, it, vi } from "vitest";
import { FALA_SOBRE_INTRO as C, medirDuracaoAudio, planejarFalaSobreIntro } from "../falaSobreIntro";

describe("planejarFalaSobreIntro", () => {
  it("introdução longa e fala curta: entra 2 s depois do início e corta antes do vocal", () => {
    // Rick Astley: vocal em 18,9 s; fala de 8 s cabe (2 + 8 + 1,5 <= 18,9)
    const plano = planejarFalaSobreIntro({ inicioSegundos: 0, inicioVocalSegundos: 18.9, duracaoFalaSegundos: 8 });
    expect(plano).toEqual({ posicaoEntradaS: 2, posicaoCorteS: 18.9 - C.CORTE_ANTES_VOCAL_S });
  });

  it("posições seguem o início do corte da faixa (vídeo com silêncio inicial cortado)", () => {
    const plano = planejarFalaSobreIntro({ inicioSegundos: 12, inicioVocalSegundos: 32, duracaoFalaSegundos: 6 });
    expect(plano?.posicaoEntradaS).toBe(14);
  });

  it("fala que não cabe antes do vocal (com margem) fica fora: locutor fala antes da música", () => {
    // 2 + 10 + 1,5 = 13,5 > 13
    expect(planejarFalaSobreIntro({ inicioSegundos: 0, inicioVocalSegundos: 13, duracaoFalaSegundos: 10 })).toBeNull();
    // no limite exato cabe
    expect(planejarFalaSobreIntro({ inicioSegundos: 0, inicioVocalSegundos: 13.5, duracaoFalaSegundos: 10 })).not.toBeNull();
  });

  it("cold intro (vocal logo no começo) não comporta fala", () => {
    expect(planejarFalaSobreIntro({ inicioSegundos: 0, inicioVocalSegundos: C.INTRO_MIN_S - 0.1, duracaoFalaSegundos: 1 })).toBeNull();
  });

  it("sem início do vocal conhecido: sem ramp", () => {
    expect(planejarFalaSobreIntro({ inicioSegundos: 0, inicioVocalSegundos: null, duracaoFalaSegundos: 3 })).toBeNull();
    expect(planejarFalaSobreIntro({ inicioSegundos: 0, inicioVocalSegundos: undefined, duracaoFalaSegundos: 3 })).toBeNull();
    expect(planejarFalaSobreIntro({ inicioSegundos: 0, inicioVocalSegundos: Number.NaN, duracaoFalaSegundos: 3 })).toBeNull();
  });

  it("duração da fala desconhecida, zero ou longa demais: sem ramp", () => {
    expect(planejarFalaSobreIntro({ inicioVocalSegundos: 60, duracaoFalaSegundos: null })).toBeNull();
    expect(planejarFalaSobreIntro({ inicioVocalSegundos: 60, duracaoFalaSegundos: 0 })).toBeNull();
    expect(planejarFalaSobreIntro({ inicioVocalSegundos: 60, duracaoFalaSegundos: Number.POSITIVE_INFINITY })).toBeNull();
    // fala de 20 s caberia em 60 s de intro, mas já é bloco de conversa
    expect(planejarFalaSobreIntro({ inicioVocalSegundos: 60, duracaoFalaSegundos: C.FALA_MAX_S + 1 })).toBeNull();
  });

  it("início do corte omitido vale zero", () => {
    expect(planejarFalaSobreIntro({ inicioVocalSegundos: 20, duracaoFalaSegundos: 5 })?.posicaoEntradaS).toBe(2);
  });
});

describe("medirDuracaoAudio", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  function stubAudio(comportamento: (audio: any) => void) {
    class FakeAudio {
      duration = Number.NaN;
      preload = "";
      private ouvintes: Record<string, (() => void)[]> = {};
      constructor(public src: string) {
        queueMicrotask(() => comportamento(this));
      }
      addEventListener(nome: string, cb: () => void) {
        (this.ouvintes[nome] ??= []).push(cb);
      }
      disparar(nome: string) {
        this.ouvintes[nome]?.forEach((cb) => cb());
      }
    }
    vi.stubGlobal("Audio", FakeAudio);
  }

  it("devolve a duração quando os metadados carregam", async () => {
    stubAudio((a) => { a.duration = 7.5; a.disparar("loadedmetadata"); });
    expect(await medirDuracaoAudio("blob:1")).toBe(7.5);
  });

  it("duração inválida (Infinity/NaN) vira null", async () => {
    stubAudio((a) => { a.duration = Number.POSITIVE_INFINITY; a.disparar("loadedmetadata"); });
    expect(await medirDuracaoAudio("blob:1")).toBeNull();
  });

  it("erro de mídia vira null", async () => {
    stubAudio((a) => a.disparar("error"));
    expect(await medirDuracaoAudio("blob:1")).toBeNull();
  });

  it("sem metadados a tempo vira null", async () => {
    vi.useFakeTimers();
    stubAudio(() => {});
    const promessa = medirDuracaoAudio("blob:1", 500);
    await vi.advanceTimersByTimeAsync(600);
    expect(await promessa).toBeNull();
  });
});
