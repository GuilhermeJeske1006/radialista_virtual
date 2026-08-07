"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import VoiceSelect from "./VoiceSelect";
import { apiFetch, ApiError } from "../lib/api";
import { setRadialistaAtualId } from "../lib/radialistas";
import { DIAS_SEMANA_LABEL, PROGRAMA_VAZIO, Programa, Radialista } from "../lib/types";
import { OndaSpin } from "./OndaLogo";

const inputClass =
  "w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg placeholder:text-fg/35 focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20";
const labelClass = "block text-sm font-medium text-fg/80 mb-1.5";

function semCamposSistema(r: Radialista) {
  const { id, wuzapi_token, ativo, ...dados } = r;
  return dados;
}

function formatarDias(dias: number[], dataEspecifica?: string | null): string {
  if (dataEspecifica) return `Avulso em ${dataEspecifica.split("-").reverse().join("/")}`;
  if (dias.length === 0) return "Todos os dias";
  return dias.map((d) => DIAS_SEMANA_LABEL[d]).join(", ");
}

type EditarRadialistaFormProps = {
  radialistaId: number;
  onSalvo?: (radialista: Radialista) => void;
  onExcluido?: () => void;
  /** quando definido, "Editar"/nome do programa e "+ Novo programa" chamam isso em vez de navegar */
  onAbrirPrograma?: (programaId: number) => void;
};

export default function EditarRadialistaForm({
  radialistaId,
  onSalvo,
  onExcluido,
  onAbrirPrograma,
}: EditarRadialistaFormProps) {
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
    setCarregando(true);
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
      onSalvo?.(atualizado);
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
      onExcluido?.();
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
      if (onAbrirPrograma) {
        carregarProgramas();
        onAbrirPrograma(criado.id);
      } else {
        window.location.href = `/radialista/${radialistaId}/programas/${criado.id}`;
      }
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao criar programa");
    } finally {
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
      <p className="flex items-center gap-2 text-sm text-fg/55">
        <OndaSpin size={16} /> Carregando...
      </p>
    );
  }

  if (!config) {
    return <p className="text-sm text-rust">{erro || "Radialista não encontrado."}</p>;
  }

  return (
    <div className="space-y-5">
      {erro && <p className="text-sm text-rust">{erro}</p>}
      {mensagem && <p className="text-sm text-teal">{mensagem}</p>}

      <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6">
        <div className="flex flex-col gap-1 mb-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="font-display text-base font-bold text-fg">Identidade do locutor</h2>
            <p className="text-sm text-fg/55">
              {config.wuzapi_token ? (
                <>
                  WhatsApp conectado.{" "}
                  <Link href={`/onboarding?radialista=${radialistaId}`} className="text-amber hover:underline">
                    Gerenciar conexão
                  </Link>
                </>
              ) : (
                <Link href={`/onboarding?radialista=${radialistaId}`} className="text-amber hover:underline">
                  Conectar este radialista ao WhatsApp
                </Link>
              )}
            </p>
          </div>
          <button
            type="button"
            onClick={excluirRadialista}
            className="text-xs font-medium text-rust hover:text-rust/80 self-start sm:self-auto"
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
          <div>
            <label className={labelClass}>Personalidade</label>
            <textarea
              className={inputClass}
              rows={4}
              placeholder="Descreva como o locutor deve se comportar: personalidade, características, jeito de falar, humor, etc."
              value={config.personalidade}
              onChange={(e) => setConfig({ ...config, personalidade: e.target.value })}
            />
          </div>
          <div className="pt-2">
            <button
              type="submit"
              disabled={salvando}
              className="rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-ink hover:bg-brand-600 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {salvando ? "Salvando..." : "Salvar"}
            </button>
          </div>
        </form>
      </div>

      <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6">
        <div className="flex items-center justify-between mb-1">
          <h2 className="font-display text-base font-bold text-fg">Programação</h2>
          <button
            type="button"
            onClick={criarPrograma}
            disabled={criandoPrograma}
            className="text-sm font-medium text-amber hover:text-amber-dim disabled:opacity-60"
          >
            {criandoPrograma ? "Criando..." : "+ Novo programa"}
          </button>
        </div>
        <p className="text-sm text-fg/55 mb-5">
          Cada programa tem seu próprio tom, tópicos, músicas, notícias e regras de pesquisa, além do horário em que
          vai ao ar.
        </p>

        {programas.length === 0 ? (
          <p className="text-sm text-fg/55">Nenhum programa cadastrado ainda.</p>
        ) : (
          <div className="space-y-2">
            {programas.map((p) => (
              <div
                key={p.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border-strong px-3 py-2.5"
              >
                {onAbrirPrograma ? (
                  <button type="button" onClick={() => onAbrirPrograma(p.id)} className="min-w-0 text-left">
                    <p className="text-sm font-medium text-fg hover:text-amber">{p.nome}</p>
                    <p className="text-xs text-fg/45 font-mono">
                      {formatarDias(p.dias_semana, p.data_especifica)} · {p.horario_inicio.slice(0, 5)} às{" "}
                      {p.horario_fim.slice(0, 5)}
                      {!p.ativo && " · pausado"}
                    </p>
                  </button>
                ) : (
                  <Link href={`/radialista/${radialistaId}/programas/${p.id}`} className="min-w-0">
                    <p className="text-sm font-medium text-fg hover:text-amber">{p.nome}</p>
                    <p className="text-xs text-fg/45 font-mono">
                      {formatarDias(p.dias_semana, p.data_especifica)} · {p.horario_inicio.slice(0, 5)} às{" "}
                      {p.horario_fim.slice(0, 5)}
                      {!p.ativo && " · pausado"}
                    </p>
                  </Link>
                )}
                <div className="flex items-center gap-3 shrink-0">
                  {onAbrirPrograma ? (
                    <button
                      type="button"
                      onClick={() => onAbrirPrograma(p.id)}
                      className="text-xs font-medium text-amber hover:text-amber-dim"
                    >
                      Editar
                    </button>
                  ) : (
                    <Link
                      href={`/radialista/${radialistaId}/programas/${p.id}`}
                      className="text-xs font-medium text-amber hover:text-amber-dim"
                    >
                      Editar
                    </Link>
                  )}
                  <button
                    type="button"
                    onClick={() => excluirPrograma(p)}
                    className="text-xs font-medium text-rust hover:text-rust/80"
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
  );
}
