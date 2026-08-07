"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "../../components/AppShell";
import { apiFetch, ApiError } from "../../lib/api";
import { DIAS_SEMANA_LABEL, Programa, RADIALISTA_VAZIO, Radialista } from "../../lib/types";
import { setRadialistaAtualId } from "../../lib/radialistas";

function formatarDias(dias: number[]): string {
  if (dias.length === 0) return "Todos os dias";
  return dias.map((d) => DIAS_SEMANA_LABEL[d]).join(", ");
}

export default function DashboardPage() {
  const [radialistas, setRadialistas] = useState<Radialista[]>([]);
  const [programasPorRadialista, setProgramasPorRadialista] = useState<Record<number, Programa[]>>({});
  const [carregando, setCarregando] = useState(true);
  const [criando, setCriando] = useState(false);
  const [erro, setErro] = useState("");

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
      window.location.href = `/dashboard/${criado.id}`;
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao criar radialista");
      setCriando(false);
    }
  }

  return (
    <AppShell title="Radialistas" maxWidthClassName="max-w-4xl">
      <div className="flex items-center justify-between mb-5">
        <p className="text-sm text-gray-500">Seus radialistas e a programação cadastrada de cada um.</p>
        <button
          type="button"
          onClick={criarRadialista}
          disabled={criando}
          className="rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-60"
        >
          {criando ? "Criando..." : "+ Novo radialista"}
        </button>
      </div>

      {erro && <p className="text-sm text-red-600 mb-4">{erro}</p>}

      {carregando ? (
        <p className="text-sm text-gray-500">Carregando...</p>
      ) : radialistas.length === 0 ? (
        <div className="bg-white rounded-2xl border border-gray-200 shadow-theme-xs p-6">
          <p className="text-sm text-gray-500">Nenhum radialista ainda. Crie o primeiro para começar.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {radialistas.map((r) => {
            const programas = programasPorRadialista[r.id] ?? [];
            return (
              <Link
                key={r.id}
                href={`/dashboard/${r.id}`}
                onClick={() => setRadialistaAtualId(r.id)}
                className="block bg-white rounded-2xl border border-gray-200 shadow-theme-xs p-5 hover:border-brand-300 transition-colors"
              >
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div>
                    <h2 className="text-base font-semibold text-gray-900">{r.nome_locutor || `Radialista #${r.id}`}</h2>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {r.wuzapi_token ? "WhatsApp conectado" : "WhatsApp não conectado"}
                    </p>
                  </div>
                  <span className="text-xs font-medium text-brand-600 shrink-0">Editar →</span>
                </div>

                {programas.length === 0 ? (
                  <p className="text-sm text-gray-400">Nenhum programa cadastrado.</p>
                ) : (
                  <ul className="space-y-1.5">
                    {programas.map((p) => (
                      <li key={p.id} className="flex flex-wrap items-center gap-2 text-sm">
                        <span className={`font-medium ${p.ativo ? "text-gray-900" : "text-gray-400"}`}>{p.nome}</span>
                        <span className="text-xs text-gray-500">
                          {formatarDias(p.dias_semana)} · {p.horario_inicio.slice(0, 5)} às {p.horario_fim.slice(0, 5)}
                        </span>
                        {!p.ativo && (
                          <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-500">
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
    </AppShell>
  );
}
