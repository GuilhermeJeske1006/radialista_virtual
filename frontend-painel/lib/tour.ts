import { ConfiguracaoInicialEstado } from "./useConfiguracaoInicial";

// appPronto e' do aparelho (localStorage/app instalado, ver lib/instalarApp.ts), nao da conta --
// fica fora de ConfiguracaoInicialEstado pra nao mexer em `completa` (menu numerado).
export type EstadoTour = ConfiguracaoInicialEstado & { appPronto: boolean };

export type PassoTour = {
  numero: number;
  titulo: string;
  texto: string;
  cta: string;
  href: string;
  feito: (estado: EstadoTour) => boolean;
};

export const PASSOS_TOUR: PassoTour[] = [
  {
    numero: 1,
    titulo: "Crie seu radialista",
    texto:
      "Gere um radialista com IA em segundos (nome, voz e personalidade prontos) ou cadastre cada campo manualmente.",
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
    href: "/configuracoes#whatsapp",
    feito: (e) => e.whatsappConectado,
  },
  {
    numero: 4,
    titulo: "Instale o app e libere o som",
    texto:
      "Sem isso o navegador bloqueia a voz e a música até alguém clicar na página. Instalado, o painel toca sozinho, mesmo depois de reiniciar o computador.",
    cta: "Instalar e liberar som",
    href: "/onboarding/app",
    feito: (e) => e.appPronto,
  },
];

/** Caminho da página do passo, sem âncora (ex.: /configuracoes#whatsapp -> /configuracoes). */
export function paginaDoPasso(passo: PassoTour): string {
  return passo.href.split("#")[0];
}

export function passoAtual(estado: EstadoTour): PassoTour | null {
  return PASSOS_TOUR.find((p) => !p.feito(estado)) ?? null;
}
