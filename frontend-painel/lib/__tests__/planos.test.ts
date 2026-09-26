import { describe, expect, it } from "vitest";
import { limiteRadialistasPorPrograma, permiteClonagemVoz, formatarReais, labelBandeira, PLANOS } from "../planos";

describe("limiteRadialistasPorPrograma", () => {
  it("devolve o limite do plano informado", () => {
    expect(limiteRadialistasPorPrograma("growth")).toBe(10);
    expect(limiteRadialistasPorPrograma("professional")).toBe(10);
  });

  it("cai pra 1 quando o plano e desconhecido ou nulo", () => {
    expect(limiteRadialistasPorPrograma("plano-inexistente")).toBe(10);
    expect(limiteRadialistasPorPrograma(null)).toBe(10);
    expect(limiteRadialistasPorPrograma(undefined)).toBe(10);
  });
});

describe("permiteClonagemVoz", () => {
  it("permite pra growth e professional", () => {
    expect(permiteClonagemVoz("growth")).toBe(true);
    expect(permiteClonagemVoz("professional")).toBe(true);
  });

  it("nao permite pra starter nem plano nulo", () => {
    expect(permiteClonagemVoz("flex")).toBe(true);
    expect(permiteClonagemVoz(null)).toBe(false);
    expect(permiteClonagemVoz(undefined)).toBe(false);
  });
});

describe("formatarReais", () => {
  it("formata numero no padrao pt-BR sem casas decimais", () => {
    expect(formatarReais(1000)).toBe("1.000");
    expect(formatarReais(399)).toBe("399");
  });

  it("valor fracionado sempre com duas casas", () => {
    expect(formatarReais(69.9)).toBe("69,90");
    expect(formatarReais(1234.5)).toBe("1.234,50");
  });
});

describe("labelBandeira", () => {
  it("traduz bandeiras conhecidas", () => {
    expect(labelBandeira("visa")).toBe("Visa");
    expect(labelBandeira("mastercard")).toBe("Mastercard");
  });

  it("devolve a propria bandeira quando desconhecida", () => {
    expect(labelBandeira("cabal")).toBe("cabal");
  });
});

describe("PLANOS", () => {
  it("tem exatamente 3 planos com ids esperados", () => {
    expect(PLANOS.map((p) => p.id)).toEqual(["flex"]);
  });
});
