import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import EditarProgramaForm from "../EditarProgramaForm";
import { BibliotecaAudioItem } from "../../lib/bibliotecaAudio";
import { formatosFixture } from "../../lib/__tests__/formatosFixtures";
import { presetsFixture } from "../../lib/__tests__/relogioFixtures";

const apiFetchMock = vi.fn();

vi.mock("../../lib/api", () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
  ApiError: class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  },
}));

const vinhetaFixture: BibliotecaAudioItem = {
  id: 9,
  nome: "Vinheta QA",
  categoria_id: null,
  audio_nome_original: "x.mp3",
  duracao_segundos: 12,
  cor: null,
  ordem: 0,
  ativo: true,
};

async function renderCriacao() {
  apiFetchMock.mockImplementation((path: string) => {
    if (path === "/config/radio") return Promise.reject(new Error("sem radio configurado"));
    if (path === "/config/tipos-radio") return Promise.resolve([]);
    if (path === "/patrocinadores") return Promise.resolve([]);
    if (path === "/biblioteca-audio") return Promise.resolve([vinhetaFixture]);
    if (path === "/categorias-vinheta") return Promise.resolve([]);
    if (path === "/config/fontes-noticia") return Promise.resolve([]);
    if (path === "/config/formatos") return Promise.resolve(formatosFixture());
    if (path === "/config/relogios/presets") return Promise.resolve(presetsFixture());
    return Promise.resolve({});
  });
  render(<EditarProgramaForm programaId={null} radioConfigId={1} />);
  await screen.findByText("Novo programa");
}

describe("EditarProgramaForm (criação)", () => {
  it("mostra a paleta completa (com vinhetas) desde a criação, sem o aviso de tela dedicada", async () => {
    await renderCriacao();

    expect(await screen.findByText("Vinheta QA")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "+ Abertura" })).toBeInTheDocument();
    expect(screen.queryByText(/reordenar essa sequência arrastando os blocos numa tela dedicada/)).not.toBeInTheDocument();
  });

  it("adicionar um bloco pela paleta atualiza a sequência na prévia", async () => {
    await renderCriacao();

    expect(screen.getByText(/Sequência vazia/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "+ Abertura" }));

    expect(await screen.findByText("Abertura")).toBeInTheDocument();
    expect(screen.queryByText(/Sequência vazia/)).not.toBeInTheDocument();
  });
});

