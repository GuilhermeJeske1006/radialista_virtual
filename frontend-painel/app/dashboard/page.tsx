"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "../../components/AppShell";
import { apiFetch, ApiError } from "../../lib/api";
import { Conta, Radialista } from "../../lib/types";
import { OndaLed, OndaSpin } from "../../components/OndaLogo";

const ATALHOS = [
  {
    href: "/radialista",
    label: "Radialistas",
    descricao: "Gerenciar locutores e programação",
  },
  {
    href: "/onboarding",
    label: "WhatsApp",
    descricao: "Conectar ou revisar conexão",
  },
  {
    href: "/live",
    label: "Ao Vivo",
    descricao: "Acompanhar programas no ar",
  },
  {
    href: "/billing",
    label: "Assinatura",
    descricao: "Plano e cobrança",
  },
  {
    href: "/perfil",
    label: "Perfil",
    descricao: "Dados da conta",
  },
];

export default function DashboardPage() {
  const [conta, setConta] = useState<Conta | null>(null);
  const [radialistas, setRadialistas] = useState<Radialista[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");

  useEffect(() => {
    Promise.all([apiFetch<Conta>("/auth/me"), apiFetch<Radialista[]>("/config/radialistas")])
      .then(([c, r]) => {
        setConta(c);
        setRadialistas(r);
      })
      .catch((err) => setErro(err instanceof ApiError ? err.message : "Erro ao carregar painel"))
      .finally(() => setCarregando(false));
  }, []);

  const conectados = radialistas.filter((r) => r.wuzapi_token).length;

  return (
    <AppShell title="Dashboard" maxWidthClassName="max-w-4xl">
      {erro && <p className="text-sm text-rust mb-4">{erro}</p>}

      {carregando ? (
        <p className="flex items-center gap-2 text-sm text-fg/55">
          <OndaSpin size={16} /> Carregando...
        </p>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
            <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-5">
              <p className="text-xs font-medium uppercase tracking-wide text-fg/45 mb-1">Radialistas</p>
              <p className="font-display text-2xl font-bold text-fg">{radialistas.length}</p>
            </div>
            <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-5">
              <p className="text-xs font-medium uppercase tracking-wide text-fg/45 mb-1">WhatsApp conectados</p>
              <p className="flex items-center gap-2 font-display text-2xl font-bold text-fg">
                <OndaLed color={conectados > 0 ? "teal" : "amber"} pulse={false} />
                {conectados} / {radialistas.length}
              </p>
            </div>
            <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-5">
              <p className="text-xs font-medium uppercase tracking-wide text-fg/45 mb-1">Plano</p>
              <p className="font-display text-2xl font-bold text-fg capitalize">{conta?.plano ?? "-"}</p>
              <p className="text-xs text-fg/45 mt-0.5 capitalize">{conta?.plano_status ?? ""}</p>
            </div>
          </div>

          <p className="text-sm font-medium text-fg/55 mb-3">Acesso rápido</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {ATALHOS.map((a) => (
              <Link
                key={a.href}
                href={a.href}
                className="flex items-center justify-between gap-3 bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-5 hover:border-amber/40 transition-colors"
              >
                <div>
                  <p className="font-display text-sm font-bold text-fg">{a.label}</p>
                  <p className="text-sm text-fg/55 mt-0.5">{a.descricao}</p>
                </div>
                <span className="text-amber shrink-0">→</span>
              </Link>
            ))}
          </div>
        </>
      )}
    </AppShell>
  );
}
