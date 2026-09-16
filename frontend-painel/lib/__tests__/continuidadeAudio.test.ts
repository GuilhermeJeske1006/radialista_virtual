import { afterEach, describe, expect, it, vi } from "vitest";
import { esperarTransicao, pausaAntesDoBloco, reproduzirGrupoDeFalas } from "../continuidadeAudio";

afterEach(() => vi.useRealTimers());

describe("continuidade da programação", () => {
  it("aplica só o intervalo recebido antes do próximo bloco", async () => {
    vi.useFakeTimers();
    let liberado = false;
    const espera = esperarTransicao(pausaAntesDoBloco(150), new AbortController().signal)
      .then((valor) => { liberado = valor; });
    await vi.advanceTimersByTimeAsync(149);
    expect(liberado).toBe(false);
    await vi.advanceTimersByTimeAsync(1);
    await espera;
    expect(liberado).toBe(true);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("emenda músicas sem introduzir uma pausa padrão sobre o zero explícito", async () => {
    vi.useFakeTimers();
    expect(await esperarTransicao(pausaAntesDoBloco(0), new AbortController().signal)).toBe(true);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("pausar durante a transição impede a reprodução e remove o timer", async () => {
    vi.useFakeTimers();
    const controller = new AbortController();
    const tocar = vi.fn();
    const espera = esperarTransicao(800, controller.signal).then((ok) => { if (ok) tocar(); });
    await vi.advanceTimersByTimeAsync(300);
    controller.abort();
    await espera;
    await vi.advanceTimersByTimeAsync(1000);
    expect(tocar).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("mantém a cama baixa durante todo o diálogo, inclusive uma linha sem áudio", async () => {
    vi.useFakeTimers();
    const eventos: unknown[] = [];
    const promessa = reproduzirGrupoDeFalas(["primeira", null, "última"], () => true,
      async (fala) => { eventos.push(fala); return fala ? 2 : 0; },
      (baixo) => eventos.push(baixo));
    await vi.runAllTimersAsync();
    const duracao = await promessa;
    expect(eventos).toEqual([true, "primeira", null, "última", false]);
    expect(duracao).toBeCloseTo(4.56, 5); // 2 + 2 de fala + 2 pausas de 280ms entre as 3 linhas
  });

  it("espera um intervalo curto entre uma linha e a próxima, pra soar como troca de turno", async () => {
    vi.useFakeTimers();
    const ordem: string[] = [];
    const promessa = reproduzirGrupoDeFalas(["a", "b"], () => true,
      async (fala) => { ordem.push(`falou:${fala}`); return 1; },
      () => {});
    await vi.advanceTimersByTimeAsync(0);
    expect(ordem).toEqual(["falou:a"]); // "b" so' comeca depois da pausa
    await vi.advanceTimersByTimeAsync(280);
    await promessa;
    expect(ordem).toEqual(["falou:a", "falou:b"]);
  });

  it("não toca o restante nem altera a cama de uma execução que substituiu o diálogo", async () => {
    let ativo = true;
    const fundo = vi.fn();
    const tocar = vi.fn(async () => { ativo = false; return 1; });
    await reproduzirGrupoDeFalas([1, 2, 3], () => ativo, tocar, fundo);
    expect(tocar).toHaveBeenCalledTimes(1);
    expect(fundo.mock.calls).toEqual([[true]]);
  });

  it("restaura a cama quando há falha de reprodução na execução atual", async () => {
    const fundo = vi.fn();
    await expect(reproduzirGrupoDeFalas([1, 2], () => true,
      async () => { throw new Error("áudio inválido"); }, fundo)).rejects.toThrow("áudio inválido");
    expect(fundo.mock.calls).toEqual([[true], [false]]);
  });
});
