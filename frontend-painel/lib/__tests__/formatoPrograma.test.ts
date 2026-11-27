import { describe, expect, it } from "vitest";
import {
  blocosExtrasDoFormato,
  definicaoDoFormato,
  ehMusical,
  formatoDe,
  FORMATOS_ESPELHO,
  formatosImplementados,
  roteiroDoFormato,
  ROTEIRO_MUSICAL,
  ROTEIRO_PADRAO,
  tipoMusical,
} from "../formatoPrograma";
import { formatosFixture } from "./formatosFixtures";

const programa = (perfil_programacao?: string) => ({ perfil_programacao });

describe("formatoDe (id canônico, como app.live.formatos.resolver_formato)", () => {
  it("vazio, ausente ou programa nulo cai no padrão", () => {
    expect(formatoDe(programa())).toBe("padrao");
    expect(formatoDe(programa(""))).toBe("padrao");
    expect(formatoDe(programa("  "))).toBe("padrao");
    expect(formatoDe(null)).toBe("padrao");
    expect(formatoDe(undefined)).toBe("padrao");
  });

  it("resolve o alias musical_companhia para musical_adulto, com e sem a lista da rota", () => {
    expect(formatoDe(programa("musical_companhia"))).toBe("musical_adulto");
    expect(formatoDe(programa("musical_companhia"), formatosFixture())).toBe("musical_adulto");
    expect(formatoDe(programa("musical_adulto"))).toBe("musical_adulto");
  });

  it("os formatos novos voltam como estão", () => {
    expect(formatoDe(programa("popular_sertanejo"))).toBe("popular_sertanejo");
    expect(formatoDe(programa("variedades_leves"), formatosFixture())).toBe("variedades_leves");
  });

  it("valor desconhecido ou formato não implementado cai no padrão (D13)", () => {
    expect(formatoDe(programa("inexistente"))).toBe("padrao");
    expect(formatoDe(programa("hits"), formatosFixture())).toBe("padrao");
  });
});

describe("ehMusical", () => {
  it("só o musical adulto (e o alias) tem o ciclo musical", () => {
    expect(ehMusical(programa("musical_companhia"))).toBe(true);
    expect(ehMusical(programa("musical_adulto"))).toBe(true);
    expect(ehMusical(programa("popular_sertanejo"))).toBe(false);
    expect(ehMusical(programa("variedades_leves"))).toBe(false);
    expect(ehMusical(programa("padrao"))).toBe(false);
    expect(ehMusical(null)).toBe(false);
  });
});

describe("roteiroDoFormato e blocos extras", () => {
  it("cada formato implementado tem o roteiro do catálogo; o padrão tem o do motor", () => {
    expect(roteiroDoFormato(programa())).toEqual(ROTEIRO_PADRAO);
    expect(roteiroDoFormato(programa("musical_companhia"))).toEqual(ROTEIRO_MUSICAL);
    expect(roteiroDoFormato(programa("popular_sertanejo"))).toEqual(["musica", "chamada_ouvinte", "musica", "comentario", "musica", "retomada"]);
    expect(roteiroDoFormato(programa("variedades_leves"))).toEqual(["musica", "comentario", "musica", "chamada_ouvinte", "musica", "retomada"]);
  });

  it("a lista da rota prevalece sobre o espelho", () => {
    const lista = formatosFixture().map((f) => f.id === "popular_sertanejo" ? { ...f, roteiro_padrao: ["musica", "recado"] } : f);
    expect(roteiroDoFormato(programa("popular_sertanejo"), lista)).toEqual(["musica", "recado"]);
    expect(roteiroDoFormato(programa("popular_sertanejo"))).toHaveLength(6);
  });

  it("devolve uma cópia: alterar o roteiro não altera o espelho", () => {
    const roteiro = roteiroDoFormato(programa("musical_adulto"));
    roteiro.push("extra");
    expect(roteiroDoFormato(programa("musical_adulto"))).toEqual(ROTEIRO_MUSICAL);
  });

  it("só o musical ignora os blocos extras (D23); os outros respeitam a flag do programa", () => {
    expect(blocosExtrasDoFormato(programa("musical_companhia"))).toBe(false);
    expect(blocosExtrasDoFormato(programa("musical_adulto"), formatosFixture())).toBe(false);
    expect(blocosExtrasDoFormato(programa("popular_sertanejo"))).toBe(true);
    expect(blocosExtrasDoFormato(programa("variedades_leves"))).toBe(true);
    expect(blocosExtrasDoFormato(programa())).toBe(true);
  });

  it("definicaoDoFormato traz os textos quando a rota respondeu e vazios no espelho", () => {
    expect(definicaoDoFormato(programa("popular_sertanejo"), formatosFixture()).promessa).toBe("Companhia e reconhecimento.");
    expect(definicaoDoFormato(programa("popular_sertanejo")).promessa).toBe("");
    expect(definicaoDoFormato(programa("musical_companhia")).id).toBe("musical_adulto");
    expect(definicaoDoFormato(programa("flashback")).id).toBe("musical_curado");
  });
});

describe("formatosImplementados (o que o select oferece)", () => {
  it("com a rota: só os implementados, padrão primeiro, sem os futuros", () => {
    expect(formatosImplementados(formatosFixture()).map((f) => f.id)).toEqual([
      "padrao", "musical_adulto", "popular_sertanejo", "variedades_leves", "musical_curado",
    ]);
  });

  it("sem a rota (vazia, nula ou não lista): o espelho", () => {
    expect(formatosImplementados([]).map((f) => f.id)).toEqual(FORMATOS_ESPELHO.map((f) => f.id));
    expect(formatosImplementados(null).map((f) => f.id)).toEqual(FORMATOS_ESPELHO.map((f) => f.id));
    expect(formatosImplementados(undefined)).toHaveLength(5);
  });
});

describe("espelho sincronizado com o catálogo do backend", () => {
  it("id, nome, alias, roteiro, relógio sugerido e blocos extras iguais à cópia da rota", () => {
    const porId = Object.fromEntries(formatosFixture().map((f) => [f.id, f]));
    for (const espelho of FORMATOS_ESPELHO) {
      const rota = porId[espelho.id];
      expect(rota, espelho.id).toBeDefined();
      expect(rota.implementado).toBe(true);
      expect(espelho.nome).toBe(rota.nome);
      expect(espelho.aliases).toEqual(rota.aliases);
      expect(espelho.roteiro_padrao).toEqual(rota.roteiro_padrao);
      expect(espelho.relogio_padrao).toBe(rota.relogio_padrao);
      expect(espelho.ia_pode_adicionar_blocos).toBe(rota.ia_pode_adicionar_blocos);
    }
  });
});

describe("tipoMusical (prévia do ciclo musical)", () => {
  it("abertura só na largada; depois o roteiro do formato pelo deslocamento (n-1)", () => {
    expect(tipoMusical([], 0)).toBe("abertura");
    expect(tipoMusical([], 1)).toBe("musica");
    expect(tipoMusical([], 3)).toBe("identificacao");
    expect(tipoMusical([], 6)).toBe("retomada");
    expect(tipoMusical([], 7)).toBe("musica");
  });

  it("estrutura personalizada sem abertura nem encerramento substitui o roteiro", () => {
    expect(tipoMusical(["abertura", "musica", "Encerramento do dia", "retomada"], 1)).toBe("musica");
    expect(tipoMusical(["abertura", "musica", "Encerramento do dia", "retomada"], 2)).toBe("retomada");
  });

  it("aceita o roteiro do formato como referência", () => {
    expect(tipoMusical([], 2, ["musica", "recado"])).toBe("recado");
  });
});
