import { describe, expect, it } from "vitest";
import { normalizarPrograma, PROGRAMA_VAZIO, rotuloBloco, Programa } from "../types";

describe("rotuloBloco", () => {
  it("devolve o label do preset pra blocos conhecidos", () => {
    expect(rotuloBloco("musica")).toBe("Música");
    expect(rotuloBloco("chamada_ouvinte")).toBe("Chamada ao ouvinte");
  });

  it("devolve o proprio texto pra bloco customizado", () => {
    expect(rotuloBloco("Musica Vaneira")).toBe("Musica Vaneira");
  });

  it("resolve nome do patrocinador quando informado", () => {
    expect(rotuloBloco("patrocinador:5", { 5: "Loja X" })).toBe("Patrocinador: Loja X");
  });

  it("cai pro id quando o nome do patrocinador nao e conhecido", () => {
    expect(rotuloBloco("patrocinador:5")).toBe("Patrocinador #5");
  });
});

describe("normalizarPrograma", () => {
  it("preenche arrays nulos com listas vazias", () => {
    const programaComNulos = {
      ...PROGRAMA_VAZIO,
      id: 1,
      radio_config_id: 1,
      topicos_permitidos: null,
      generos_musicais: undefined,
    } as unknown as Programa;

    const normalizado = normalizarPrograma(programaComNulos);
    expect(normalizado.topicos_permitidos).toEqual([]);
    expect(normalizado.generos_musicais).toEqual([]);
  });

  it("preserva arrays ja preenchidos", () => {
    const programa: Programa = {
      ...PROGRAMA_VAZIO,
      id: 1,
      radio_config_id: 1,
      topicos_permitidos: ["musica", "esportes"],
    };
    expect(normalizarPrograma(programa).topicos_permitidos).toEqual(["musica", "esportes"]);
  });
});
