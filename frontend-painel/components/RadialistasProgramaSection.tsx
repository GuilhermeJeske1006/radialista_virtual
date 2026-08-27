"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch, ApiError } from "../lib/api";
import { PAPEIS_SUGERIDOS, Radialista, RadialistaPrograma } from "../lib/types";
import { LocufySpin } from "./LocufyLogo";

const inputClass =
  "w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg placeholder:text-fg/65 focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20";

type Props = {
  programaId: number;
};

export default function RadialistasProgramaSection({ programaId }: Props) {
  const [roster, setRoster] = useState<RadialistaPrograma[] | null>(null);
  const [radialistasConta, setRadialistasConta] = useState<Radialista[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");
  const [mensagemLimite, setMensagemLimite] = useState("");
  const [salvandoId, setSalvandoId] = useState<number | null>(null);

  function carregar() {
    setCarregando(true);
    Promise.all([
      apiFetch<RadialistaPrograma[]>(`/config/programas/${programaId}/radialistas`),
      apiFetch<Radialista[]>("/config/radialistas"),
    ])
      .then(([rosterDados, radialistasDados]) => {
        setRoster(rosterDados);
        setRadialistasConta(radialistasDados);
      })
      .catch((err) => setErro(err instanceof ApiError ? err.message : "Erro ao carregar radialistas do programa"))
      .finally(() => setCarregando(false));
  }

  useEffect(carregar, [programaId]);

  function atualizarLocal(radioConfigId: number, campo: "papel" | "comportamento", valor: string) {
    setRoster((atual) => atual?.map((r) => (r.radio_config_id === radioConfigId ? { ...r, [campo]: valor } : r)) ?? atual);
  }

  async function salvar(item: RadialistaPrograma) {
    setSalvandoId(item.radio_config_id);
    setErro("");
    try {
      const atualizado = await apiFetch<RadialistaPrograma>(
        `/config/programas/${programaId}/radialistas/${item.radio_config_id}`,
        { method: "PUT", body: JSON.stringify({ papel: item.papel, comportamento: item.comportamento }) }
      );
      setRoster((atual) => atual?.map((r) => (r.radio_config_id === atualizado.radio_config_id ? atualizado : r)) ?? atual);
    } catch (err) {
      if (err instanceof ApiError && err.status === 402) {
        setMensagemLimite(err.message);
      } else {
        setErro(err instanceof ApiError ? err.message : "Erro ao salvar radialista");
      }
    } finally {
      setSalvandoId(null);
    }
  }

  async function adicionar(radioConfigId: number) {
    const radialista = radialistasConta.find((r) => r.id === radioConfigId);
    if (!radialista) return;
    await salvar({
      radio_config_id: radioConfigId,
      nome_locutor: radialista.nome_locutor,
      voz_id: radialista.voz_id,
      papel: "Co-apresentador",
      comportamento: "",
      e_dono: false,
    });
    carregar();
  }

  async function remover(radioConfigId: number) {
    setSalvandoId(radioConfigId);
    setErro("");
    try {
      await apiFetch(`/config/programas/${programaId}/radialistas/${radioConfigId}`, { method: "DELETE" });
      setRoster((atual) => atual?.filter((r) => r.radio_config_id !== radioConfigId) ?? atual);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao remover radialista");
    } finally {
      setSalvandoId(null);
    }
  }

  if (carregando) {
    return (
      <p className="flex items-center gap-2 text-sm text-fg/65">
        <LocufySpin size={16} /> Carregando radialistas...
      </p>
    );
  }

  if (!roster) {
    return <p className="text-sm text-rust-text">{erro || "Não foi possível carregar os radialistas do programa."}</p>;
  }

  const disponiveisPraAdicionar = radialistasConta.filter(
    (r) => r.ativo && !roster.some((v) => v.radio_config_id === r.id)
  );

  return (
    <div className="space-y-4">
      <p className="text-xs text-fg/65">
        Mais de um radialista no programa gera um diálogo alternado entre eles no ao vivo, cada um com sua própria
        voz. Defina o papel e como cada um deve se comportar.
      </p>

      {erro && <p className="text-sm text-rust-text">{erro}</p>}

      <div className="space-y-3">
        {roster.map((item) => (
          <div key={item.radio_config_id} className="rounded-lg border border-border-strong p-3 space-y-2">
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium text-fg">
                {item.nome_locutor}
                {item.e_dono && (
                  <span className="ml-2 rounded-full bg-amber/10 px-2 py-0.5 text-xs font-medium text-amber-text">
                    Dono do programa
                  </span>
                )}
              </span>
              {!item.e_dono && (
                <button
                  type="button"
                  onClick={() => remover(item.radio_config_id)}
                  disabled={salvandoId === item.radio_config_id}
                  className="text-xs font-medium text-rust-text hover:text-rust/80 disabled:opacity-60"
                >
                  Remover
                </button>
              )}
            </div>

            <div className="flex flex-wrap gap-1.5">
              {PAPEIS_SUGERIDOS.map((papel) => (
                <button
                  key={papel}
                  type="button"
                  onClick={() => atualizarLocal(item.radio_config_id, "papel", papel)}
                  className={`rounded-full px-3 py-1 text-xs font-medium border ${
                    item.papel === papel
                      ? "bg-brand-500 text-ink border-brand-500"
                      : "bg-transparent text-fg/65 border-border-strong"
                  }`}
                >
                  {papel}
                </button>
              ))}
            </div>
            <input
              className={inputClass}
              value={item.papel}
              placeholder="Papel (ex: Apresentador principal, Co-apresentador, Comentarista)"
              onChange={(e) => atualizarLocal(item.radio_config_id, "papel", e.target.value)}
            />
            <textarea
              className={inputClass}
              rows={2}
              placeholder="Como esse radialista deve se comportar neste programa (interação com os outros, humor, jeito de falar)..."
              value={item.comportamento}
              onChange={(e) => atualizarLocal(item.radio_config_id, "comportamento", e.target.value)}
            />
            <div>
              <button
                type="button"
                onClick={() => salvar(item)}
                disabled={salvandoId === item.radio_config_id}
                className="rounded-lg border border-border-strong px-3 py-1.5 text-xs font-medium text-fg/80 hover:bg-paper/5 disabled:opacity-60"
              >
                {salvandoId === item.radio_config_id ? "Salvando..." : "Salvar"}
              </button>
            </div>
          </div>
        ))}
      </div>

      {disponiveisPraAdicionar.length > 0 && (
        <select
          aria-label="Adicionar radialista ao programa"
          value=""
          onChange={(e) => {
            if (e.target.value) adicionar(Number(e.target.value));
            e.target.value = "";
          }}
          className="rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg/80"
        >
          <option value="">+ Adicionar radialista ao programa</option>
          {disponiveisPraAdicionar.map((r) => (
            <option key={r.id} value={r.id}>
              {r.nome_locutor}
            </option>
          ))}
        </select>
      )}

      {mensagemLimite && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/50 px-4"
          onClick={() => setMensagemLimite("")}
        >
          <div
            className="w-full max-w-sm rounded-2xl border border-border-strong bg-surface p-6 shadow-theme-xs"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="font-display text-base font-bold text-fg mb-2">Limite de radialistas atingido</h2>
            <p className="text-sm text-fg/70 mb-5">{mensagemLimite}</p>
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setMensagemLimite("")}
                className="rounded-lg px-4 py-2.5 text-sm font-medium text-fg/60 hover:text-fg"
              >
                Fechar
              </button>
              <Link
                href="/billing"
                className="rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-ink hover:bg-brand-600"
              >
                Ver planos
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
