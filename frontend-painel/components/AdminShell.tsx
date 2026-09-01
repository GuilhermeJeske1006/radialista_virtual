"use client";

import { useRouter } from "next/navigation";
import { apiFetch } from "../lib/api";
import { limparSuperAdminCache, useSuperAdmin } from "../lib/useSuperAdmin";
import { LocufyMark } from "./LocufyLogo";
import ThemeToggle from "./ThemeToggle";

// Layout minimo pras paginas /admin/* -- de proposito nao usa AppShell (sidebar/topbar do
// painel de radio, NotificationBell, OnboardingTour, SuporteChat): super-admin e' um perfil
// isolado do tenant, essa chrome toda e' do produto de radio e nao faz sentido aqui.
export default function AdminShell({
  title,
  children,
  maxWidthClassName = "max-w-6xl",
}: {
  title: string;
  children: React.ReactNode;
  maxWidthClassName?: string;
}) {
  const admin = useSuperAdmin();
  const router = useRouter();

  function sair() {
    apiFetch("/admin/auth/logout", { method: "POST" }).catch(() => {});
    limparSuperAdminCache();
    router.push("/login");
  }

  return (
    <div className="min-h-screen bg-bg">
      <header className="sticky top-0 z-10 bg-bg/90 backdrop-blur border-b border-border">
        <div className={`flex items-center justify-between h-16 px-4 sm:px-6 ${maxWidthClassName} mx-auto`}>
          <div className="flex items-center gap-3 min-w-0">
            <LocufyMark size={22} className="shrink-0" />
            <h1 className="font-display text-xl font-bold text-fg truncate">{title}</h1>
            <span className="rounded-full bg-amber/10 px-2 py-0.5 text-[11px] font-semibold tracking-wide text-amber-text shrink-0">
              ADMIN
            </span>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            {admin && <span className="hidden sm:inline text-sm text-fg/65 truncate max-w-[16rem]">{admin.nome || admin.email}</span>}
            <ThemeToggle />
            <button
              onClick={sair}
              className="rounded-lg border border-border-strong px-3 py-1.5 text-xs font-medium text-fg hover:bg-paper/5"
            >
              Sair
            </button>
          </div>
        </div>
      </header>
      <main className="px-4 sm:px-6 py-6">
        <div className={`${maxWidthClassName} mx-auto`}>{children}</div>
      </main>
    </div>
  );
}
