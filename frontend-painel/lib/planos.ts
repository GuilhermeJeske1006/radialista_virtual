export type Plano = {
  id: string;
  nome: string;
  preco: number;
  agentes: number;
  mensagens: number;
  destaque?: boolean;
  descricao: string;
};

export const PLANOS: Plano[] = [
  {
    id: "starter",
    nome: "Starter",
    preco: 299,
    agentes: 1,
    mensagens: 1000,
    descricao: "Pequenos negócios",
  },
  {
    id: "growth",
    nome: "Growth",
    preco: 599,
    agentes: 3,
    mensagens: 3000,
    destaque: true,
    descricao: "Empresas em crescimento",
  },
  {
    id: "professional",
    nome: "Professional",
    preco: 999,
    agentes: 5,
    mensagens: 7500,
    descricao: "Maior volume de atendimento",
  },
  {
    id: "business",
    nome: "Business",
    preco: 1499,
    agentes: 10,
    mensagens: 15000,
    descricao: "Operações maiores",
  },
];

export const PRECO_AGENTE_ADICIONAL = 100;
export const PRECO_EXCEDENTE_1000_MSG = 50;

export function formatarReais(valor: number) {
  return valor.toLocaleString("pt-BR", { minimumFractionDigits: 0 });
}
