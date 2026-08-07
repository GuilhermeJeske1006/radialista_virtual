"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "../../components/AppShell";
import { apiFetch, ApiError } from "../../lib/api";
import { DIAS_SEMANA_LABEL, Programa, RADIALISTA_VAZIO, Radialista } from "../../lib/types";
import { setRadialistaAtualId } from "../../lib/radialistas";
import { OndaLed, OndaSpin } from "../../components/OndaLogo";

function formatarDias(dias: number[], dataEspecifica?: string | null): string {
  if (dataEspecifica) return `Avulso em ${dataEspecifica.split("-").reverse().join("/")}`;
  if (dias.length === 0) return "Todos os dias";
  return dias.map((d) => DIAS_SEMANA_LABEL[d]).join(", ");
}

export default function DashboardPage() {
  const [radialistas, setRadialistas] = useState<Radialista[]>([]);
  const [programasPorRadialista, setProgramasPorRadialista] = useState<Record<number, Programa[]>>({});
  const [carregando, setCarregando] = useState(true);
  const [criando, setCriando] = useState(false);
  const [erro, setErro] = useState("");
  const [mensagemUpgrade, setMensagemUpgrade] = useState("");

  function carregar() {
    setCarregando(true);
    apiFetch<Radialista[]>("/config/radialistas")
      .then(async (lista) => {
        setRadialistas(lista);
        const entradas = await Promise.all(
          lista.map(async (r) => {
            try {
              const programas = await apiFetch<Programa[]>(`/config/radialistas/${r.id}/programas`);
              return [r.id, programas] as const;
            } catch {
              return [r.id, []] as const;
            }
          })
        );
        setProgramasPorRadialista(Object.fromEntries(entradas));
      })
      .catch((err) => setErro(err instanceof ApiError ? err.message : "Erro ao carregar radialistas"))
      .finally(() => setCarregando(false));
  }

  useEffect(() => {
    carregar();
  }, []);

  async function criarRadialista() {
    setCriando(true);
    setErro("");
    try {
      const criado = await apiFetch<Radialista>("/config/radialistas", {
        method: "POST",
        body: JSON.stringify({ ...RADIALISTA_VAZIO, nome_locutor: "Novo radialista" }),
      });
      setRadialistaAtualId(criado.id);
      window.location.href = `/radialista/${criado.id}`;
    } catch (err) {
      if (err instanceof ApiError && err.status === 402) {
        setMensagemUpgrade(err.message);
      } else {
        setErro(err instanceof ApiError ? err.message : "Erro ao criar radialista");
      }
      setCriando(false);
    }
  }

  return (
    <AppShell title="Radialistas" maxWidthClassName="max-w-4xl">
      <div className="flex items-center justify-between mb-5">
        <p className="text-sm text-fg/55">Seus radialistas e a programação cadastrada de cada um.</p>
        <button
          type="button"
          onClick={criarRadialista}
          disabled={criando}
          className="rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-ink hover:bg-brand-600 disabled:opacity-60"
        >
          {criando ? "Criando..." : "+ Novo radialista"}
        </button>
      </div>

      {erro && <p className="text-sm text-rust mb-4">{erro}</p>}

      {carregando ? (
        <p className="flex items-center gap-2 text-sm text-fg/55">
          <OndaSpin size={16} /> Carregando...
        </p>
      ) : radialistas.length === 0 ? (
        <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6">
          <p className="text-sm text-fg/55">Nenhum radialista ainda. Crie o primeiro para começar.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {radialistas.map((r) => {
            const programas = programasPorRadialista[r.id] ?? [];
            return (
              <Link
                key={r.id}
                href={`/radialista/${r.id}`}
                onClick={() => setRadialistaAtualId(r.id)}
                className="block bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-5 hover:border-amber/40 transition-colors"
              >
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div>
                    <h2 className="font-display text-base font-bold text-fg">{r.nome_locutor || `Radialista #${r.id}`}</h2>
                    <p className="flex items-center gap-1.5 text-xs text-fg/55 mt-1">
                      <OndaLed color={r.wuzapi_token ? "teal" : "amber"} pulse={false} />
                      {r.wuzapi_token ? "WhatsApp conectado" : "WhatsApp não conectado"}
                    </p>
                  </div>
                  <span className="text-xs font-medium text-amber shrink-0">Editar →</span>
                </div>

                {programas.length === 0 ? (
                  <p className="text-sm text-fg/35">Nenhum programa cadastrado.</p>
                ) : (
                  <ul className="space-y-1.5">
                    {programas.map((p) => (
                      <li key={p.id} className="flex flex-wrap items-center gap-2 text-sm">
                        <span className={`font-medium ${p.ativo ? "text-fg" : "text-fg/35"}`}>{p.nome}</span>
                        <span className="text-xs text-fg/45 font-mono">
                          {formatarDias(p.dias_semana, p.data_especifica)} · {p.horario_inicio.slice(0, 5)} às{" "}
                          {p.horario_fim.slice(0, 5)}
                        </span>
                        {!p.ativo && (
                          <span className="rounded-full bg-paper/5 px-2 py-0.5 text-xs font-medium text-fg/45">
                            Pausado
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </Link>
            );
          })}
        </div>
      )}

      {mensagemUpgrade && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/50 px-4"
          onClick={() => setMensagemUpgrade("")}
        >
          <div
            className="w-full max-w-sm rounded-2xl border border-border-strong bg-surface p-6 shadow-theme-xs"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="font-display text-base font-bold text-fg mb-2">Limite do plano atingido</h2>
            <p className="text-sm text-fg/70 mb-5">{mensagemUpgrade}</p>
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setMensagemUpgrade("")}
                className="rounded-lg px-4 py-2.5 text-sm font-medium text-fg/60 hover:text-fg"
              >
                Fechar
              </button>
              <Link
                href="/billing"
                className="rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-ink hover:bg-brand-600"
              >
                Fazer upgrade
              </Link>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
