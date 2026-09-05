"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import Sidebar from "./Sidebar";
import NotificationBell from "./NotificationBell";
import OnboardingTour from "./OnboardingTour";
import SuporteChat from "./SuporteChat";
import { apiFetch } from "../lib/api";
import { limparContaCache, useConta } from "../lib/useConta";
import { useConfiguracaoInicialCompleta } from "../lib/useConfiguracaoInicial";
import { LocufyLed, LocufyMark } from "./LocufyLogo";
import ThemeToggle from "./ThemeToggle";

const INTERVALO_NO_AR_MS = 30_000;

function useNoAr() {
  const [noAr, setNoAr] = useState(false);

  useEffect(() => {
    function buscar() {
      apiFetch<{ no_ar: boolean }>("/live/no-ar")
        .then((r) => setNoAr(r.no_ar))
        .catch(() => {
          // ignora falha isolada, mantem o ultimo estado conhecido
        });
    }
    buscar();
    const intervalo = setInterval(buscar, INTERVALO_NO_AR_MS);
    return () => clearInterval(intervalo);
  }, []);

  return noAr;
}

const MOBILE_LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/radialista", label: "Radialistas", numeroSetup: 1 },
  { href: "/programas", label: "Programas", numeroSetup: 2 },
  { href: "/programacao", label: "Grade" },
  { href: "/vinhetagem", label: "Vinhetagem" },
  { href: "/live", label: "Ao Vivo" },
  { href: "/metrics", label: "Métricas" },
  { href: "/conversas", label: "Conversas", numeroSetup: 3 },
  { href: "/billing", label: "Assinatura", adminOnly: true },
  { href: "/equipe", label: "Equipe", adminOnly: true },
  { href: "/configuracoes", label: "Dados da rádio" },
  { href: "/perfil", label: "Perfil" },
];

export default function AppShell({
  title,
  children,
  maxWidthClassName = "max-w-4xl",
}: {
  title: string;
  children: React.ReactNode;
  maxWidthClassName?: string;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const conta = useConta();
  const noAr = useNoAr();
  const setupCompleto = useConfiguracaoInicialCompleta();
  const mobileLinks = MOBILE_LINKS.filter((link) => !link.adminOnly || conta?.role === "admin").map((link) =>
    link.numeroSetup && !setupCompleto ? { ...link, label: `${link.numeroSetup}. ${link.label}` } : link
  );
  const sidebarColapsada = pathname === "/live";

  function sair() {
    apiFetch("/auth/logout", { method: "POST" }).catch(() => {});
    limparContaCache();
    router.push("/login");
  }

  return (
    <div className="min-h-screen bg-bg">
      <Sidebar />
      <div className={`flex flex-col min-h-screen transition-[padding] duration-150 ${sidebarColapsada ? "md:pl-20" : "md:pl-72.5"}`}>
        <header className="sticky top-0 z-10 bg-bg/90 backdrop-blur border-b border-border">
          <div className="flex items-center justify-between h-16 px-4 sm:px-6">
            <div className="flex items-center gap-3 min-w-0">
              <LocufyMark size={22} className="shrink-0 md:hidden" />
              <h1 className="font-display text-xl font-bold text-fg truncate">{title}</h1>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              <span
                className={`hidden sm:flex items-center gap-2 rounded-full border border-border-strong px-3 py-1.5 font-mono text-[11px] tracking-wider ${
                  noAr ? "text-fg/70" : "text-fg/40"
                }`}
                title={noAr ? "A rádio está transmitindo ao vivo agora" : "Nenhum programa no ar agora"}
              >
                <LocufyLed color={noAr ? "rust" : "amber"} pulse={noAr} />
                {noAr ? "NO AR" : "FORA DO AR"}
              </span>
              <ThemeToggle />
              <NotificationBell />
              <Link
                href="/perfil"
                title="Perfil"
                className="flex h-8 w-8 items-center justify-center rounded-full bg-amber/10 text-amber-text text-xs font-semibold hover:bg-amber/20"
              >
                RV
              </Link>
            
            </div>
          </div>
          <nav className="md:hidden flex gap-4 overflow-x-auto px-4 sm:px-6 pb-3 -mt-1">
            {mobileLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={`text-sm font-medium whitespace-nowrap pb-1 border-b-2 ${
                  pathname === link.href
                    ? "border-amber text-amber-text"
                    : "border-transparent text-fg/65"
                }`}
              >
                {link.label}
              </Link>
            ))}
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
