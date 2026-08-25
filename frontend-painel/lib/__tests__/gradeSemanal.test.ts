import { describe, expect, it } from "vitest";
import {
  corPorIndice,
  dataEspecificaParaDiaSemana,
  horarioParaMinutos,
  segmentosDoPrograma,
} from "../gradeSemanal";
import { PROGRAMA_VAZIO, Programa } from "../types";

function programaFixture(overrides: Partial<Programa> = {}): Programa {
  return { ...PROGRAMA_VAZIO, id: 1, radio_config_id: 1, ...overrides };
}

describe("horarioParaMinutos", () => {
  it("converte HH:MM:SS em minutos desde meia-noite", () => {
    expect(horarioParaMinutos("00:00:00")).toBe(0);
    expect(horarioParaMinutos("08:30:00")).toBe(510);
    expect(horarioParaMinutos("23:59:00")).toBe(1439);
  });
});

describe("dataEspecificaParaDiaSemana", () => {
  it("mapeia data ISO pro indice 0=Seg..6=Dom", () => {
    // 2026-08-24 e' uma segunda-feira
    expect(dataEspecificaParaDiaSemana("2026-08-24")).toBe(0);
    // 2026-08-30 e' um domingo
    expect(dataEspecificaParaDiaSemana("2026-08-30")).toBe(6);
  });
});

describe("segmentosDoPrograma", () => {
  it("programa recorrente num unico dia -> 1 segmento nesse dia", () => {
    const segmentos = segmentosDoPrograma(
      programaFixture({ dias_semana: [2], horario_inicio: "08:00:00", horario_fim: "10:00:00" })
    );
    expect(segmentos).toEqual([{ diaSemana: 2, inicioMin: 480, fimMin: 600 }]);
  });

  it("dias_semana vazio -> aparece nos 7 dias (mesma regra do backend, lista vazia = todos os dias)", () => {
    const segmentos = segmentosDoPrograma(
      programaFixture({ dias_semana: [], horario_inicio: "08:00:00", horario_fim: "10:00:00" })
    );
    expect(segmentos).toHaveLength(7);
    expect(segmentos.map((s) => s.diaSemana).sort((a, b) => a - b)).toEqual([0, 1, 2, 3, 4, 5, 6]);
  });

  it("overnight (horario_inicio > horario_fim) -> 2 segmentos em dias consecutivos", () => {
    const segmentos = segmentosDoPrograma(
      programaFixture({ dias_semana: [5], horario_inicio: "22:00:00", horario_fim: "02:00:00" })
    );
    expect(segmentos).toEqual([
      { diaSemana: 5, inicioMin: 1320, fimMin: 1440 },
      { diaSemana: 6, inicioMin: 0, fimMin: 120 },
    ]);
  });

  it("overnight no ultimo dia da semana (sabado->domingo) faz wrap pro indice 0", () => {
    const segmentos = segmentosDoPrograma(
      programaFixture({ dias_semana: [6], horario_inicio: "22:00:00", horario_fim: "02:00:00" })
    );
    expect(segmentos[1].diaSemana).toBe(0);
  });

  it("data_especifica -> 1 segmento so, no dia calculado a partir da data", () => {
    const segmentos = segmentosDoPrograma(
      programaFixture({
        dias_semana: [],
        data_especifica: "2026-08-24", // segunda
        horario_inicio: "14:00:00",
        horario_fim: "16:00:00",
      })
    );
    expect(segmentos).toEqual([{ diaSemana: 0, inicioMin: 840, fimMin: 960 }]);
  });
});

describe("corPorIndice", () => {
  it("cicla pela paleta de forma estavel e determinista", () => {
    const cor0a = corPorIndice(0);
    const cor0b = corPorIndice(0);
    expect(cor0a).toEqual(cor0b);
    expect(corPorIndice(0)).not.toEqual(corPorIndice(1));
  });

  it("repete a paleta apos o numero de cores disponiveis (5)", () => {
    expect(corPorIndice(5)).toEqual(corPorIndice(0));
  });
});
