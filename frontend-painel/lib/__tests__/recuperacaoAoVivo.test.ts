import { afterEach, expect, it, vi } from "vitest";
import { RecuperacaoAoVivo } from "../recuperacaoAoVivo";

afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); });

it("espaça novas tentativas, limita a espera e recupera após sucesso", async () => {
  vi.useFakeTimers();
  vi.spyOn(Math, "random").mockReturnValue(0);
  const circuito = new RecuperacaoAoVivo();
  for (const espera of [5_000, 10_000, 20_000, 30_000, 30_000]) {
    circuito.falhou();
    let liberou = false;
    const aguardar = circuito.aguardar(() => true).then(() => { liberou = true; });
    await vi.advanceTimersByTimeAsync(espera - 1);
    expect(liberou).toBe(false);
    await vi.advanceTimersByTimeAsync(1);
    await aguardar;
    expect(circuito.disponivel()).toBe(true);
  }
  circuito.falhou();
  circuito.sucesso();
  expect(circuito.disponivel()).toBe(true);
});

it("cancelamento libera o preparo sem esperar o cooldown inteiro", async () => {
  vi.useFakeTimers();
  const circuito = new RecuperacaoAoVivo();
  circuito.falhou();
  let ativo = true;
  const aguardar = circuito.aguardar(() => ativo);
  ativo = false;
  await vi.advanceTimersByTimeAsync(250);
  await aguardar;
  expect(circuito.disponivel()).toBe(false);
});
