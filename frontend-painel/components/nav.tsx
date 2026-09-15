/**
 * Navegação em um lugar só — sidebar (desktop) e header (mobile) liam duas
 * listas separadas e saíam de sincronia.
 *
 * Os ícones são monoline de traço 1.75 com ponta arredondada, o mesmo desenho
 * do símbolo da marca. Cada um nomeia o que a pessoa faz ali, não como o
 * sistema chama: microfone para locutores, ondas para transmissão.
 */

export type NavGroup = "Principal" | "Conteúdo" | "Conta";

export type NavLink = {
  href: string;
  label: string;
  adminOnly?: boolean;
  icon: React.ReactNode;
  /** ausente pros links fora da navegação principal (Ajuda, Perfil, Sair). */
  group?: NavGroup;
  /** 1/2/3 -- ganha o prefixo numérico enquanto o setup inicial não termina
   * (ver useConfiguracaoInicialCompleta). */
  numeroSetup?: number;
};

export function NavIcone({ children, className = "h-5 w-5 shrink-0" }: { children: React.ReactNode; className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

export const NAV_LINKS: NavLink[] = [
  {
    href: "/dashboard",
    group: "Principal",
    label: "Visão geral",
    icon: (
      <>
        <rect x="3.5" y="3.5" width="7" height="7" rx="2.5" />
        <rect x="13.5" y="3.5" width="7" height="7" rx="2.5" />
        <rect x="3.5" y="13.5" width="7" height="7" rx="2.5" />
        <rect x="13.5" y="13.5" width="7" height="7" rx="2.5" />
      </>
    ),
  },
  {
    href: "/live",
    group: "Principal",
    label: "Ao vivo",
    numeroSetup: 3,
    icon: (
      <>
        <circle cx="12" cy="12" r="2" />
        <path d="M8.2 8.2a5.4 5.4 0 0 0 0 7.6" />
        <path d="M15.8 8.2a5.4 5.4 0 0 1 0 7.6" />
        <path d="M5.4 5.4a9.3 9.3 0 0 0 0 13.2" />
        <path d="M18.6 5.4a9.3 9.3 0 0 1 0 13.2" />
      </>
    ),
  },
  {
    href: "/metrics",
    group: "Principal",
    label: "Métricas",
    icon: (
      <>
        <path d="M6 20V10" />
        <path d="M12 20V4" />
        <path d="M18 20v-7" />
      </>
    ),
  },
  {
    href: "/conversas",
    group: "Principal",
    label: "Conversas",
    icon: (
      <>
        <path d="M4 6.5A2.5 2.5 0 0 1 6.5 4h9A2.5 2.5 0 0 1 18 6.5v6a2.5 2.5 0 0 1-2.5 2.5H10l-4 4v-4H6.5A2.5 2.5 0 0 1 4 12.5v-6Z" />
      </>
    ),
  },
  {
    href: "/radialista",
    group: "Conteúdo",
    label: "Locutores",
    numeroSetup: 1,
    icon: (
      <>
        <rect x="9" y="3" width="6" height="10" rx="3" />
        <path d="M6 11a6 6 0 0 0 12 0" />
        <path d="M12 17v4" />
      </>
    ),
  },
  {
    href: "/programas",
    group: "Conteúdo",
    label: "Programas",
    numeroSetup: 2,
    icon: (
      <>
        <path d="M9 6h11M9 12h11M9 18h11" />
        <circle cx="5" cy="6" r="1" />
        <circle cx="5" cy="12" r="1" />
        <circle cx="5" cy="18" r="1" />
      </>
    ),
  },
  {
    href: "/programacao",
    group: "Conteúdo",
    label: "Grade",
    icon: (
      <>
        <rect x="3.5" y="5" width="17" height="15" rx="2.5" />
        <path d="M3.5 10h17" />
        <path d="M8 3v4M16 3v4" />
      </>
    ),
  },
  {
    href: "/vinhetagem",
    group: "Conteúdo",
    label: "Vinhetagem",
    icon: (
      <>
        <path d="M4 12h3l2-5 3 10 2-7 2 4h4" />
      </>
    ),
  },
  {
    href: "/billing",
    group: "Conta",
    label: "Assinatura",
    adminOnly: true,
    icon: (
      <>
        <rect x="3" y="5" width="18" height="14" rx="3.5" />
        <path d="M3 10h18" />
        <path d="M7 14.5h3" />
      </>
    ),
  },
  {
    href: "/equipe",
    group: "Conta",
    label: "Equipe",
    adminOnly: true,
    icon: (
      <>
        <circle cx="9.5" cy="8" r="3" />
        <path d="M4 19a5.5 5.5 0 0 1 11 0" />
        <path d="M16 5.6a3 3 0 0 1 0 5.8" />
        <path d="M17.6 13.6A5.5 5.5 0 0 1 20.5 18" />
      </>
    ),
  },
  {
    href: "/configuracoes",
    group: "Conta",
    label: "Configuração",
    icon: (
      <>
        <path d="M5 4v5M5 14v6M12 4v2M12 11v9M19 4v8M19 17v3" />
        <circle cx="5" cy="11.5" r="2.2" />
        <circle cx="12" cy="8.5" r="2.2" />
        <circle cx="19" cy="14.5" r="2.2" />
      </>
    ),
  },
];

export const LINK_AJUDA: NavLink = {
  href: "/ajuda",
  label: "Ajuda",
  icon: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M9.5 9.2a2.5 2.5 0 0 1 4.9.8c0 1.6-2.4 1.8-2.4 3.5" />
      <circle cx="12" cy="17.2" r=".6" fill="currentColor" />
    </>
  ),
};

export const LINK_PERFIL: NavLink = {
  href: "/perfil",
  label: "Perfil",
  icon: (
    <>
      <circle cx="12" cy="8" r="3.5" />
      <path d="M5 19.5a7 7 0 0 1 14 0" />
    </>
  ),
};

export const ICONE_SAIR = (
  <>
    <path d="M14 4h3.5A2.5 2.5 0 0 1 20 6.5v11a2.5 2.5 0 0 1-2.5 2.5H14" />
    <path d="M10 8l-4 4 4 4" />
    <path d="M6 12h10" />
  </>
);
