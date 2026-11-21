import { describe, expect, it } from "vitest";
import { ajustarDuracao, formatarMinSeg, lerMinSeg, recalcularInicios, totais } from "../relogio";
import { relogioA } from "./relogioFixtures";

describe("relógio da hora (edição)", () => {
  it("formata e lê mm:ss", () => {
    expect(formatarMinSeg(40)).toBe("00:40");
    expect(formatarMinSeg(3600)).toBe("60:00");
    expect(lerMinSeg("0:50")).toBe(50);
    expect(lerMinSeg("11:20")).toBe(680);
    expect(lerMinSeg("75")).toBe(75);
    expect(lerMinSeg("1:75")).toBeNull();
    expect(lerMinSeg("abc")).toBeNull();
  });

  it("recalcula os inícios a partir das durações e soma os totais", () => {
    const relogio = relogioA();
    const embaralhado = relogio.eventos.map((e) => ({ ...e, inicio_s: 0 }));
    expect(recalcularInicios(embaralhado).map((e) => e.inicio_s)).toEqual(relogio.eventos.map((e) => e.inicio_s));
    expect(totais(relogio.eventos)).toEqual({ musica_s: 3015, fala_s: 225, intervalo_s: 360, total_s: 3600 });
  });

  it("compensa o ajuste na próxima música ajustável e mantém 60:00", () => {
    const resultado = ajustarDuracao(relogioA(), 2, 50);
    expect(resultado.erro).toBeUndefined();
    const eventos = resultado.relogio!.eventos;
    expect(eventos[2].duracao_s).toBe(50);
    expect(eventos[3].duracao_s).toBe(670);
    expect(eventos[3].inicio_s).toBe(770);
    expect(totais(eventos).total_s).toBe(3600);
  });

  it("sem música depois, compensa na anterior", () => {
    const resultado = ajustarDuracao(relogioA(), 11, 40);
    expect(resultado.relogio!.eventos[10].duracao_s).toBe(200);
    expect(totais(resultado.relogio!.eventos).total_s).toBe(3600);
  });

  it("recusa compensação que deixaria a música abaixo do mínimo ou duração inválida", () => {
    const resultado = ajustarDuracao(relogioA(), 9, 380);
    expect(resultado.relogio).toBeUndefined();
    expect(resultado.erro).toMatch(/Música de fechamento.*mínimo é 00:30/);
    expect(ajustarDuracao(relogioA(), 0, 0).erro).toMatch(/maior que zero/);
    const soMusicaFixa = { ...relogioA(), eventos: relogioA().eventos.map((e) => ({ ...e, natureza: "obrigatorio" as const })) };
    expect(ajustarDuracao(soMusicaFixa, 2, 50).erro).toMatch(/Não há música ajustável/);
  });
});
