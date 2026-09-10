// Cobre so' programaNoAr (a unica funcao pura exportada de useLiveEngine.ts). O motor
// completo (gerarProximaFala, prepararSegmento, tocarMusica etc.) depende de YouTube iframe API
// + HTMLMediaElement real pra fechar o ciclo de reproducao -- fora de escopo aqui; a validacao
// desses fluxos ficou por conta dos testes ao vivo manuais desta sessao (backend real + browser).
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { programaNoAr, segundosParaInicio } from "../useLiveEngine";
import { PROGRAMA_VAZIO, Programa } from "../../lib/types";

// 2026-09-08 = terca-feira, 2026-09-12 = sabado (ver comentario abaixo) -- confirmado via
// Intl.DateTimeFormat em UTC antes de escrever o teste. Mesma dupla de datas que expos o bug
// real desta sessao: programa cadastrado so' pra sabado, testado manualmente numa terca --
// a transmissao manual se autopausava sozinha ~1s depois de comecar porque o watchdog de corte
// pontual (verificarFimPontual em useLiveEngine.ts) tratava "fora do horario configurado" like
// "passou do horario_fim", sem distinguir "dia errado da semana" de "hora errada no dia certo".
const TERCA_12H_UTC = "2026-09-08T12:00:00.000Z";
const SABADO_10H_UTC = "2026-09-12T10:00:00.000Z";

function programa(overrides: Partial<Programa> = {}): Programa {
  return {
    ...PROGRAMA_VAZIO,
    id: 1,
    radio_config_id: 1,
    ...overrides,
  } as Programa;
}

describe("programaNoAr", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("da false quando o programa esta inativo, mesmo dentro do horario/dia certos", () => {
    vi.setSystemTime(new Date(SABADO_10H_UTC));
    const p = programa({ ativo: false, dias_semana: [5], horario_inicio: "08:00:00", horario_fim: "13:00:00" });
    expect(programaNoAr(p, "UTC")).toBe(false);
  });

  it("da false fora do dia da semana configurado -- o bug real desta sessao (Sab-only testado numa terca)", () => {
    vi.setSystemTime(new Date(TERCA_12H_UTC));
    const p = programa({ ativo: true, dias_semana: [5], horario_inicio: "07:00:00", horario_fim: "13:00:00" });
    expect(programaNoAr(p, "UTC")).toBe(false);
  });

  it("da true no dia da semana certo e dentro do horario", () => {
    vi.setSystemTime(new Date(SABADO_10H_UTC));
    const p = programa({ ativo: true, dias_semana: [5], horario_inicio: "07:00:00", horario_fim: "13:00:00" });
    expect(programaNoAr(p, "UTC")).toBe(true);
  });

  it("dias_semana vazio = roda todo dia, sem restricao de dia", () => {
    vi.setSystemTime(new Date(TERCA_12H_UTC));
    const p = programa({ ativo: true, dias_semana: [], horario_inicio: "07:00:00", horario_fim: "13:00:00" });
    expect(programaNoAr(p, "UTC")).toBe(true);
  });

  it("data_especifica bate com hoje = ignora dias_semana", () => {
    vi.setSystemTime(new Date(TERCA_12H_UTC));
    const p = programa({
      ativo: true,
      dias_semana: [5], // sabado -- seria false se checado, mas data_especifica tem prioridade
      data_especifica: "2026-09-08",
      horario_inicio: "07:00:00",
      horario_fim: "13:00:00",
    });
    expect(programaNoAr(p, "UTC")).toBe(true);
  });

  it("data_especifica de outro dia = false mesmo com dias_semana compativel", () => {
    vi.setSystemTime(new Date(TERCA_12H_UTC));
    const p = programa({
      ativo: true,
      dias_semana: [],
      data_especifica: "2026-09-09",
      horario_inicio: "00:00:00",
      horario_fim: "23:59:59",
    });
    expect(programaNoAr(p, "UTC")).toBe(false);
  });

  it("false antes do horario_inicio", () => {
    vi.setSystemTime(new Date(SABADO_10H_UTC)); // 10:00 UTC
    const p = programa({ ativo: true, dias_semana: [5], horario_inicio: "11:00:00", horario_fim: "13:00:00" });
    expect(programaNoAr(p, "UTC")).toBe(false);
  });

  it("false depois do horario_fim", () => {
    vi.setSystemTime(new Date(SABADO_10H_UTC)); // 10:00 UTC
    const p = programa({ ativo: true, dias_semana: [5], horario_inicio: "07:00:00", horario_fim: "09:00:00" });
    expect(programaNoAr(p, "UTC")).toBe(false);
  });

  it("inclusivo nas duas pontas do horario", () => {
    vi.setSystemTime(new Date(SABADO_10H_UTC)); // exatamente 10:00:00 UTC
    expect(
      programaNoAr(programa({ ativo: true, dias_semana: [5], horario_inicio: "10:00:00", horario_fim: "13:00:00" }), "UTC")
    ).toBe(true);
    expect(
      programaNoAr(programa({ ativo: true, dias_semana: [5], horario_inicio: "07:00:00", horario_fim: "10:00:00" }), "UTC")
    ).toBe(true);
  });

  it("janela que cruza a meia-noite (ex.: programa noturno 22h-02h)", () => {
    // 23:30 UTC de sabado -- dentro da janela 22:00-02:00
    vi.setSystemTime(new Date("2026-09-12T23:30:00.000Z"));
    const p = programa({ ativo: true, dias_semana: [5], horario_inicio: "22:00:00", horario_fim: "02:00:00" });
    expect(programaNoAr(p, "UTC")).toBe(true);

    // 12:00 UTC de sabado -- fora da janela 22h-02h
    vi.setSystemTime(new Date(SABADO_10H_UTC));
    expect(programaNoAr(p, "UTC")).toBe(false);
  });
});

describe("segundosParaInicio", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("da a contagem regressiva ate horario_inicio no dia certo", () => {
    vi.setSystemTime(new Date(SABADO_10H_UTC)); // 10:00 UTC
    const p = programa({ ativo: true, dias_semana: [5], horario_inicio: "10:01:30", horario_fim: "13:00:00" });
    expect(segundosParaInicio(p, "UTC")).toBe(90);
  });

  it("null quando ja passou do horario_inicio (mesmo ainda dentro da janela do programa)", () => {
    vi.setSystemTime(new Date(SABADO_10H_UTC));
    const p = programa({ ativo: true, dias_semana: [5], horario_inicio: "07:00:00", horario_fim: "13:00:00" });
    expect(segundosParaInicio(p, "UTC")).toBe(null);
  });

  it("null quando o programa esta inativo", () => {
    vi.setSystemTime(new Date(SABADO_10H_UTC));
    const p = programa({ ativo: false, dias_semana: [5], horario_inicio: "10:05:00", horario_fim: "13:00:00" });
    expect(segundosParaInicio(p, "UTC")).toBe(null);
  });

  it("null fora do dia da semana configurado", () => {
    vi.setSystemTime(new Date(TERCA_12H_UTC));
    const p = programa({ ativo: true, dias_semana: [5], horario_inicio: "12:05:00", horario_fim: "13:00:00" });
    expect(segundosParaInicio(p, "UTC")).toBe(null);
  });

  it("data_especifica de outro dia da null mesmo com horario_inicio ainda por vir hoje", () => {
    vi.setSystemTime(new Date(TERCA_12H_UTC));
    const p = programa({ ativo: true, dias_semana: [], data_especifica: "2026-09-09", horario_inicio: "12:05:00", horario_fim: "13:00:00" });
    expect(segundosParaInicio(p, "UTC")).toBe(null);
  });
});
