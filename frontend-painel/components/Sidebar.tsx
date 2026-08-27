"use client";

import type { ReactElement } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { apiFetch } from "../lib/api";
import { limparContaCache, useConta } from "../lib/useConta";
import { LocufyLogo, LocufyMark } from "./LocufyLogo";

type SidebarLink = {
  href: string;
  label: string;
  adminOnly?: boolean;
  icon: ReactElement;
};

type SidebarGroup = {
  label: string;
  links: SidebarLink[];
};

const GROUPS: SidebarGroup[] = [
  {
    label: "Principal",
    links: [
      {
        href: "/dashboard",
        label: "Dashboard",
        icon: (
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z"
          />
        ),
      },
      {
        href: "/live",
        label: "Ao Vivo",
        icon: (
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M8.288 15.038a5.25 5.25 0 117.424 0M6.34 17.5a8.25 8.25 0 1111.32 0M12 12.75a.75.75 0 11-.75-.75.75.75 0 01.75.75z"
          />
        ),
      },
      {
        href: "/metrics",
        label: "Métricas",
        icon: (
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z"
          />
        ),
      },
      {
        href: "/conversas",
        label: "Conversas",
        icon: (
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M20.25 8.511c.884.284 1.5 1.128 1.5 2.097v4.286c0 1.136-.847 2.1-1.98 2.193-.34.027-.68.052-1.02.072v3.091l-3-3c-1.354 0-2.694-.055-4.02-.163a2.115 2.115 0 01-.825-.242m9.345-8.334a2.126 2.126 0 00-.476-.095 48.64 48.64 0 00-8.048 0c-1.131.094-1.976 1.057-1.976 2.192v4.286c0 .837.46 1.58 1.155 1.951m9.345-8.334V6.637c0-1.621-1.152-3.026-2.76-3.235A48.455 48.455 0 0011.25 3c-2.115 0-4.198.137-6.24.402-1.608.209-2.76 1.614-2.76 3.235v6.226c0 1.621 1.152 3.026 2.76 3.235.577.075 1.157.14 1.74.194V21l4.155-4.155"
          />
        ),
      },
    ],
  },
  {
    label: "Configuração inicial",
    links: [
      {
        href: "/radialista",
        label: "1. Radialistas",
        icon: (
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
          />
        ),
      },
      {
        href: "/programas",
        label: "2. Programas",
        icon: (
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M8.25 6.75h12M8.25 12h12M8.25 17.25h12M3.75 6.75h.007v.008H3.75V6.75zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zM3.75 12h.007v.008H3.75V12zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zM3.75 17.25h.007v.008H3.75v-.008zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z"
          />
        ),
      },
      {
        href: "/onboarding",
        label: "3. WhatsApp",
        icon: (
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z"
          />
        ),
      },
    ],
  },
  {
    label: "Conteúdo",
    links: [
      {
        href: "/programacao",
        label: "Grade",
        icon: (
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5"
          />
        ),
      },
      {
        href: "/vinhetagem",
        label: "Vinhetagem",
        icon: (
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M10.34 15.84c-.688-.06-1.386-.09-2.09-.09H7.5a4.5 4.5 0 110-9h.75c.704 0 1.402-.03 2.09-.09m0 9.18c.253.962.584 1.892.985 2.783.247.55.06 1.21-.463 1.511l-.657.38c-.551.318-1.26.117-1.527-.461a20.845 20.845 0 01-1.44-4.282m3.102.069a18.03 18.03 0 01-.59-4.59c0-1.586.205-3.124.59-4.59m0 9.18a23.848 23.848 0 018.835 2.535M10.34 6.66a23.847 23.847 0 008.835-2.535m0 0A23.74 23.74 0 0018.795 3m.38 1.125a23.91 23.91 0 011.014 5.395m-1.014 8.855c-.118.38-.245.754-.38 1.125m.38-1.125a23.91 23.91 0 001.014-5.395m0-3.46c.495.413.811 1.035.811 1.73 0 .695-.316 1.317-.811 1.73m0-3.46a24.347 24.347 0 010 3.46"
          />
        ),
      },
    ],
  },
  {
    label: "Conta",
    links: [
      {
        href: "/billing",
        label: "Assinatura",
        adminOnly: true,
        icon: (
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        ),
      },
      {
        href: "/equipe",
        label: "Equipe",
        adminOnly: true,
        icon: (
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.94-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.06 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z"
          />
        ),
      },
      {
        href: "/configuracoes",
        label: "Configuração",
        icon: (
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M10.343 3.94c.09-.542.56-.94 1.11-.94h1.093c.55 0 1.02.398 1.11.94l.149.894c.07.424.384.764.78.93.398.164.855.142 1.205-.108l.737-.527a1.125 1.125 0 011.45.12l.773.774c.39.389.44 1.002.12 1.45l-.527.737c-.25.35-.272.806-.107 1.204.165.397.505.71.93.78l.893.15c.543.09.94.56.94 1.109v1.094c0 .55-.397 1.02-.94 1.11l-.893.149c-.425.07-.765.383-.93.78-.165.398-.143.854.107 1.204l.527.738c.32.447.269 1.06-.12 1.45l-.774.773a1.125 1.125 0 01-1.449.12l-.738-.527c-.35-.25-.806-.272-1.203-.107-.397.165-.71.505-.781.929l-.149.894c-.09.542-.56.94-1.11.94h-1.094c-.55 0-1.019-.398-1.11-.94l-.148-.894c-.071-.424-.384-.764-.781-.93-.398-.164-.854-.142-1.204.108l-.738.527c-.447.32-1.06.269-1.45-.12l-.773-.774a1.125 1.125 0 01-.12-1.45l.527-.737c.25-.35.273-.806.108-1.204-.165-.397-.505-.71-.93-.78l-.894-.15c-.542-.09-.94-.56-.94-1.109v-1.094c0-.55.398-1.02.94-1.11l.894-.149c.424-.07.765-.383.93-.78.165-.398.143-.854-.107-1.204l-.527-.738a1.125 1.125 0 01.12-1.45l.773-.773a1.125 1.125 0 011.45-.12l.737.527c.35.25.807.272 1.204.107.397-.165.71-.505.78-.929l.15-.894z"
          />
        ),
      },
    ],
  },
];

