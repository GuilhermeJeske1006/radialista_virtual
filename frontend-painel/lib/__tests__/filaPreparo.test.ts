import { expect, it, vi } from "vitest";
import { FilaPreparo } from "../filaPreparo";

function pendente<T>() {
  let resolve!: (valor: T) => void;
  const promise = new Promise<T>((r) => { resolve = r; });
  return { promise, resolve };
}

async function aguardarEtapas() {
  for (let i = 0; i < 30; i++) await Promise.resolve();
}

function criarFila() {
  const textos = Array.from({ length: 8 }, () => pendente<string>());
  const audios = Array.from({ length: 8 }, () => pendente<string>());
  const gerarTexto = vi.fn((contexto: string[]) => textos[contexto.length].promise);
  const prepararAudio = vi.fn((_texto: string, contexto: string[]) => audios[contexto.length].promise);
  const descartar = vi.fn();
  const fila = new FilaPreparo<string[], string, string>([], {
    gerarTexto, prepararAudio, descartar,
    contaNaAntecedencia: (texto) => texto !== "vinheta",
    avancar: (contexto, texto) => texto === "fim" ? null : [...contexto, texto],
  });
  return { fila, textos, audios, gerarTexto, prepararAudio, descartar };
}

it("escreve e sintetiza as próximas duas falas enquanto a primeira voz ainda está em processamento", async () => {
  const { fila, textos, audios, gerarTexto, prepararAudio } = criarFila();
  const primeira = fila.retirar();
  textos[0].resolve("abertura");
  await aguardarEtapas();
  expect(prepararAudio).toHaveBeenCalledWith("abertura", []);
  expect(gerarTexto).toHaveBeenLastCalledWith(["abertura"]);
  textos[1].resolve("musica");
  textos[2].resolve("comentario");
  await aguardarEtapas();
  expect(prepararAudio).toHaveBeenCalledTimes(3);
  expect(gerarTexto).toHaveBeenCalledTimes(3);
  expect(gerarTexto).toHaveBeenLastCalledWith(["abertura", "musica"]);
  audios[0].resolve("audio inicial");
  expect(await primeira).toBe("audio inicial");
  fila.cancelar();
});

it("reproduz na ordem do roteiro mesmo quando a segunda voz fica pronta primeiro, sem gerar de novo", async () => {
  const { fila, textos, audios, prepararAudio } = criarFila();
  const primeira = fila.retirar();
  textos[0].resolve("um");
  textos[1].resolve("dois");
  textos[2].resolve("tres");
  await aguardarEtapas();
  audios[1].resolve("voz dois");
  let primeiraPronta = false;
  primeira.then(() => { primeiraPronta = true; });
  await aguardarEtapas();
  expect(primeiraPronta).toBe(false);
  audios[0].resolve("voz um");
  expect(await primeira).toBe("voz um");
  expect(await fila.retirar()).toBe("voz dois");
  expect(prepararAudio).toHaveBeenCalledTimes(3);
  fila.cancelar();
});

it("cancelar durante a escrita não inicia TTS nem preenche mais a fila", async () => {
  const { fila, textos, prepararAudio, gerarTexto } = criarFila();
  const primeira = fila.retirar();
  await aguardarEtapas();
  fila.cancelar();
  textos[0].resolve("resposta atrasada");
  expect(await primeira).toBeNull();
  expect(await fila.retirar()).toBeNull();
  expect(prepararAudio).not.toHaveBeenCalled();
  expect(gerarTexto).toHaveBeenCalledTimes(1);
});

it("libera áudios prontos e tardios exatamente uma vez ao cancelar", async () => {
  const { fila, textos, audios, descartar } = criarFila();
  fila.preencher();
  textos[0].resolve("um");
  textos[1].resolve("dois");
  audios[0].resolve("pronto");
  await aguardarEtapas();
  fila.cancelar();
  audios[1].resolve("tardio");
  await aguardarEtapas();
  expect(descartar.mock.calls).toEqual([["pronto"], ["tardio"]]);
});

it("não gera outro bloco depois de um encerramento", async () => {
  const { fila, textos, audios, gerarTexto } = criarFila();
  const primeira = fila.retirar();
  textos[0].resolve("fim");
  audios[0].resolve("despedida");
  expect(await primeira).toBe("despedida");
  expect(await fila.retirar()).toBeNull();
  expect(gerarTexto).toHaveBeenCalledTimes(1);
});

it("atravessa vinhetas consecutivas antes de seus downloads terminarem e reserva duas falas", async () => {
  const { fila, textos, audios, prepararAudio, gerarTexto } = criarFila();
  const primeira = fila.retirar();
  for (const [i, texto] of ["musica", "vinheta", "vinheta", "fala seguinte", "outra fala"].entries()) {
    textos[i].resolve(texto);
  }
  await aguardarEtapas();
  expect(prepararAudio).toHaveBeenCalledTimes(5);
  expect(gerarTexto).toHaveBeenLastCalledWith(["musica", "vinheta", "vinheta", "fala seguinte"]);
  audios[0].resolve("musica");
  expect(await primeira).toBe("musica");
  fila.cancelar();
});

it("limita o preparo de um roteiro só de vinhetas e repõe a fila ao consumir uma", async () => {
  const gerarTexto = vi.fn(async (indice: number) => indice);
  const fila = new FilaPreparo(0, {
    gerarTexto, prepararAudio: async (indice: number) => indice,
    avancar: (indice: number) => indice + 1,
    descartar: vi.fn(), contaNaAntecedencia: () => false,
  });
  expect(await fila.retirar()).toBe(0);
  for (let i = 0; i < 5; i++) await aguardarEtapas();
  expect(gerarTexto).toHaveBeenCalledTimes(13); // Atual + teto de 12 entradas.
  expect(await fila.retirar()).toBe(1);
  await aguardarEtapas();
  expect(gerarTexto).toHaveBeenCalledTimes(14);
  fila.cancelar();
});
