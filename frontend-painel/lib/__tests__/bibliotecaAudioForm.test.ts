import { describe, expect, it } from "vitest";
import { dadosFormVinheta } from "../bibliotecaAudio";

const base = { nome: "Abertura", categoria_id: 4, cor: "#e8a33d", ordem: 2, ativo: true, uso: "promocao" as const };
const arquivo = new File(["mp3"], "abertura.mp3", { type: "audio/mpeg" });

describe("dadosFormVinheta", () => {
  it("criação manda o áudio em `arquivos`, o campo que o POST /biblioteca-audio exige", () => {
    const dados = dadosFormVinheta({ ...base, arquivo }, true);
    expect(dados.getAll("arquivos")).toHaveLength(1);
    expect((dados.get("arquivos") as File).name).toBe("abertura.mp3");
    expect(dados.has("arquivo")).toBe(false);
  });

  it("edição troca o áudio pelo campo `arquivo` do PUT, e sem arquivo não manda nenhum", () => {
    const comArquivo = dadosFormVinheta({ ...base, arquivo }, false);
    expect((comArquivo.get("arquivo") as File).name).toBe("abertura.mp3");
    expect(comArquivo.has("arquivos")).toBe(false);
    const semArquivo = dadosFormVinheta({ ...base, arquivo: null }, false);
    expect(semArquivo.has("arquivo")).toBe(false);
  });

  it("manda nome, categoria, cor, ordem, ativo e uso", () => {
    const dados = dadosFormVinheta({ ...base, arquivo: null }, false);
    expect(Object.fromEntries(dados.entries())).toEqual({
      nome: "Abertura", categoria_id: "4", cor: "#e8a33d", ordem: "2", ativo: "true", uso: "promocao",
    });
  });

  it("sem categoria e sem cor não manda os campos", () => {
    const dados = dadosFormVinheta({ ...base, categoria_id: null, cor: "", arquivo: null }, false);
    expect(dados.has("categoria_id")).toBe(false);
    expect(dados.has("cor")).toBe(false);
  });
});
