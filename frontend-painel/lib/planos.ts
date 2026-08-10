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

export const PLANOS: Plano[] = [
  {
    id: "starter",
    nome: "Starter",
    preco: 399,
    agentes: 1,
    mensagens: 1000,
    radialistasPorPrograma: 1,
    descricao: "Pequenos negócios",
  },
  {
    id: "growth",
    nome: "Growth",
    preco: 599,
    agentes: 3,
    mensagens: 3000,
    radialistasPorPrograma: 2,
    destaque: true,
    descricao: "Empresas em crescimento",
  },
  {
    id: "professional",
    nome: "Professional",
    preco: 999,
    agentes: 5,
    mensagens: 7500,
    radialistasPorPrograma: 3,
    descricao: "Maior volume de atendimento",
  },
];

// Espelha LimitesPlano.radialistas_por_programa em backend/app/planos.py -- so usado pra
// texto de upsell na UI; o backend e' quem de fato bloqueia (402) ao adicionar radialista demais.
export function limiteRadialistasPorPrograma(planoId: string | null | undefined): number {
  return PLANOS.find((p) => p.id === planoId)?.radialistasPorPrograma ?? 1;
}

export const PRECO_AGENTE_ADICIONAL = 100;
export const PRECO_EXCEDENTE_1000_MSG = 50;

// Espelha LimitesPlano.clonagem_voz em backend/app/planos.py -- so usado pra decidir se
// mostra o recurso na UI; o backend e' quem de fato bloqueia (402) se tentar sem o plano.
const PLANOS_COM_CLONAGEM_VOZ = new Set(["growth", "professional"]);

export function permiteClonagemVoz(planoId: string | null | undefined): boolean {
  return !!planoId && PLANOS_COM_CLONAGEM_VOZ.has(planoId);
}

export function formatarReais(valor: number) {
  return valor.toLocaleString("pt-BR", { minimumFractionDigits: 0 });
}
