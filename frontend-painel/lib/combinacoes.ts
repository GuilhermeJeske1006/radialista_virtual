// Combinações texto + voz oferecidas pelo backend (GET /billing/combinacoes). O preço por
// hora já vem calculado com as tarifas vigentes; aqui só se projeta pelo horário do programa.

// Exemplo real da combinação (mesmo pedido e mesma voz para todas), com o preço que as
// unidades medidas teriam na tarifa vigente.
export type ExemploCombinacao = {
  pedido: string;
  texto: string;
  audio_url: string;
  duracao_segundos: number;
  caracteres_voz: number;
  voz_padrao: boolean;
  preco_brl: number;
};

export type Combinacao = {
  id: string;
  nome: string;
  descricao: string;
  limitacoes: string;
  recomendada: boolean;
  modelo_texto: string;
  modelo_voz: string;
  preco_hora_brl: number;
  // Composição do preço por hora: texto do locutor, classificações auxiliares e voz.
  custo_hora_brl?: { texto: number; classificacao: number; voz: number };
  preco_mes_referencia_brl?: number;
  preco_mil_caracteres_brl?: number;
  exemplo?: ExemploCombinacao | null;
};

// O que cada modelo faz no locutor: o de texto escreve as falas, o de voz as transforma em áudio.
export type ModeloIA = { funcao: "texto" | "voz"; descricao: string };

export type CatalogoCombinacoes = {
  combinacoes: Combinacao[];
  modelos?: Record<string, ModeloIA>;
  // Modelos usados por programa (ou WhatsApp) sem escolha gravada.
  padrao?: { texto: string; voz: string };
  mensalidade_brl: number;
  minutos_fala_por_hora: number;
  horas_mes_referencia?: number;
  premissas: string;
};

export type HorarioPrograma = {
  horario_inicio: string;
  horario_fim: string;
  dias_semana: number[];
  data_especifica: string | null;
};

const MINUTOS_DIA = 24 * 60;

function minutos(hora: string): number {
  const [h, m] = hora.split(":").map(Number);
  return (h || 0) * 60 + (m || 0);
}

// Programa que atravessa a meia-noite (ex.: 22h às 2h) dura até o dia seguinte.
export function horasPorDia(programa: HorarioPrograma): number {
  let duracao = minutos(programa.horario_fim) - minutos(programa.horario_inicio);
  if (duracao <= 0) duracao += MINUTOS_DIA;
  return duracao / 60;
}

// Nenhum dia marcado = todos os dias; data específica = uma exibição só.
export function exibicoesPorMes(programa: HorarioPrograma): number {
  if (programa.data_especifica) return 1;
  const dias = programa.dias_semana.length === 0 ? 7 : programa.dias_semana.length;
  return (dias * 30) / 7;
}

export function horasPorMes(programa: HorarioPrograma): number {
  return horasPorDia(programa) * exibicoesPorMes(programa);
}

export function consumoMensalEstimado(combinacao: Combinacao, programa: HorarioPrograma): number {
  return combinacao.preco_hora_brl * horasPorMes(programa);
}

export function reais(valor: number, casas = 2): string {
  return valor.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  });
}

// Centavos somem em gerações baratas: mostra ao menos 4 casas abaixo de R$ 0,10.
export function reaisPreciso(valor: number): string {
  return reais(valor, valor > 0 && valor < 0.1 ? 4 : 2);
}

const NOMES_MODELOS: Record<string, string> = {
  "claude-opus-5": "Claude Opus 5",
  "claude-sonnet-5": "Claude Sonnet 5",
  "claude-haiku-4-5": "Claude Haiku 4.5",
  eleven_v3: "ElevenLabs v3",
  eleven_flash_v2_5: "ElevenLabs Flash 2.5",
  eleven_multilingual_v2: "ElevenLabs Multilingual 2",
};

export function nomeModelo(id: string): string {
  return NOMES_MODELOS[id] ?? id;
}
