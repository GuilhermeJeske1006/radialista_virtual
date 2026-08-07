"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import AppShell from "../../../components/AppShell";
import VoiceSelect from "../../../components/VoiceSelect";
import { apiFetch, ApiError } from "../../../lib/api";
import { setRadialistaAtualId } from "../../../lib/radialistas";
import { DIAS_SEMANA_LABEL, PROGRAMA_VAZIO, Programa, Radialista } from "../../../lib/types";

const inputClass =
  "w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:border-brand-300 focus:ring-2 focus:ring-brand-500/20";
const labelClass = "block text-sm font-medium text-gray-700 mb-1.5";

function semCamposSistema(r: Radialista) {
  const { id, wuzapi_token, ativo, ...dados } = r;
  return dados;
}

function formatarDias(dias: number[]): string {
  if (dias.length === 0) return "Todos os dias";
  return dias.map((d) => DIAS_SEMANA_LABEL[d]).join(", ");
}

export default function EditarRadialistaPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const radialistaId = Number(params.id);

  const [config, setConfig] = useState<Radialista | null>(null);
  const [programas, setProgramas] = useState<Programa[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [criandoPrograma, setCriandoPrograma] = useState(false);
  const [mensagem, setMensagem] = useState("");
  const [erro, setErro] = useState("");

  function carregarProgramas() {
    apiFetch<Programa[]>(`/config/radialistas/${radialistaId}/programas`)
      .then(setProgramas)
      .catch(() => setProgramas([]));
  }

  useEffect(() => {
    setRadialistaAtualId(radialistaId);
    apiFetch<Radialista>(`/config/radialistas/${radialistaId}`)
      .then(setConfig)
      .catch((err) => setErro(err instanceof ApiError ? err.message : "Erro ao carregar radialista"))
      .finally(() => setCarregando(false));
    carregarProgramas();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [radialistaId]);

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    if (!config) return;
    setSalvando(true);
    setErro("");
    setMensagem("");
    try {
      const atualizado = await apiFetch<Radialista>(`/config/radialistas/${radialistaId}`, {
        method: "PUT",
        body: JSON.stringify(semCamposSistema(config)),
      });
      setConfig(atualizado);
      setMensagem("Configuração salva.");
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao salvar");
    } finally {
      setSalvando(false);
    }
  }

  async function excluirRadialista() {
    if (!config) return;
    if (!confirm(`Excluir o radialista "${config.nome_locutor}"? Essa ação não pode ser desfeita.`)) return;
    try {
      await apiFetch(`/config/radialistas/${radialistaId}`, { method: "DELETE" });
      router.push("/dashboard");
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao excluir radialista");
    }
  }

  async function criarPrograma() {
    setCriandoPrograma(true);
    setErro("");
    try {
      const criado = await apiFetch<Programa>(`/config/radialistas/${radialistaId}/programas`, {
        method: "POST",
        body: JSON.stringify({ ...PROGRAMA_VAZIO, nome: "Novo programa" }),
      });
      router.push(`/dashboard/${radialistaId}/programas/${criado.id}`);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao criar programa");
      setCriandoPrograma(false);
    }
  }

  async function excluirPrograma(programa: Programa) {
    if (!confirm(`Excluir o programa "${programa.nome}"?`)) return;
    try {
      await apiFetch(`/config/programas/${programa.id}`, { method: "DELETE" });
      carregarProgramas();
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao excluir programa");
    }
  }

  if (carregando) {
    return (
      <AppShell title="Radialista">
        <p className="text-sm text-gray-500">Carregando...</p>
      </AppShell>
    );
  }

  if (!config) {
    return (
      <AppShell title="Radialista">
        <p className="text-sm text-red-600">{erro || "Radialista não encontrado."}</p>
        <Link href="/dashboard" className="text-sm text-brand-600 hover:underline mt-2 inline-block">
          Voltar para a lista
        </Link>
      </AppShell>
    );
  }

  return (
    <AppShell title={config.nome_locutor || "Radialista"} maxWidthClassName="max-w-4xl">
      <Link href="/dashboard" className="text-sm text-brand-600 hover:underline mb-4 inline-block">
        ← Todos os radialistas
      </Link>

      <div className="space-y-5">
        {erro && <p className="text-sm text-red-600">{erro}</p>}
        {mensagem && <p className="text-sm text-emerald-600">{mensagem}</p>}

        <div className="bg-white rounded-2xl border border-gray-200 shadow-theme-xs p-6">
          <div className="flex flex-col gap-1 mb-5 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-base font-semibold text-gray-900">Identidade do locutor</h2>
              <p className="text-sm text-gray-500">
                {config.wuzapi_token ? (
                  <>
                    WhatsApp conectado.{" "}
                    <Link href={`/onboarding?radialista=${radialistaId}`} className="text-brand-600 hover:underline">
                      Gerenciar conexão
                    </Link>
                  </>
                ) : (
                  <Link href={`/onboarding?radialista=${radialistaId}`} className="text-brand-600 hover:underline">
                    Conectar este radialista ao WhatsApp
                  </Link>
                )}
              </p>
            </div>
            <button
              type="button"
              onClick={excluirRadialista}
              className="text-xs font-medium text-red-600 hover:text-red-700 self-start sm:self-auto"
            >
              Excluir radialista
            </button>
          </div>

          <form onSubmit={salvar} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className={labelClass}>Nome do locutor</label>
                <input
                  className={inputClass}
                  value={config.nome_locutor}
                  onChange={(e) => setConfig({ ...config, nome_locutor: e.target.value })}
                />
              </div>
              <div>
                <label className={labelClass}>Voz</label>
                <VoiceSelect value={config.voz_id} onChange={(vozId) => setConfig({ ...config, voz_id: vozId })} />
              </div>
            </div>
            <div className="pt-2">
              <button
                type="submit"
                disabled={salvando}
                className="rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {salvando ? "Salvando..." : "Salvar"}
              </button>
            </div>
          </form>
        </div>

        <div className="bg-white rounded-2xl border border-gray-200 shadow-theme-xs p-6">
          <div className="flex items-center justify-between mb-1">
            <h2 className="text-base font-semibold text-gray-900">Programação</h2>
            <button
              type="button"
              onClick={criarPrograma}
              disabled={criandoPrograma}
              className="text-sm font-medium text-brand-600 hover:text-brand-700 disabled:opacity-60"
            >
              {criandoPrograma ? "Criando..." : "+ Novo programa"}
            </button>
          </div>
          <p className="text-sm text-gray-500 mb-5">
            Cada programa tem seu próprio tom, tópicos, músicas, notícias e regras de pesquisa, além do horário em
            que vai ao ar.
          </p>

          {programas.length === 0 ? (
            <p className="text-sm text-gray-500">Nenhum programa cadastrado ainda.</p>
          ) : (
            <div className="space-y-2">
              {programas.map((p) => (
                <div
                  key={p.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-gray-200 px-3 py-2.5"
                >
                  <Link href={`/dashboard/${radialistaId}/programas/${p.id}`} className="min-w-0">
                    <p className="text-sm font-medium text-gray-900 hover:text-brand-600">{p.nome}</p>
                    <p className="text-xs text-gray-500">
                      {formatarDias(p.dias_semana)} · {p.horario_inicio.slice(0, 5)} às {p.horario_fim.slice(0, 5)}
                      {!p.ativo && " · pausado"}
                    </p>
                  </Link>
                  <div className="flex items-center gap-3 shrink-0">
                    <Link
                      href={`/dashboard/${radialistaId}/programas/${p.id}`}
                      className="text-xs font-medium text-brand-600 hover:text-brand-700"
                    >
                      Editar
                    </Link>
                    <button
                      type="button"
                      onClick={() => excluirPrograma(p)}
                      className="text-xs font-medium text-red-600 hover:text-red-700"
                    >
                      Excluir
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
