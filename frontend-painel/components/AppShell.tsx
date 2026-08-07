"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import Sidebar from "./Sidebar";
import { clearToken } from "../lib/auth";
import { OndaLed, OndaMark } from "./OndaLogo";
import ThemeToggle from "./ThemeToggle";

const MOBILE_LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/radialista", label: "Radialistas" },
  { href: "/programas", label: "Programas" },
  { href: "/onboarding", label: "WhatsApp" },
  { href: "/live", label: "Ao Vivo" },
  { href: "/billing", label: "Assinatura" },
  { href: "/configuracoes", label: "Configuração" },
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

  function sair() {
    clearToken();
    router.push("/login");
  }

  return (
    <div className="min-h-screen bg-bg">
      <Sidebar />
      <div className="md:pl-72.5 flex flex-col min-h-screen">
        <header className="sticky top-0 z-10 bg-bg/90 backdrop-blur border-b border-border">
          <div className="flex items-center justify-between h-16 px-4 sm:px-6">
            <div className="flex items-center gap-3 min-w-0">
              <OndaMark size={22} className="shrink-0 md:hidden" />
              <h1 className="font-display text-xl font-bold text-fg truncate">{title}</h1>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              <span className="hidden sm:flex items-center gap-2 rounded-full border border-border-strong px-3 py-1.5 font-mono text-[11px] tracking-wider text-fg/70">
                <OndaLed color="amber" />
                NO AR
              </span>
              <ThemeToggle />
              <Link
                href="/perfil"
                title="Perfil"
                className="flex h-8 w-8 items-center justify-center rounded-full bg-amber/10 text-amber text-xs font-semibold hover:bg-amber/20"
              >
                RV
              </Link>
            
            </div>
          </div>
          <nav className="md:hidden flex gap-4 overflow-x-auto px-4 sm:px-6 pb-3 -mt-1">
            {MOBILE_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={`text-sm font-medium whitespace-nowrap pb-1 border-b-2 ${
                  pathname === link.href
                    ? "border-amber text-amber"
                    : "border-transparent text-fg/55"
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
    </div>
  );
}
