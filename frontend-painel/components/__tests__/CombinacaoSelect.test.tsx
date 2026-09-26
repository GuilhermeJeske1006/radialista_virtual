import { beforeEach, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CombinacaoSelect from "../CombinacaoSelect";

const api = vi.hoisted(() => vi.fn());
vi.mock("../../lib/api", () => ({ apiFetch: api }));

const catalogo = {
  mensalidade_brl: 69.9, minutos_fala_por_hora: 6, premissas: "Estimativa com 6 minutos de fala nova.",
  combinacoes: [
    { id: "premium", nome: "Premium", descricao: "Voz expressiva", limitacoes: "Maior custo", recomendada: true,
      modelo_texto: "claude-opus-5", modelo_voz: "eleven_v3", preco_hora_brl: 2.5 },
    { id: "agil", nome: "Ágil", descricao: "Voz rápida", limitacoes: "Sem direção vocal", recomendada: false,
      modelo_texto: "claude-sonnet-5", modelo_voz: "eleven_flash_v2_5", preco_hora_brl: 1 },
  ],
};

beforeEach(() => { api.mockReset(); api.mockResolvedValue(catalogo); });

it("pré-seleciona a recomendada e mostra modelos, preço e limitações", async () => {
  const onChange = vi.fn();
  render(<CombinacaoSelect value={null} onChange={onChange} />);
  expect(await screen.findByText("Claude Opus 5")).toHaveAttribute("translate", "no");
  expect(screen.getByText("ElevenLabs v3")).toBeInTheDocument();
  expect(screen.getByText(/2,50 \/ hora de programa/)).toBeInTheDocument();
  expect(screen.getByText(/Limitações: Sem direção vocal/)).toBeInTheDocument();
  expect(screen.getByText(/Mensalidade de R\$\s69,90 à parte/)).toBeInTheDocument();
  await waitFor(() => expect(onChange).toHaveBeenCalledWith(catalogo.combinacoes[0]));
});

it("mantém a escolha prévia e troca ao clicar", async () => {
  const onChange = vi.fn();
  render(<CombinacaoSelect value="agil" onChange={onChange} />);
  const agil = await screen.findByRole("radio", { name: /Ágil/ });
  expect(agil).toBeChecked();
  expect(onChange).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("radio", { name: /Premium/ }));
  expect(onChange).toHaveBeenCalledWith(catalogo.combinacoes[0]);
});

it("estima o mês do programa pelo horário", async () => {
  const programa = { horario_inicio: "06:00:00", horario_fim: "09:00:00", dias_semana: [], data_especifica: null };
  render(<CombinacaoSelect value="agil" onChange={vi.fn()} programa={programa} />);
  // 3 h × 30 exibições × R$ 1/h
  expect(await screen.findByText(/Este programa: ≈ R\$\s90,00\/mês/)).toBeInTheDocument();
});

it("catálogo vazio avisa que usa a configuração padrão", async () => {
  api.mockResolvedValue({ ...catalogo, combinacoes: [] });
  const onChange = vi.fn();
  render(<CombinacaoSelect value={null} onChange={onChange} />);
  expect(await screen.findByText(/após a publicação das tarifas/)).toBeInTheDocument();
  expect(onChange).toHaveBeenCalledWith(null);
});

it("mostra exemplo em áudio, texto gerado e composição do custo", async () => {
  const completa = {
    ...catalogo.combinacoes[0],
    custo_hora_brl: { texto: 1.49, classificacao: 0.26, voz: 6.6 },
    preco_mes_referencia_brl: 250.5,
    preco_mil_caracteres_brl: 1.1,
    exemplo: { pedido: "Anuncie Twist and Shout.", texto: "Boa tarde, Curitiba!", audio_url: "/exemplos/combinacoes/premium.mp3",
      duracao_segundos: 23.8, caracteres_voz: 480, voz_padrao: true, preco_brl: 0.0567 },
  };
  api.mockResolvedValue({ ...catalogo, horas_mes_referencia: 30, combinacoes: [completa] });
  render(<CombinacaoSelect value="premium" onChange={vi.fn()} />);
  const audio = await screen.findByLabelText("Exemplo da combinação Premium");
  expect(audio).toHaveAttribute("src", "/exemplos/combinacoes/premium.mp3");
  expect(audio).toHaveAttribute("preload", "none");
  expect(screen.getByText(/24 s · custaria R\$\s0,0567/)).toBeInTheDocument();
  expect(screen.getByText(/1 h por dia: ≈ R\$\s250,50\/mês de uso \(30 h no mês\)/)).toBeInTheDocument();
  // Texto do exemplo aparece junto do áudio, sem precisar abrir nada; o pedido comum vem uma vez só.
  expect(screen.getByText("“Boa tarde, Curitiba!”")).toBeVisible();
  expect(screen.getByText("“Anuncie Twist and Shout.”")).toBeVisible();
  await userEvent.click(screen.getByText("Ver composição do custo"));
  expect(screen.getByText(/R\$\s6,60\/h/)).toBeVisible();
  expect(screen.getByText(/1,10 por mil caracteres/)).toBeInTheDocument();
});

it("explica o que cada modelo faz, separando texto e voz", async () => {
  api.mockResolvedValue({
    ...catalogo,
    modelos: {
      "claude-opus-5": { funcao: "texto", descricao: "O mais elaborado." },
      eleven_v3: { funcao: "voz", descricao: "A mais expressiva." },
    },
  });
  render(<CombinacaoSelect value="premium" onChange={vi.fn()} />);
  const texto = (await screen.findByText("Modelos de texto")).parentElement!;
  expect(within(texto).getByText("Claude Opus 5")).toBeInTheDocument();
  expect(within(texto).getByText("O mais elaborado.")).toBeInTheDocument();
  const voz = screen.getByText("Modelos de voz").parentElement!;
  expect(within(voz).getByText("ElevenLabs v3")).toBeInTheDocument();
  expect(within(voz).getByText("A mais expressiva.")).toBeInTheDocument();
});
