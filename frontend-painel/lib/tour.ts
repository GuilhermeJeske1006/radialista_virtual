import { ConfiguracaoInicialEstado } from "./useConfiguracaoInicial";

export type PassoTour = {
  numero: number;
  titulo: string;
  texto: string;
  cta: string;
  href: string;
  feito: (estado: ConfiguracaoInicialEstado) => boolean;
};

export const PASSOS_TOUR: PassoTour[] = [
  {
    numero: 1,
    titulo: "Crie seu radialista",
    texto:
      "Gere um locutor com IA em segundos (nome, voz e personalidade prontos) ou cadastre cada campo manualmente.",
    cta: "Criar radialista",
    href: "/onboarding/locutor",
    feito: (e) => e.radialistaPronto,
  },
  {
    numero: 2,
    titulo: "Cadastre um programa",
    texto:
      "Defina dias, horário e o que o radialista toca ou fala nesse programa. Sem isso ele não sabe quando entrar no ar.",
    cta: "Criar programa",
    href: "/programas",
    feito: (e) => e.programaAtivo,
  },
  {
    numero: 3,
    titulo: "Conecte o WhatsApp da rádio",
    texto:
      "Escaneie o QR Code com o número que vai atender os ouvintes. Só depois disso o radialista responde de verdade.",
    cta: "Conectar WhatsApp",
    href: "/onboarding",
    feito: (e) => e.whatsappConectado,
  },
];

export function passoAtual(estado: ConfiguracaoInicialEstado): PassoTour | null {
  return PASSOS_TOUR.find((p) => !p.feito(estado)) ?? null;
}
