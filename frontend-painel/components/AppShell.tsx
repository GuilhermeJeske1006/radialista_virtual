"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import Sidebar from "./Sidebar";
import NotificationBell from "./NotificationBell";
import OnboardingTour from "./OnboardingTour";
import SuporteChat from "./SuporteChat";
import { apiFetch } from "../lib/api";
import { limparContaCache, useConta } from "../lib/useConta";
import { useConfiguracaoInicialCompleta } from "../lib/useConfiguracaoInicial";
import { LocufyMark, LocufyWaveform } from "./LocufyLogo";
import { LINK_AJUDA, LINK_PERFIL, NAV_LINKS } from "./nav";
import ThemeToggle from "./ThemeToggle";

export default function AppShell({
  title,
  children,
  noAr = false,
  maxWidthClassName = "max-w-4xl",
}: {
  title: string;
  children: React.ReactNode;
  /** Programa transmitindo agora — acende o indicador no header. */
  noAr?: boolean;
  maxWidthClassName?: string;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const conta = useConta();
  const setupCompleto = useConfiguracaoInicialCompleta();
  const links = NAV_LINKS.filter((link) => !link.adminOnly || conta?.role === "admin").map((link) =>
    link.numeroSetup && !setupCompleto ? { ...link, label: `${link.numeroSetup}. ${link.label}` } : link
  );
  // acompanha o recolhimento automático da sidebar na tela Ao Vivo (ver Sidebar.tsx)
  const sidebarColapsada = pathname === "/live";

  function sair() {
    apiFetch("/auth/logout", { method: "POST" }).catch(() => {});
    limparContaCache();
    router.push("/login");
  }

  return (
    <div className="min-h-screen bg-bg">
      <Sidebar />
      <div
        className={`flex flex-col min-h-screen transition-[padding] duration-150 ${
          sidebarColapsada ? "md:pl-20" : "md:pl-72.5"
        }`}
      >
        <header className="sticky top-0 z-10 bg-bg/90 backdrop-blur border-b border-border">
          <div className="flex items-center justify-between h-16 px-4 sm:px-6">
            <div className="flex items-center gap-3 min-w-0">
              <LocufyMark size={24} className="shrink-0 text-acento-claro md:hidden" />
              <h1 className="font-display text-xl font-semibold text-fg truncate">{title}</h1>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {/* Estado, não etiqueta: a onda só se mexe quando tem programa no
                  ar, e o chip apaga quando não tem. */}
              <span
                className={`hidden sm:flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-semibold ${
                  noAr ? "bg-ciano/15 text-ciano" : "text-fg/40"
                }`}
              >
                {noAr ? <LocufyWaveform bars={5} className="h-3" /> : null}
                {noAr ? "No ar" : "Fora do ar"}
              </span>
              <ThemeToggle />
              <NotificationBell />

            </div>
          </div>

          {/* Mobile: pílulas roláveis, mesma forma do menu do desktop. */}
          <nav aria-label="Navegação principal" className="md:hidden flex gap-2 overflow-x-auto px-4 sm:px-6 pb-3">
            {[...links, LINK_AJUDA, LINK_PERFIL].map((link) => {
              const ativo = pathname === link.href;
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  aria-current={ativo ? "page" : undefined}
                  className={`shrink-0 rounded-full px-3.5 py-1.5 text-sm font-semibold whitespace-nowrap transition-colors ${
                    ativo ? "bg-acento text-on-brand" : "bg-fg/5 text-fg/60"
                  }`}
                >
                  {link.label}
                </Link>
              );
            })}
            <button
              type="button"
              onClick={sair}
              className="shrink-0 rounded-full px-3.5 py-1.5 text-sm font-semibold whitespace-nowrap bg-fg/5 text-fg/60 hover:bg-fg/10 transition-colors"
            >
              Sair
            </button>
          </nav>
        </header>

        <main className="flex-1 px-4 sm:px-6 py-6">
          <div className={`${maxWidthClassName} mx-auto`}>{children}</div>
        </main>
      </div>
      {!setupCompleto && <OnboardingTour />}
      <SuporteChat />
    </div>
  );
}
