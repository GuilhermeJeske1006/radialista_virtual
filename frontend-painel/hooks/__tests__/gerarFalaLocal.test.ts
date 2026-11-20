import { describe, expect, it } from "vitest";
import { gerarFalaLocal } from "../useLiveEngine";
import { PROGRAMA_VAZIO, Programa, Radialista } from "../../lib/types";

// Fala de emergência do painel (TTS/LLM indisponível): F6 (D22) troca as frases que prometiam conteúdo pela
// reorientação neutra da F5 e decide o tipo pelo formato do programa, sem comparar a string crua.

const radialista = { nome_locutor: "Ana" } as Radialista;

function programa(overrides: Partial<Programa> = {}): Programa {
  return { ...PROGRAMA_VAZIO, id: 1, radio_config_id: 1, nome: "Tarde Sertaneja", ...overrides };
}

const PROMESSAS = [/volto com mais/i, /trago certinho/i, /eu leio aqui/i, /assim que a fonte/i];

describe("gerarFalaLocal", () => {
  it.each(["musical_companhia", "musical_adulto"])("musical (%s): identificação curta com o nome do programa", (perfil) => {
    const fala = gerarFalaLocal(radialista, programa({ perfil_programacao: perfil }), 3);
    expect(fala.tipo).toBe("identificacao");
    expect(fala.fala).toContain("Tarde Sertaneja");
  });

  it("com o nome da rádio, a identificação do musical reorienta com programa e rádio", () => {
    const fala = gerarFalaLocal(radialista, programa({ perfil_programacao: "musical_adulto" }), 3, "Rádio Serra");
    expect(fala.fala).toContain("Você está no Tarde Sertaneja, na Rádio Serra.");
  });

  it("estrutura vazia: abertura na largada e depois o roteiro do formato pelo deslocamento (n-1), como o motor", () => {
    const popular = programa({ perfil_programacao: "popular_sertanejo", estrutura_blocos: [] });
    expect(gerarFalaLocal(radialista, popular, 0).tipo).toBe("abertura");
    expect(gerarFalaLocal(radialista, popular, 1).tipo).toBe("musica");
    expect(gerarFalaLocal(radialista, popular, 2).tipo).toBe("chamada_ouvinte");
    expect(gerarFalaLocal(radialista, popular, 4).tipo).toBe("comentario");

    const livre = programa({ estrutura_blocos: [] });
    expect(gerarFalaLocal(radialista, livre, 0).tipo).toBe("abertura");
    expect(gerarFalaLocal(radialista, livre, 1).tipo).toBe("musica");
    expect(gerarFalaLocal(radialista, livre, 3).tipo).toBe("comentario");
  });

  it("estrutura personalizada: segue a sequência do programa em loop, sem o encerramento", () => {
    const p = programa({ perfil_programacao: "variedades_leves", estrutura_blocos: ["musica", "Encerramento", "retomada"] });
    expect(gerarFalaLocal(radialista, p, 0).tipo).toBe("musica");
    expect(gerarFalaLocal(radialista, p, 1).tipo).toBe("retomada");
    expect(gerarFalaLocal(radialista, p, 2).tipo).toBe("musica");
  });

  it("nenhuma fala de emergência promete conteúdo (D22) e todas reorientam com o nome do programa", () => {
    const p = programa({ estrutura_blocos: ["abertura", "musica", "comentario", "noticia", "chamada_ouvinte", "retomada"] });
    for (let total = 0; total < 6; total += 1) {
      const { fala } = gerarFalaLocal(radialista, p, total, "Rádio Serra");
      for (const promessa of PROMESSAS) expect(fala, fala).not.toMatch(promessa);
      expect(fala, fala).toContain("Tarde Sertaneja");
      expect(fala, fala).toContain("Rádio Serra");
    }
  });
});