describe("EditarProgramaForm (formato do programa, F6)", () => {
  it("o select oferece só os formatos implementados do catálogo, com 'Livre' primeiro, e mostra a promessa", async () => {
    await renderCriacao();
    const select = screen.getByLabelText("Formato do programa");
    await within(select).findByRole("option", { name: "Popular/sertanejo" });
    expect(within(select).getAllByRole("option").map((o) => o.textContent)).toEqual([
      "Livre (sem formato)", "Musical adulto", "Popular/sertanejo", "Variedades leves", "Flashback 1970–1999",
    ]);
    expect(select).toHaveValue("padrao");
    expect(screen.getByText(/sem promessa de formato/)).toBeInTheDocument();
  });

  it("permite selecionar o formato musical e aplicar seu roteiro sem comentários extras", async () => {
    await renderCriacao();
    const select = screen.getByLabelText("Formato do programa");
    await within(select).findByRole("option", { name: "Musical adulto" });
    await userEvent.selectOptions(select, "musical_adulto");
    expect(screen.getByText(/Acompanhar com curadoria/)).toBeInTheDocument();
    expect(screen.getByText(/Pedido real anunciado no bloco de música/)).toBeInTheDocument();
    expect(screen.getByText(/link de 10 a 35 s/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Usar sequência sugerida" }));
    expect(screen.queryByText(/Sequência vazia/)).not.toBeInTheDocument();
    expect(screen.getAllByText("Identificação curta").length).toBeGreaterThan(0);
    const extras = screen.getByRole("checkbox", { name: /segue a sequência sem inserir comentários extras/ });
    expect(extras).toBeDisabled();
    expect(extras).not.toBeChecked();
    expect(select).toHaveValue("musical_adulto");
    await userEvent.selectOptions(select, "padrao");
    expect(screen.getByRole("checkbox", { name: /IA pode inserir blocos extras/ })).toBeEnabled();
  });

  it("popular/sertanejo: promessa do catálogo, relógio sugerido A aplicado uma vez e blocos extras pela flag do programa", async () => {
    await renderCriacao();
    const select = screen.getByLabelText("Formato do programa");
    await within(select).findByRole("option", { name: "Popular/sertanejo" });
    await userEvent.selectOptions(select, "popular_sertanejo");
    expect(screen.getByText(/Companhia e reconhecimento/)).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /IA pode inserir blocos extras/ })).toBeEnabled();
    expect(screen.getByLabelText("Relógio da hora")).toHaveValue("");
    await userEvent.click(screen.getByRole("button", { name: "Usar relógio sugerido (A)" }));
    expect(screen.getByLabelText("Relógio da hora")).toHaveValue("A");
    expect(screen.queryByRole("button", { name: /Usar relógio sugerido/ })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Usar sequência sugerida" }));
    expect(screen.getAllByText("Chamada ao ouvinte").length).toBeGreaterThan(0);
    expect(screen.getByRole("checkbox", { name: /IA pode inserir blocos extras/ })).toBeChecked();
  });

  it("'Livre' não sugere relógio nem sequência", async () => {
    await renderCriacao();
    await within(screen.getByLabelText("Formato do programa")).findByRole("option", { name: "Popular/sertanejo" });
    expect(screen.queryByRole("button", { name: /Usar relógio sugerido/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Usar sequência sugerida" })).not.toBeInTheDocument();
  });

  async function renderEdicaoFormato(perfil_programacao: string) {
    const { PROGRAMA_VAZIO, RADIO_PERFIL_VAZIO } = await import("../../lib/types");
    const programa = { ...PROGRAMA_VAZIO, id: 5, radio_config_id: 1, nome: "Tarde Sertaneja", perfil_programacao };
    apiFetchMock.mockReset();
    apiFetchMock.mockImplementation((path: string, opcoes?: { method?: string; body?: string }) => {
      if (path === "/config/formatos") return Promise.resolve(formatosFixture());
      if (path === "/config/relogios/presets") return Promise.resolve(presetsFixture());
      if (path === "/config/radio") {
        return Promise.resolve({ ...RADIO_PERFIL_VAZIO, nome_radio: "Rádio Serra", slogan: "A voz da serra",
          cidade: "Urubici", frequencia: "98,7 FM", tipo_radio: "sertaneja" });
      }
      if (path === "/config/programas/5" && opcoes?.method === "PUT") {
        return Promise.resolve({ ...programa, ...JSON.parse(opcoes.body!) });
      }
      if (path === "/config/programas/5") return Promise.resolve(programa);
      return Promise.resolve([]);
    });
    render(<EditarProgramaForm programaId={5} />);
    await screen.findByText("Editar programa");
    await within(screen.getByLabelText("Formato do programa")).findByRole("option", { name: "Popular/sertanejo" });
  }

  const corpoDoPut = () => JSON.parse(
    apiFetchMock.mock.calls.find(([p, o]) => p === "/config/programas/5" && o?.method === "PUT")![1].body,
  );

  it("alias musical_companhia aparece como Musical adulto e é preservado ao salvar sem trocar (D2)", async () => {
    await renderEdicaoFormato("musical_companhia");
    expect(screen.getByLabelText("Formato do programa")).toHaveValue("musical_adulto");
    expect(screen.getByText("O programa usará a sequência sugerida do formato Musical adulto.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Salvar programa" }));
    expect((await screen.findAllByText("Programa salvo.")).length).toBeGreaterThan(0);
    expect(corpoDoPut().perfil_programacao).toBe("musical_companhia");
  });

  it("trocar o formato grava o id canônico escolhido", async () => {
    await renderEdicaoFormato("musical_companhia");
    await userEvent.selectOptions(screen.getByLabelText("Formato do programa"), "variedades_leves");
    expect(screen.getByText(/Ajudar na vida cotidiana/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Salvar programa" }));
    expect((await screen.findAllByText("Programa salvo.")).length).toBeGreaterThan(0);
    expect(corpoDoPut().perfil_programacao).toBe("variedades_leves");
  });

  it("salva o perfil de fala e as orientações dentro do programa", async () => {
    await renderEdicaoFormato("padrao");
    await userEvent.click(screen.getByRole("button", { name: "Personalizar jeito de falar" }));
    await userEvent.selectOptions(screen.getByLabelText("Perfil de fala"), "jornalistico");
    await userEvent.type(screen.getByLabelText("Orientações para este programa"), "Boletins curtos e objetivos.");
    await userEvent.click(screen.getByRole("button", { name: "Salvar programa" }));
    await screen.findAllByText("Programa salvo.");
    expect(corpoDoPut().persona).toMatchObject({
      formalidade: 5, humor: 1, girias: "evitar", orientacoes: "Boletins curtos e objetivos.",
    });
    expect(apiFetchMock.mock.calls.some(([path, opcoes]) =>
      String(path).startsWith("/config/radialistas/") && opcoes?.method === "PUT",
    )).toBe(false);
  });

  it("valor gravado fora do catálogo é mostrado como Livre, avisado e preservado ao salvar", async () => {
    await renderEdicaoFormato("hits");
    expect(screen.getByLabelText("Formato do programa")).toHaveValue("padrao");
    expect(screen.getByText(/Formato gravado "hits"/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Salvar programa" }));
    expect((await screen.findAllByText("Programa salvo.")).length).toBeGreaterThan(0);
    expect(corpoDoPut().perfil_programacao).toBe("hits");
  });

  it("separa a identidade da rádio (somente leitura, com link) da identidade do programa", async () => {
    await renderEdicaoFormato("popular_sertanejo");
    const cartao = screen.getByRole("region", { name: "Identidade da rádio" });
    expect(within(cartao).getByText(/Rádio Serra/)).toBeInTheDocument();
    expect(within(cartao).getByText(/98,7 FM/)).toBeInTheDocument();
    expect(within(cartao).getByText(/Urubici/)).toBeInTheDocument();
    expect(within(cartao).getByText("A voz da serra")).toBeInTheDocument();
    expect(within(cartao).getByRole("link", { name: /Editar em Configurações/ })).toHaveAttribute("href", "/configuracoes");
    expect(within(cartao).queryByRole("textbox")).not.toBeInTheDocument();

    const secao = screen.getByRole("region", { name: "Identidade do programa" });
    expect(within(secao).getByLabelText("Nome do programa")).toHaveValue("Tarde Sertaneja");
    expect(within(secao).getByLabelText("Sobre o programa")).toBeInTheDocument();
    expect(within(secao).getByLabelText("Formato do programa")).toHaveValue("popular_sertanejo");
    expect(within(secao).getByLabelText("O que rende conversa aqui")).toBeInTheDocument();
  });

  it("sem rádio configurada, o cartão da rádio não aparece e o formulário segue", async () => {
    await renderCriacao();
    expect(screen.queryByRole("region", { name: "Identidade da rádio" })).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Identidade do programa" })).toBeInTheDocument();
  });
});

it("permite selecionar o perfil jornalismo e aplicar a estrutura sugerida", async () => {
  await renderCriacao();
  expect(screen.queryByRole("button", { name: "Usar estrutura de jornalismo sugerida" })).not.toBeInTheDocument();

  await userEvent.selectOptions(screen.getByLabelText("Perfil do programa"), "jornalismo");
  await userEvent.click(screen.getByRole("button", { name: "Usar estrutura de jornalismo sugerida" }));

  expect(await screen.findByText("Escalada (manchetes)")).toBeInTheDocument();
  expect(screen.getAllByText("Notícia").length).toBeGreaterThan(0);
  expect(screen.getByText("Giro de notícias")).toBeInTheDocument();
});

describe("EditarProgramaForm (relógio da hora)", () => {
  async function renderEdicao(comRelogio: boolean) {
    const { PROGRAMA_VAZIO } = await import("../../lib/types");
    const { presetsFixture, relogioA } = await import("../../lib/__tests__/relogioFixtures");
    const programa = { ...PROGRAMA_VAZIO, id: 5, radio_config_id: 1, nome: "Tarde", relogio_hora: comRelogio ? relogioA() : null };
    apiFetchMock.mockReset();
    apiFetchMock.mockImplementation((path: string, opcoes?: { method?: string; body?: string }) => {
      if (path === "/config/relogios/presets") return Promise.resolve(presetsFixture());
      if (path === "/config/radio") return Promise.reject(new Error("sem radio configurado"));
      if (path === "/config/programas/5" && opcoes?.method === "PUT") return Promise.resolve(programa);
      if (path === "/config/programas/5") return Promise.resolve(programa);
      if (path === "/config/programas/5/relogio" && opcoes?.method === "PUT") {
        return Promise.resolve({ ...programa, relogio_hora: JSON.parse(opcoes.body!) });
      }
      if (path === "/config/programas/5/relogio") return Promise.resolve({ ...programa, relogio_hora: null });
      return Promise.resolve([]);
    });
    render(<EditarProgramaForm programaId={5} />);
    await screen.findByText("Editar programa");
    await screen.findByRole("option", { name: "A: Musical com companhia" });
  }

  const chamadas = () => apiFetchMock.mock.calls
    .filter(([, opcoes]) => opcoes?.method)
    .map(([path, opcoes]) => `${opcoes.method} ${path}`);

  it("salvar com o relógio alterado chama PUT do programa e depois PUT do relógio", async () => {
    await renderEdicao(false);
    await userEvent.selectOptions(screen.getByLabelText("Relógio da hora"), "A");
    await userEvent.click(screen.getByRole("button", { name: "Salvar programa" }));
    expect((await screen.findAllByText("Programa salvo.")).length).toBeGreaterThan(0);
    expect(chamadas()).toEqual(["PUT /config/programas/5", "PUT /config/programas/5/relogio"]);
    const corpo = JSON.parse(apiFetchMock.mock.calls.find(([p, o]) => p === "/config/programas/5/relogio" && o)![1].body);
    expect(corpo.preset).toBe("A");
    expect(corpo.eventos).toHaveLength(12);
  });

  it("'Sem relógio' num programa com relógio chama DELETE", async () => {
    await renderEdicao(true);
    expect(screen.getByLabelText("Relógio da hora")).toHaveValue("A");
    await userEvent.selectOptions(screen.getByLabelText("Relógio da hora"), "");
    await userEvent.click(screen.getByRole("button", { name: "Salvar programa" }));
    expect((await screen.findAllByText("Programa salvo.")).length).toBeGreaterThan(0);
    expect(chamadas()).toEqual(["PUT /config/programas/5", "DELETE /config/programas/5/relogio"]);
  });

  it("programa sem relógio e sem mudança não chama a rota do relógio", async () => {
    await renderEdicao(false);
    await userEvent.click(screen.getByRole("button", { name: "Salvar programa" }));
    expect((await screen.findAllByText("Programa salvo.")).length).toBeGreaterThan(0);
    expect(chamadas()).toEqual(["PUT /config/programas/5"]);
  });
});

describe("esportes no fluxo de Programas", () => {
  it("escolher Esportivo habilita pesquisa e roteiro sem exigir produção manual", async () => {
    await renderCriacao();
    await userEvent.selectOptions(screen.getByLabelText('Perfil do programa'), 'esportivo');
    expect(screen.getByText(/A IA pesquisa notícias, resultados e classificação/)).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: 'Pode pesquisar' })).toBeChecked();
    expect(screen.queryByText(/Sequência vazia/)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Criar programa' })).toBeEnabled();
    expect(screen.queryByRole('button', { name: 'Preparar edições esportivas' })).not.toBeInTheDocument();
    expect(apiFetchMock.mock.calls.filter(([path]) => path.startsWith('/esportes/'))).toHaveLength(0);
  });

  it("edita e salva o programa esportivo pelo fluxo normal, sem carregar o editor de edições", async () => {
    const { PROGRAMA_VAZIO } = await import('../../lib/types');
    const programa = { ...PROGRAMA_VAZIO, id: 5, radio_config_id: 1, nome: 'Esporte da cidade', perfil: 'esportivo', horario_inicio: '16:00:00', horario_fim: '16:30:00' };
    apiFetchMock.mockReset();
    apiFetchMock.mockImplementation((path: string, opcoes?: { method?: string; body?: string }) => {
      if (path === '/config/programas/5') return Promise.resolve(opcoes?.body ? { ...programa, ...JSON.parse(opcoes.body) } : programa);
      if (path === '/config/radio') return Promise.resolve({ tipo_radio: 'esportiva' });
      return Promise.resolve([]);
    });
    render(<EditarProgramaForm programaId={5} />);
    await screen.findByText('Editar programa');
    expect(screen.queryByRole('region', { name: 'Produção esportiva' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Produção esportiva' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Preparar edições esportivas' })).not.toBeInTheDocument();
    expect(screen.getByLabelText('Perfil do programa')).toBeEnabled();
    await userEvent.click(screen.getByRole('button', { name: 'Salvar programa' }));
    expect((await screen.findAllByText('Programa salvo.')).length).toBeGreaterThan(0);
    expect(apiFetchMock.mock.calls.some(([path, opcoes]) => path === '/config/programas/5' && opcoes?.method === 'PUT')).toBe(true);
    expect(apiFetchMock.mock.calls.filter(([path]) => path.startsWith('/esportes/'))).toHaveLength(0);
  });
});
