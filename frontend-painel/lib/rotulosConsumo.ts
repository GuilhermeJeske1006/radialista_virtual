// Rótulos exibidos ao cliente para os códigos do extrato e das faturas (backend
// app/billing). Código desconhecido aparece como veio, para não esconder informação.

const FUNCIONALIDADES: Record<string, string> = {
  programa_ao_vivo: "Programa ao vivo",
  locucao: "Locução",
  configuracao_ia: "Configuração com IA",
  patrocinadores: "Patrocinadores",
  vinhetas: "Vinhetas",
  roteiros: "Roteiros",
  roteiros_automaticos: "Roteiros automáticos",
  noticias: "Notícias",
  participacao_ouvintes: "Participação de ouvintes",
  atendimento_whatsapp: "Atendimento WhatsApp",
  amostra_personalizada: "Amostra personalizada",
  credito: "Crédito",
  llm: "Texto",
  tts: "Voz",
  stt: "Transcrição",
  music: "Trilha musical",
};

const ESTADOS_USO: Record<string, string> = {
  reservado: "Em andamento",
  medido: "Em andamento",
  concluido: "Concluído",
  falha: "Não cobrado",
  ajuste: "Ajuste",
  ajuste_aplicado: "Ajuste aplicado",
};

const ESTADOS_FATURA: Record<string, string> = {
  conferindo: "Em conferência",
  apurada: "Apurada",
  emitida: "Emitida",
  pendente: "Pagamento pendente",
  paga: "Paga",
};

const STATUS_ASSINATURA: Record<string, string> = {
  ativo: "Ativa",
  trial: "Aguardando assinatura",
  inadimplente: "Pagamento pendente",
  cancelado: "Cancelada",
};

const UNIDADES: Record<string, string> = {
  entrada: "tokens de entrada",
  saida: "tokens de saída",
  cache_write: "tokens gravados em cache",
  cache_read: "tokens lidos do cache",
  buscas: "buscas",
  caracteres: "caracteres",
  segundos: "segundos",
  milissegundos: "milissegundos",
};

export const rotuloFuncionalidade = (codigo: string) => FUNCIONALIDADES[codigo] ?? codigo;
export const rotuloEstadoUso = (codigo: string) => ESTADOS_USO[codigo] ?? codigo;
export const rotuloEstadoFatura = (codigo: string) => ESTADOS_FATURA[codigo] ?? codigo;
export const rotuloStatusAssinatura = (codigo: string) => STATUS_ASSINATURA[codigo] ?? codigo;
export const rotuloUnidade = (codigo: string) => UNIDADES[codigo] ?? codigo;

export function formatarQuantidade(valor: string | number): string {
  const numero = Number(valor);
  return Number.isFinite(numero) ? numero.toLocaleString("pt-BR", { maximumFractionDigits: 3 }) : String(valor);
}

// Resumo das unidades de um uso, sem as zeradas (cache e buscas quase sempre vêm 0).
export function resumirUnidades(unidades: Record<string, string>): string {
  const itens = Object.entries(unidades).filter(([, v]) => Number(v) !== 0);
  return itens.length ? itens.map(([k, v]) => `${formatarQuantidade(v)} ${rotuloUnidade(k)}`).join(" · ") : "—";
}

// Tarifa de referência na moeda de origem, com casas suficientes para centavos de dólar.
export function formatarTarifa(preco: string, moeda: string): string {
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: moeda, maximumFractionDigits: 6 }).format(
    Number(preco),
  );
}

// Câmbio e acréscimo chegam como texto decimal ("5.5"); exibir no formato brasileiro.
export function formatarDecimal(valor: string): string {
  const numero = Number(valor);
  return Number.isFinite(numero) ? numero.toLocaleString("pt-BR", { maximumFractionDigits: 4 }) : valor;
}
