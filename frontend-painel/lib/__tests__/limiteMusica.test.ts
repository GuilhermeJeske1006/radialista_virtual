import { expect, it } from "vitest";
import { limiteMusicaMs } from "../limiteMusica";

it("Blue Monday de sete minutos não é interrompida pelo antigo limite de seis", () => {
  expect(limiteMusicaMs(449)).toBeGreaterThan(449000);
});

it("usa a duração do trecho, conserva margem e limita metadados inválidos", () => {
  expect(limiteMusicaMs(900, 60, 300)).toBe(270000);
  expect(limiteMusicaMs(Number.NaN)).toBe(360000);
  expect(limiteMusicaMs(Infinity)).toBe(360000);
  expect(limiteMusicaMs(999999)).toBeLessThanOrEqual(25 * 60 * 1000);
});
