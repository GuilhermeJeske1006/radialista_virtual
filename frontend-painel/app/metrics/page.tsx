"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "../../components/AppShell";
import { apiFetch, apiFetchDownload, ApiError } from "../../lib/api";
import { STATUS_HEX, STATUS_LABEL } from "../../lib/statusInteracao";
import { Radialista } from "../../lib/types";
import { LocufySpin } from "../../components/LocufyLogo";
import { GraficoBarras } from "../../components/GraficoBarras";

type MensagemPorDia = { data: string; total: number };

type Resumo = {
  total: number;
  por_status: Record<string, number>;
  ultimos_7_dias: number;
  ultimos_30_dias: number;
  mensagens_por_dia: MensagemPorDia[];
};

function StatCard({ label, valor }: { label: string; valor: number }) {
  return (
    <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-5">
      <p className="text-xs font-medium text-fg/65 uppercase tracking-wide">{label}</p>
      <p className="mt-2 font-display text-3xl font-bold text-fg">{valor.toLocaleString("pt-BR")}</p>
    </div>
  );
}

function BreakdownPorStatus({ porStatus, total }: { porStatus: Record<string, number>; total: number }) {
  const linhas = Object.entries(porStatus).sort(([, a], [, b]) => b - a);

  if (linhas.length === 0) {
    return <p className="text-sm text-fg/65">Nenhuma interação registrada ainda.</p>;
  }

  return (
    <div className="space-y-3">
      {linhas.map(([status, quantidade]) => {
        const participacao = total > 0 ? Math.round((quantidade / total) * 100) : 0;
        return (
          <div key={status} className="flex items-center gap-3">
            <span
              className="h-2.5 w-2.5 rounded-full shrink-0"
              style={{ backgroundColor: STATUS_HEX[status] ?? "#8a8471" }}
              aria-hidden
            />
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm text-fg truncate">{STATUS_LABEL[status] ?? status}</span>
                <span className="text-sm font-medium text-fg shrink-0">{quantidade.toLocaleString("pt-BR")}</span>
              </div>
              <div className="mt-1 h-1.5 rounded-full bg-bg overflow-hidden">
                <div
                  className="h-full rounded-full"
                  style={{ width: `${participacao}%`, backgroundColor: STATUS_HEX[status] ?? "#8a8471" }}
                />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

const OPCOES_PERIODO = [
  { valor: "7", label: "Últimos 7 dias" },
  { valor: "30", label: "Últimos 30 dias" },
  { valor: "90", label: "Últimos 90 dias" },
  { valor: "", label: "Tudo" },
];

export default function MetricsPage() {
  const [radialistas, setRadialistas] = useState<Radialista[]>([]);
  const [radialistaId, setRadialistaId] = useState<number | null>(null);
  const [resumo, setResumo] = useState<Resumo | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");
  const [periodoExport, setPeriodoExport] = useState("30");
  const [exportando, setExportando] = useState(false);

  async function exportarCsv() {
    setExportando(true);
    try {
      const params = new URLSearchParams();
      if (radialistaId !== null) params.set("radialista_id", String(radialistaId));
      if (periodoExport) params.set("dias", periodoExport);
      const hoje = new Date().toISOString().slice(0, 10);
      await apiFetchDownload(`/metrics/export?${params.toString()}`, `interacoes-${hoje}.csv`);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao exportar CSV");
    } finally {
      setExportando(false);
    }
  }

  useEffect(() => {
    apiFetch<Radialista[]>("/config/radialistas")
      .then((lista) => {
        setRadialistas(lista);
        if (lista[0]) setRadialistaId(lista[0].id);
        else setCarregando(false);
      })
      .catch((err) => {
        setErro(err instanceof ApiError ? err.message : "Erro ao carregar radialistas");
        setCarregando(false);
      });
  }, []);

  useEffect(() => {
    if (radialistaId === null) return;
    setCarregando(true);
    setErro("");
    apiFetch<Resumo>(`/metrics/summary?radialista_id=${radialistaId}`)
      .then(setResumo)
      .catch((err) => setErro(err instanceof ApiError ? err.message : "Erro ao carregar métricas"))
      .finally(() => setCarregando(false));
  }, [radialistaId]);

  return (
    <AppShell title="Métricas" maxWidthClassName="max-w-4xl">
      <p className="text-sm text-fg/65 mb-5">
        Números agregados das interações. Pra ver as conversas mensagem a mensagem,{" "}
        <Link href="/conversas" className="text-amber-text hover:text-amber-dim font-medium">
          acesse Conversas
        </Link>
        .
      </p>
      <div className="flex flex-wrap items-end justify-between gap-4 mb-5">
        {radialistas.length > 1 ? (
          <div>
            <label className="block text-sm font-medium text-fg/80 mb-1.5">Radialista</label>
            <select
              aria-label="Radialista"
              value={radialistaId ?? ""}
              onChange={(e) => setRadialistaId(Number(e.target.value))}
              className="rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
            >
              {radialistas.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.nome_locutor || `Radialista #${r.id}`}
                </option>
              ))}
            </select>
          </div>
        ) : (
          <span />
        )}

        {radialistas.length > 0 && (
          <div className="flex items-end gap-2">
            <div>
              <label className="block text-sm font-medium text-fg/80 mb-1.5">Período do CSV</label>
              <select
                aria-label="Período do CSV"
                value={periodoExport}
                onChange={(e) => setPeriodoExport(e.target.value)}
                className="rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
              >
                {OPCOES_PERIODO.map((opcao) => (
                  <option key={opcao.valor} value={opcao.valor}>
                    {opcao.label}
                  </option>
                ))}
              </select>
            </div>
            <button
              type="button"
              onClick={exportarCsv}
              disabled={exportando}
              className="rounded-lg border border-border-strong px-4 py-2 text-sm font-medium text-fg hover:bg-paper/5 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {exportando ? "Exportando..." : "Exportar CSV"}
            </button>
          </div>
        )}
      </div>

      {erro && <p className="text-sm text-rust-text mb-4">{erro}</p>}

      {carregando ? (
        <p className="flex items-center gap-2 text-sm text-fg/65">
          <LocufySpin size={16} /> Carregando...
        </p>
      ) : radialistas.length === 0 ? (
        <p className="text-sm text-fg/65">Cadastre um radialista para acompanhar as métricas.</p>
      ) : resumo ? (
        <div className="space-y-5">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <StatCard label="Total de interações" valor={resumo.total} />
            <StatCard label="Últimos 7 dias" valor={resumo.ultimos_7_dias} />
            <StatCard label="Últimos 30 dias" valor={resumo.ultimos_30_dias} />
          </div>

          <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6">
            <h2 className="font-display text-base font-bold text-fg mb-1">Mensagens por dia</h2>
            <p className="text-xs text-fg/65 mb-5">Últimos 30 dias.</p>
            {resumo.mensagens_por_dia.every((ponto) => ponto.total === 0) ? (
              <p className="text-sm text-fg/65">Nenhuma mensagem nos últimos 30 dias.</p>
            ) : (
              <GraficoBarras serie={resumo.mensagens_por_dia} />
            )}
          </div>

          <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6">
            <h2 className="font-display text-base font-bold text-fg mb-4">Por status</h2>
            <BreakdownPorStatus porStatus={resumo.por_status} total={resumo.total} />
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}
