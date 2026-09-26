import { describe, expect, it } from "vitest";
import { formatarTelefone } from "../telefone";

describe("formatarTelefone", () => {
  it("formata celular e fixo brasileiros", () => {
    expect(formatarTelefone("5547991230010")).toBe("+55 (47) 99123-0010");
    expect(formatarTelefone("554733221100")).toBe("+55 (47) 3322-1100");
  });

  it("mantém como veio o que não é número brasileiro", () => {
    expect(formatarTelefone("14155550123")).toBe("14155550123");
    expect(formatarTelefone("grupo-123")).toBe("grupo-123");
  });
});
