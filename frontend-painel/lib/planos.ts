export type Plano = {
  id: string;
  nome: string;
  preco: number;
  agentes: number;
  mensagens: number;
  radialistasPorPrograma: number;
  destaque?: boolean;
  descricao: string;
};

export const PLANOS: Plano[] = [{
  id: "flex", nome: "Locufy Flex", preco: 69.90, agentes: 100, mensagens: 0,
  radialistasPorPrograma: 10, descricao: "Mensalidade de acesso + processamento utilizado, cobrado no fim do ciclo.",
}];

// Espelha LimitesPlano.radialistas_por_programa em backend/app/planos.py -- so usado pra
// texto de upsell na UI; o backend e' quem de fato bloqueia (402) ao adicionar radialista demais.
export function limiteRadialistasPorPrograma(planoId: string | null | undefined): number {
  return PLANOS.find((p) => p.id === planoId)?.radialistasPorPrograma ?? 10;
}

export const PRECO_AGENTE_ADICIONAL = 100;
export const PRECO_EXCEDENTE_1000_MSG = 50;

// Espelha LimitesPlano.clonagem_voz em backend/app/planos.py -- so usado pra decidir se
// mostra o recurso na UI; o backend e' quem de fato bloqueia (402) se tentar sem o plano.

export function permiteClonagemVoz(planoId: string | null | undefined): boolean {
  return !!planoId;
}

export function formatarReais(valor: number) {
  return valor.toLocaleString("pt-BR", { minimumFractionDigits: 0 });
}

// Espelha o retorno de GET /billing/cartao (ver stripe_client.obter_cartao_mais_recente).
export type Cartao = {
  bandeira: string;
  final: string;
  mes_expiracao: number;
  ano_expiracao: number;
};

const BANDEIRA_LABEL: Record<string, string> = {
  visa: "Visa",
  mastercard: "Mastercard",
  amex: "American Express",
  elo: "Elo",
  hipercard: "Hipercard",
  diners: "Diners Club",
  discover: "Discover",
};

export function labelBandeira(bandeira: string): string {
  return BANDEIRA_LABEL[bandeira] ?? bandeira;
}
