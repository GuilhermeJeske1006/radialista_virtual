import { describe, it, expect } from "vitest";
import { dataNoFuso, isoNoFuso, modeloEsportivoDoPrograma, proximaExibicaoEsportiva } from "../esportes";

describe("horários editoriais da emissora", () => {
  it("converte São Paulo sem depender do fuso do operador", () => {
    expect(isoNoFuso("2026-11-11T16:00", "America/Sao_Paulo")).toBe("2026-11-11T19:00:00.000Z");
    expect(dataNoFuso("2026-11-11T19:00:00Z", "America/Sao_Paulo")).toBe("2026-11-11T16:00");
  });
  it("considera fusos com meia hora e virada do dia", () => {
    expect(isoNoFuso("2026-11-12T00:15", "Asia/Kolkata")).toBe("2026-11-11T18:45:00.000Z");
    expect(isoNoFuso("2026-11-11T23:30", "America/Manaus")).toBe("2026-11-12T03:30:00.000Z");
  });
  it("considera horário de verão no fuso da rádio", () => {
    expect(isoNoFuso("2026-07-11T16:00", "America/New_York")).toBe("2026-07-11T20:00:00.000Z");
    expect(isoNoFuso("2026-11-11T16:00", "America/New_York")).toBe("2026-11-11T21:00:00.000Z");
  });
  it("rejeita hora inexistente na mudança de horário de verão", () => {
    expect(() => isoNoFuso("2026-03-08T02:30", "America/New_York")).toThrow(/não existe/);
  });
});


describe("integração com a grade do programa", () => {
  const programa = { horario_inicio: "16:00:00", horario_fim: "16:30:00", dias_semana: [0, 1, 2, 3, 4], data_especifica: null };
  it("sugere o modelo conforme a duração já cadastrada", () => {
    expect(modeloEsportivoDoPrograma(programa)).toBe('programa_30');
    expect(modeloEsportivoDoPrograma({ ...programa, horario_fim: "16:02:00" })).toBe('boletim_2');
    expect(modeloEsportivoDoPrograma({ ...programa, horario_fim: "16:03:00" })).toBe('boletim_3');
    expect(modeloEsportivoDoPrograma({ ...programa, horario_inicio: "23:45:00", horario_fim: "00:15:00" })).toBe('programa_30');
  });
  it("usa hoje se o programa ainda vai começar no fuso da emissora", () => {
    expect(proximaExibicaoEsportiva(programa, 'America/Sao_Paulo', new Date('2026-11-11T18:00:00Z'))).toBe('2026-11-11T16:00');
  });
  it("pula dias fora da grade quando a exibição de hoje já passou", () => {
    expect(proximaExibicaoEsportiva(programa, 'America/Sao_Paulo', new Date('2026-11-13T20:00:00Z'))).toBe('2026-11-16T16:00');
  });
  it("respeita programas avulsos e deixa data vencida para revisão do operador", () => {
    expect(proximaExibicaoEsportiva({ ...programa, data_especifica: '2026-12-20' }, 'America/Sao_Paulo', new Date('2026-11-11T18:00:00Z'))).toBe('2026-12-20T16:00');
    expect(proximaExibicaoEsportiva({ ...programa, data_especifica: '2026-11-10' }, 'America/Sao_Paulo', new Date('2026-11-11T18:00:00Z'))).toBe('');
  });
});
