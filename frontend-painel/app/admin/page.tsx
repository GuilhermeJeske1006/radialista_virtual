"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AdminShell from "../../components/AdminShell";
import { LocufySpin } from "../../components/LocufyLogo";
import { apiFetch, ApiError } from "../../lib/api";
import { formatarReais } from "../../lib/planos";
import { AdminEmpresasPaginadas, AdminOverview } from "../../lib/types";

const STATUS_LABEL: Record<string, string> = {
  trial: "Trial",
  ativo: "Ativo",
  inadimplente: "Inadimplente",
  cancelado: "Cancelado",
};

const STATUS_CLASSE: Record<string, string> = {
  trial: "bg-amber/10 text-amber-text",
  ativo: "bg-teal/10 text-teal-text",
  inadimplente: "bg-rust/10 text-rust-text",
  cancelado: "bg-paper text-fg/65",
};

function formatarData(iso: string): string {
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "short", year: "numeric" });
}

export default function AdminPage() {
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [empresas, setEmpresas] = useState<AdminEmpresasPaginadas | null>(null);
  const [pagina, setPagina] = useState(1);
  const [busca, setBusca] = useState("");
  const [buscaAplicada, setBuscaAplicada] = useState("");
  const [statusFiltro, setStatusFiltro] = useState("");
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");

  useEffect(() => {
    apiFetch<AdminOverview>("/admin/overview")
      .then(setOverview)
      .catch((err) => setErro(err instanceof ApiError ? err.message : "Erro ao carregar métricas"));
  }, []);

  useEffect(() => {
    setCarregando(true);
    setErro("");
    const params = new URLSearchParams({ pagina: String(pagina), tamanho_pagina: "20" });
    if (buscaAplicada) params.set("busca", buscaAplicada);
    if (statusFiltro) params.set("status", statusFiltro);

    apiFetch<AdminEmpresasPaginadas>(`/admin/empresas?${params.toString()}`)
      .then(setEmpresas)
      .catch((err) => setErro(err instanceof ApiError ? err.message : "Erro ao carregar empresas"))
      .finally(() => setCarregando(false));
  }, [pagina, buscaAplicada, statusFiltro]);

  const mrrTotal = overview ? overview.mrr_planos + overview.mrr_agentes_extras : 0;

  return (
    <AdminShell title="Administração" maxWidthClassName="max-w-6xl">
      <div className="space-y-5">
        {erro && <p className="text-sm text-rust-text">{erro}</p>}

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          <MetricaCard rotulo="Empresas" valor={overview ? String(overview.total_empresas) : "—"} />
          <MetricaCard rotulo="MRR estimado" valor={overview ? `R$ ${formatarReais(mrrTotal)}` : "—"} />
          <MetricaCard rotulo="Novas (30d)" valor={overview ? String(overview.novas_empresas_30_dias) : "—"} />
          <MetricaCard rotulo="Usuários ativos" valor={overview ? String(overview.total_usuarios_ativos) : "—"} />
          <MetricaCard rotulo="Mensagens (30d)" valor={overview ? String(overview.mensagens_30_dias) : "—"} />
        </div>

        {overview && (
          <div className="grid sm:grid-cols-2 gap-3">
            <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6">
              <h2 className="font-display text-sm font-bold text-fg mb-3">Empresas por status</h2>
              <div className="space-y-2">
                {Object.entries(overview.por_status).map(([status, total]) => (
                  <div key={status} className="flex items-center justify-between text-sm">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_CLASSE[status] ?? "bg-paper text-fg/65"}`}>
                      {STATUS_LABEL[status] ?? status}
                    </span>
                    <span className="text-fg/80 font-medium">{total}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6">
              <h2 className="font-display text-sm font-bold text-fg mb-3">Contas ativas por plano</h2>
              <div className="space-y-2">
                {Object.entries(overview.por_plano).map(([plano, total]) => (
                  <div key={plano} className="flex items-center justify-between text-sm">
                    <span className="text-fg/70 capitalize">{plano}</span>
                    <span className="text-fg/80 font-medium">{total}</span>
                  </div>
                ))}
                {Object.keys(overview.por_plano).length === 0 && (
                  <p className="text-sm text-fg/65">Nenhuma conta ativa ainda.</p>
                )}
              </div>
            </div>
          </div>
        )}

        <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-4">
            <h2 className="font-display text-base font-bold text-fg">Empresas</h2>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                setPagina(1);
                setBuscaAplicada(busca.trim());
              }}
              className="flex gap-2"
            >
              <input
                type="text"
                placeholder="Buscar por nome da rádio..."
                value={busca}
                onChange={(e) => setBusca(e.target.value)}
                className="rounded-lg border border-border-strong bg-bg px-3 py-1.5 text-sm text-fg placeholder:text-fg/65 focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
              />
              <select
                aria-label="Filtrar por status"
                value={statusFiltro}
                onChange={(e) => {
                  setPagina(1);
                  setStatusFiltro(e.target.value);
                }}
                className="rounded-lg border border-border-strong bg-bg px-2.5 py-1.5 text-sm text-fg"
              >
                <option value="">Todos os status</option>
                {Object.entries(STATUS_LABEL).map(([valor, label]) => (
                  <option key={valor} value={valor}>
                    {label}
                  </option>
                ))}
              </select>
              <button
                type="submit"
                className="rounded-lg border border-border-strong px-3 py-1.5 text-sm font-medium text-fg hover:bg-paper/5"
              >
                Buscar
              </button>
            </form>
          </div>

          {carregando ? (
            <p className="flex items-center gap-2 text-sm text-fg/65">
              <LocufySpin size={16} /> Carregando...
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-fg/65 border-b border-border">
                    <th className="py-2 pr-3">Rádio</th>
                    <th className="py-2 pr-3">Admin</th>
                    <th className="py-2 pr-3">Plano</th>
                    <th className="py-2 pr-3">Status</th>
                    <th className="py-2 pr-3">Usuários</th>
                    <th className="py-2 pr-3">Agentes</th>
                    <th className="py-2 pr-3">Criada em</th>
                  </tr>
                </thead>
                <tbody>
                  {empresas?.empresas.map((empresa) => (
                    <tr key={empresa.id} className="border-b border-border last:border-0 hover:bg-paper/5">
                      <td className="py-2.5 pr-3">
                        <Link href={`/admin/empresas/${empresa.id}`} className="font-medium text-fg hover:text-amber-text">
                          {empresa.nome_radio || `Empresa #${empresa.id}`}
                        </Link>
                      </td>
                      <td className="py-2.5 pr-3 text-fg/70">{empresa.email_admin ?? "—"}</td>
                      <td className="py-2.5 pr-3 capitalize text-fg/70">{empresa.plano}</td>
                      <td className="py-2.5 pr-3">
                        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_CLASSE[empresa.plano_status] ?? "bg-paper text-fg/65"}`}>
                          {STATUS_LABEL[empresa.plano_status] ?? empresa.plano_status}
                        </span>
                      </td>
                      <td className="py-2.5 pr-3 text-fg/70">{empresa.usuarios_ativos}</td>
                      <td className="py-2.5 pr-3 text-fg/70">{empresa.agentes}</td>
                      <td className="py-2.5 pr-3 text-fg/70">{formatarData(empresa.criado_em)}</td>
                    </tr>
                  ))}
                  {empresas?.empresas.length === 0 && (
                    <tr>
                      <td colSpan={7} className="py-6 text-center text-fg/65">
                        Nenhuma empresa encontrada.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}

          {empresas && empresas.total_paginas > 1 && (
            <div className="flex items-center justify-between pt-4 text-xs text-fg/65">
              <button
                onClick={() => setPagina((p) => p - 1)}
                disabled={pagina <= 1 || carregando}
                className="disabled:opacity-40 hover:text-fg"
              >
                ‹ Anterior
              </button>
              <span>
                {empresas.pagina}/{empresas.total_paginas}
              </span>
              <button
                onClick={() => setPagina((p) => p + 1)}
                disabled={pagina >= empresas.total_paginas || carregando}
                className="disabled:opacity-40 hover:text-fg"
              >
                Próxima ›
              </button>
            </div>
          )}
        </div>
      </div>
    </AdminShell>
  );
}

function MetricaCard({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-4">
      <p className="text-xs text-fg/65 mb-1">{rotulo}</p>
      <p className="font-display text-xl font-bold text-fg">{valor}</p>
    </div>
  );
}