const DIAL_SCALE = ["88", "90", "92", "94", "96", "LOCUFY", "100", "102", "104", "106", "108"];

function NavLink({
  href,
  label,
  icon,
  active,
  colapsada,
}: {
  href: string;
  label: string;
  icon: ReactElement;
  active: boolean;
  colapsada: boolean;
}) {
  return (
    <Link
      href={href}
      title={colapsada ? label : undefined}
      className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
        colapsada ? "justify-center" : ""
      } ${active ? "bg-amber/10 text-amber-text" : "text-fg/65 hover:bg-paper/5 hover:text-fg"}`}
    >
      <svg
        className={`h-5 w-5 shrink-0 ${active ? "text-amber-text" : "text-fg/65"}`}
        fill="none"
        viewBox="0 0 24 24"
        strokeWidth={1.5}
        stroke="currentColor"
      >
        {icon}
      </svg>
      {!colapsada && label}
    </Link>
  );
}

// tela Ao Vivo precisa do maximo de largura pra grade de 3 colunas -- sidebar
// vira uma trilha so' de icones nessa rota (sem toggle manual, so' auto por rota).
export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const conta = useConta();
  const colapsada = pathname === "/live";
  const groups = GROUPS.map((group) => ({
    ...group,
    links: group.links.filter((link) => !link.adminOnly || conta?.role === "admin"),
  })).filter((group) => group.links.length > 0);

  function sair() {
    apiFetch("/auth/logout", { method: "POST" }).catch(() => {});
    limparContaCache();
    router.push("/login");
  }

  return (
    <aside
      className={`hidden md:flex md:flex-col md:fixed md:inset-y-0 bg-surface border-r border-border transition-[width] duration-150 ${
        colapsada ? "md:w-20" : "md:w-72.5"
      }`}
    >
      <div className="flex flex-col flex-1 min-h-0">
        <div className={`py-8 shrink-0 ${colapsada ? "px-0 flex justify-center" : "px-6"}`}>
          {colapsada ? <LocufyMark size={28} /> : <LocufyLogo />}
        </div>
        {!colapsada && (
          <div className="flex justify-between font-mono text-[10px] tracking-wide text-fg/65 border-y border-border px-6 py-2 mb-4">
            {DIAL_SCALE.map((tick) => (
              <span key={tick} className={tick === "LOCUFY" ? "text-amber-text" : ""}>
                {tick}
              </span>
            ))}
          </div>
        )}
        <nav className={`flex-1 overflow-y-auto space-y-5 ${colapsada ? "px-3 pt-2" : "px-4"}`}>
          {groups.map((group) => (
            <div key={group.label}>
              {!colapsada && (
                <div className="text-xs font-medium uppercase tracking-wide text-fg/65 px-3 mb-2 font-mono">
                  {group.label}
                </div>
              )}
              <div className="space-y-1">
                {group.links.map((link) => (
                  <NavLink
                    key={link.href}
                    href={link.href}
                    label={link.label}
                    icon={link.icon}
                    active={pathname === link.href}
                    colapsada={colapsada}
                  />
                ))}
              </div>
            </div>
          ))}
        </nav>
        <div className={`pb-6 space-y-1 border-t border-border pt-4 ${colapsada ? "px-3" : "px-4"}`}>
          <NavLink
            href="/perfil"
            label="Perfil"
            active={pathname === "/perfil"}
            colapsada={colapsada}
            icon={
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z"
              />
            }
          />
          <button
            onClick={sair}
            title={colapsada ? "Sair" : undefined}
            className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-fg/65 hover:bg-paper/5 hover:text-fg transition-colors ${
              colapsada ? "justify-center" : ""
            }`}
          >
            <svg className="h-5 w-5 shrink-0 text-fg/65" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15M12 9l-3 3m0 0l3 3m-3-3h12.75"
              />
            </svg>
            {!colapsada && "Sair"}
          </button>
        </div>
      </div>
    </aside>
  );
}
