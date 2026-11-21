import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import ProximosBlocosPanel from "../ProximosBlocosPanel";
import { PROGRAMA_VAZIO, Programa } from "../../../lib/types";
import { apiFetch } from "../../../lib/api";
import { formatosFixture } from "../../../lib/__tests__/formatosFixtures";

vi.mock("../../../lib/api", () => ({
  apiFetch: vi.fn().mockResolvedValue([]),
}));

afterEach(() => {
  vi.mocked(apiFetch).mockReset().mockResolvedValue([]);
});

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

it.each(["musical_companhia", "musical_adulto"])(
  "prévia musical (%s) acompanha o ciclo do backend e não promete comentários extras",
  async (perfil_programacao) => {
    const { rerender } = render(<ProximosBlocosPanel programa={programa({ perfil_programacao })} totalFalas={0} />);
    await screen.findByText("Próximos blocos");
    let textos = textosDosBlocos();
    expect(textos[0]).toContain("Abertura");
    expect(textos[1]).toContain("Música");
    expect(textos[2]).toContain("Música");
    expect(textos[3]).toContain("Identificação curta");
    expect(screen.queryByText(/A IA pode ocasionalmente/)).not.toBeInTheDocument();
    rerender(<ProximosBlocosPanel programa={programa({ perfil_programacao })} totalFalas={6} />);
    textos = textosDosBlocos();
    expect(textos[0]).toContain("Retomada");
    expect(textos.some((t) => t.includes("Abertura"))).toBe(false);
  },
);

describe("ProximosBlocosPanel com os formatos da F6 (roteiro do formato com a estrutura vazia)", () => {
  it("popular/sertanejo: abertura na largada e depois o roteiro do formato pelo deslocamento (n-1)", async () => {
    render(<ProximosBlocosPanel programa={programa({ perfil_programacao: "popular_sertanejo" })} totalFalas={0} />);
    await screen.findByText("Próximos blocos");
    const textos = textosDosBlocos();
    expect(textos[0]).toContain("Abertura");
    expect(textos[1]).toContain("Música");
    expect(textos[2]).toContain("Chamada ao ouvinte");
    expect(textos[3]).toContain("Música");
    expect(textos[4]).toContain("Comentário");
    // D23: o popular respeita a flag do programa (PROGRAMA_VAZIO liga os blocos extras).
    expect(screen.getByText(/A IA pode ocasionalmente/)).toBeInTheDocument();
  });

  it("variedades leves: roteiro próprio e sem o aviso de blocos extras quando o programa desliga a flag", async () => {
    render(
      <ProximosBlocosPanel
        programa={programa({ perfil_programacao: "variedades_leves", ia_pode_adicionar_blocos: false })}
        totalFalas={1}
      />,
    );
    await screen.findByText("Próximos blocos");
    const textos = textosDosBlocos();
    expect(textos[0]).toContain("Música");
    expect(textos[1]).toContain("Comentário");
    expect(textos[2]).toContain("Música");
    expect(textos[3]).toContain("Chamada ao ouvinte");
    expect(textos[4]).toContain("Música");
    expect(screen.queryByText(/A IA pode ocasionalmente/)).not.toBeInTheDocument();
  });

  it("com estrutura personalizada, o formato novo segue a sequência do programa em loop", async () => {
    render(
      <ProximosBlocosPanel
        programa={programa({ perfil_programacao: "popular_sertanejo", estrutura_blocos: ["musica", "retomada"] })}
        totalFalas={0}
      />,
    );
    await screen.findByText("Próximos blocos");
    const textos = textosDosBlocos();
    expect(textos[0]).toContain("Música");
    expect(textos[1]).toContain("Retomada");
    expect(textos[2]).toContain("Música");
  });

  it("a lista de GET /config/formatos prevalece sobre o espelho local", async () => {
    const lista = formatosFixture().map((f) =>
      f.id === "popular_sertanejo" ? { ...f, roteiro_padrao: ["noticia", "musica"] } : f,
    );
    vi.mocked(apiFetch).mockImplementation((path: string) =>
      Promise.resolve(path === "/config/formatos" ? lista : []),
    );
    render(<ProximosBlocosPanel programa={programa({ perfil_programacao: "popular_sertanejo" })} totalFalas={1} />);
    expect((await screen.findAllByText("Notícia")).length).toBeGreaterThan(0);
    const textos = textosDosBlocos();
    expect(textos[0]).toContain("Notícia");
    expect(textos[1]).toContain("Música");
    expect(textos[2]).toContain("Notícia");
  });
});

describe("ProximosBlocosPanel com relógio da hora", () => {
  it("troca a prévia por sequência pelo aviso do relógio, com etapa e próximo horário fixo", async () => {
    const { relogioA } = await import("../../../lib/__tests__/relogioFixtures");
    const relogioAoVivo = {
      preset: "A", inicio_previsto: "2026-11-10T15:12:10Z", inicio_previsto_aceito: true, hora: 0,
      etapa: { hora: 0, inicio_s: 720, tipo: "link", tipo_efetivo: "link", rotulo: "Link com um assunto",
        natureza: "ajustavel", hard_time: false, inicio: "2026-11-10T15:12:00Z", fim: "2026-11-10T15:12:35Z" },
      proximo_compromisso: { hora: 0, inicio_s: 1440, tipo: "intervalo", tipo_efetivo: "intervalo", rotulo: "Intervalo",
        natureza: "obrigatorio", hard_time: true, inicio: "2026-11-10T15:24:00Z", fim: "2026-11-10T15:27:00Z" },
      segundos_ate_hard_time: 710, espaco_s: 710, acao: "fala", orcamento_s: [10, 35] as [number, number],
    };
    render(
      <ProximosBlocosPanel programa={programa({ relogio_hora: relogioA() })} totalFalas={3} relogioAoVivo={relogioAoVivo} />,
    );
    expect(screen.getByText("Segue o relógio A: a ordem vem do horário.")).toBeInTheDocument();
    expect(screen.getByText(/Etapa: Link com um assunto \(12:00 da hora\)/)).toBeInTheDocument();
    expect(screen.getByText(/Próximo horário fixo: Intervalo às/)).toBeInTheDocument();
    expect(screen.queryAllByRole("listitem").some((li) => li.textContent?.includes("Abertura"))).toBe(false);
  });
});
