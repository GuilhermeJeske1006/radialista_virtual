import { describe, expect, it } from "vitest";
import { limiteRadialistasPorPrograma, permiteClonagemVoz, formatarReais, PLANOS } from "../planos";

describe("limiteRadialistasPorPrograma", () => {
  it("devolve o limite do plano informado", () => {
    expect(limiteRadialistasPorPrograma("growth")).toBe(2);
    expect(limiteRadialistasPorPrograma("professional")).toBe(3);
  });

  it("cai pra 1 quando o plano e desconhecido ou nulo", () => {
    expect(limiteRadialistasPorPrograma("plano-inexistente")).toBe(1);
    expect(limiteRadialistasPorPrograma(null)).toBe(1);
    expect(limiteRadialistasPorPrograma(undefined)).toBe(1);
  });
});

describe("permiteClonagemVoz", () => {
  it("permite pra growth e professional", () => {
    expect(permiteClonagemVoz("growth")).toBe(true);
    expect(permiteClonagemVoz("professional")).toBe(true);
  });

  it("nao permite pra starter nem plano nulo", () => {
    expect(permiteClonagemVoz("starter")).toBe(false);
    expect(permiteClonagemVoz(null)).toBe(false);
    expect(permiteClonagemVoz(undefined)).toBe(false);
  });
});

describe("formatarReais", () => {
  it("formata numero no padrao pt-BR sem casas decimais", () => {
    expect(formatarReais(1000)).toBe("1.000");
    expect(formatarReais(399)).toBe("399");
  });
});

describe("PLANOS", () => {
  it("tem exatamente 3 planos com ids esperados", () => {
    expect(PLANOS.map((p) => p.id)).toEqual(["starter", "growth", "professional"]);
  });
});
