import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import ProximosBlocosPanel from "../ProximosBlocosPanel";
import { PROGRAMA_VAZIO, Programa } from "../../../lib/types";

vi.mock("../../../lib/api", () => ({
  apiFetch: vi.fn().mockResolvedValue([]),
}));

function programa(overrides: Partial<Programa> = {}): Programa {
  return { ...PROGRAMA_VAZIO, id: 1, radio_config_id: 1, ...overrides };
}

function textosDosBlocos(): string[] {
  return screen.getAllByRole("listitem").map((li) => li.textContent ?? "");
}

describe("ProximosBlocosPanel", () => {
  it("sem estrutura customizada, usa o roteiro padrao do motor (offset (n-1), com abertura so' na largada)", () => {
    render(<ProximosBlocosPanel programa={programa({ estrutura_blocos: [] })} totalFalas={0} />);
    const textos = textosDosBlocos();
    // total_falas: 0->abertura (caso especial), 1->musica, 2->abertura ((2-1)%5=1), 3->comentario, 4->noticia
    expect(textos[0]).toContain("Abertura");
    expect(textos[1]).toContain("Música");
    expect(textos[2]).toContain("Abertura");
    expect(textos[3]).toContain("Comentário");
    expect(textos[4]).toContain("Notícia");
  });

  it("sem estrutura customizada e total_falas > 0, segue o roteiro padrao pelo offset (n-1)", () => {
    render(<ProximosBlocosPanel programa={programa({ estrutura_blocos: [] })} totalFalas={1} />);
    const textos = textosDosBlocos();
    // total_falas: 1->musica, 2->abertura, 3->comentario, 4->noticia, 5->chamada_ouvinte
    expect(textos[0]).toContain("Música");
    expect(textos[1]).toContain("Abertura");
    expect(textos[2]).toContain("Comentário");
    expect(textos[3]).toContain("Notícia");
    expect(textos[4]).toContain("Chamada ao ouvinte");
  });

  it("com estrutura customizada, segue exatamente a sequencia definida em loop", () => {
    render(
      <ProximosBlocosPanel
        programa={programa({ estrutura_blocos: ["abertura", "musica", "noticia"] })}
        totalFalas={0}
      />
    );
    const textos = textosDosBlocos();
    expect(textos[0]).toContain("Abertura");
    expect(textos[1]).toContain("Música");
    expect(textos[2]).toContain("Notícia");
    // loop: volta pro inicio depois do fim da estrutura customizada
    expect(textos[3]).toContain("Abertura");
    expect(textos[4]).toContain("Música");
  });

  it("resolve bloco de patrocinador pelo id", async () => {
    const api = await import("../../../lib/api");
    vi.mocked(api.apiFetch).mockResolvedValueOnce([{ id: 7, nome: "Loja X", tipo_conteudo: "texto", ativo: true }]);

    render(
      <ProximosBlocosPanel programa={programa({ estrutura_blocos: ["patrocinador:7"] })} totalFalas={0} />
    );

    expect((await screen.findAllByText("Patrocinador: Loja X")).length).toBeGreaterThan(0);
  });

  it("filtra 'encerramento' da estrutura customizada, sem quebrar o loop", () => {
    render(
      <ProximosBlocosPanel
        programa={programa({ estrutura_blocos: ["abertura", "encerramento", "musica"] })}
        totalFalas={0}
      />
    );
    const textos = textosDosBlocos();
    expect(textos.some((t) => t.toLowerCase().includes("encerramento"))).toBe(false);
    expect(textos[0]).toContain("Abertura");
    expect(textos[1]).toContain("Música");
    expect(textos[2]).toContain("Abertura");
  });

  it("marca o primeiro item como 'a seguir'", () => {
    render(<ProximosBlocosPanel programa={programa({ estrutura_blocos: ["musica"] })} totalFalas={0} />);
    expect(screen.getByText("a seguir")).toBeInTheDocument();
  });

  it("nao renderiza nada sem programa selecionado", () => {
    const { container } = render(<ProximosBlocosPanel programa={null} totalFalas={0} />);
    expect(container).toBeEmptyDOMElement();
  });
});
