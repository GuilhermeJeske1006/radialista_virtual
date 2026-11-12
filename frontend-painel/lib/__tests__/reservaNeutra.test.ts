import { describe, expect, it } from "vitest";

import { falaReservaNeutra } from "../reservaNeutra";

// F5 (D16): a fala de reserva do painel não promete conteúdo ("já volto com mais uma novidade"); reorienta quem
// acabou de sintonizar, com os mesmos modelos do backend (app/live/validacao_fala.py, reserva_neutra).
describe("falaReservaNeutra", () => {
  it("usa o programa e a rádio quando os dois existem", () => {
    expect(falaReservaNeutra("Tarde Viva", "Rádio Teste")).toBe("Você está no Tarde Viva, na Rádio Teste.");
  });

  it("cai para a rádio ou o programa sozinhos", () => {
    expect(falaReservaNeutra(null, "Rádio Teste")).toBe("Você está na Rádio Teste.");
    expect(falaReservaNeutra("Tarde Viva", "  ")).toBe("Você está no Tarde Viva.");
  });

  it("sem nome nenhum não inventa e não promete", () => {
    const fala = falaReservaNeutra(undefined, undefined);
    expect(fala).toBe("Você está na rádio.");
    expect(fala.toLowerCase()).not.toMatch(/volto|novidade|daqui a pouco|já já/);
  });
});
