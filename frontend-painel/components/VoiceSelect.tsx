"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch, ApiError } from "../lib/api";
import { permiteClonagemVoz } from "../lib/planos";
import { Conta, Voz, VozClonada } from "../lib/types";
import VozCloneModal from "./VozCloneModal";

type Props = {
  value: string | null;
  onChange: (vozId: string | null) => void;
};

export default function VoiceSelect({ value, onChange }: Props) {
  const [vozes, setVozes] = useState<Voz[]>([]);
  const [vozesClonadas, setVozesClonadas] = useState<VozClonada[]>([]);
  const [plano, setPlano] = useState<string | null>(null);
  const [modalAberto, setModalAberto] = useState(false);
  const [editandoId, setEditandoId] = useState<number | null>(null);
  const [nomeEdicao, setNomeEdicao] = useState("");
  const [erro, setErro] = useState("");

  function carregarVozesClonadas() {
    apiFetch<VozClonada[]>("/tts/vozes-clonadas")
      .then(setVozesClonadas)
      .catch(() => setVozesClonadas([]));
  }

  useEffect(() => {
    apiFetch<Voz[]>("/tts/voices")
      .then(setVozes)
      .catch(() => setVozes([]));
    apiFetch<Conta>("/auth/me")
      .then((conta) => setPlano(conta.plano))
      .catch(() => setPlano(null));
    carregarVozesClonadas();
  }, []);

  function iniciarEdicao(v: VozClonada) {
    setErro("");
    setEditandoId(v.id);
    setNomeEdicao(v.nome);
  }

  async function salvarRenomeacao(id: number) {
    const nome = nomeEdicao.trim();
    if (!nome) return;
    try {
      const atualizada = await apiFetch<VozClonada>(`/tts/vozes-clonadas/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ nome }),
      });
      setVozesClonadas((atual) => atual.map((v) => (v.id === id ? atualizada : v)));
      setEditandoId(null);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao renomear voz");
    }
  }

  async function excluirVozClonada(v: VozClonada) {
    if (!window.confirm(`Excluir a voz clonada "${v.nome}"? Essa ação não pode ser desfeita.`)) return;
    setErro("");
    try {
      await apiFetch(`/tts/vozes-clonadas/${v.id}`, { method: "DELETE" });
      setVozesClonadas((atual) => atual.filter((x) => x.id !== v.id));
      if (value === v.voz_id) onChange(null);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao excluir voz");
    }
  }

  return (
    <div>
      <div
        role="radiogroup"
        aria-label="Voz"
        className="max-h-72 divide-y divide-border-strong overflow-y-auto rounded-lg border border-border-strong"
      >
        <label className="flex cursor-pointer items-center gap-2 px-3 py-2 text-sm hover:bg-fg/5">
          <input type="radio" name="voz" checked={!value} onChange={() => onChange(null)} />
          Voz padrão do servidor
        </label>

        {vozesClonadas.length > 0 && (
          <>
            <p className="px-3 pt-2 text-xs font-medium text-fg/65">Minhas vozes clonadas</p>
            {vozesClonadas.map((v) =>
              editandoId === v.id ? (
                <div key={v.voz_id} className="flex items-center gap-2 px-3 py-2 text-sm">
                  <input
                    autoFocus
                    className="min-w-0 flex-1 rounded-lg border border-border-strong bg-bg px-2 py-1 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
                    value={nomeEdicao}
                    onChange={(e) => setNomeEdicao(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") salvarRenomeacao(v.id);
                      if (e.key === "Escape") setEditandoId(null);
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => salvarRenomeacao(v.id)}
                    className="shrink-0 text-xs font-medium text-amber-text hover:text-amber-dim"
                  >
                    Salvar
                  </button>
                  <button
                    type="button"
                    onClick={() => setEditandoId(null)}
                    className="shrink-0 text-xs text-fg/65 hover:text-fg"
                  >
                    Cancelar
                  </button>
                </div>
              ) : (
                <div key={v.voz_id} className="flex items-center gap-2 px-3 py-2 text-sm hover:bg-fg/5">
                  <label className="flex flex-1 cursor-pointer items-center gap-2">
                    <input type="radio" name="voz" checked={value === v.voz_id} onChange={() => onChange(v.voz_id)} />
                    {v.nome}
                  </label>
                  {v.preview_url && (
                    <audio controls preload="none" src={v.preview_url} className="h-8 w-40 shrink-0" />
                  )}
                  <button
                    type="button"
                    onClick={() => iniciarEdicao(v)}
                    title="Renomear"
                    className="shrink-0 text-fg/65 hover:text-fg"
                  >
                    ✏️
                  </button>
                  <button
                    type="button"
                    onClick={() => excluirVozClonada(v)}
                    title="Excluir"
                    className="shrink-0 text-fg/65 hover:text-rust-text"
                  >
                    🗑️
                  </button>
                </div>
              )
            )}
          </>
        )}

        <p className="px-3 pt-2 text-xs font-medium text-fg/65">Catálogo (com amostra de áudio)</p>
        {vozes.map((v) => (
          <div key={v.voz_id} className="flex items-center gap-2 px-3 py-2 text-sm hover:bg-fg/5">
            <label className="flex flex-1 cursor-pointer items-center gap-2">
              <input type="radio" name="voz" checked={value === v.voz_id} onChange={() => onChange(v.voz_id)} />
              {v.nome} — {v.genero}, {v.descricao}
            </label>
            {v.preview_url && (
              <audio controls preload="none" src={v.preview_url} className="h-8 w-40 shrink-0" />
            )}
          </div>
        ))}
      </div>

      {erro && <p className="mt-1.5 text-xs text-rust-text">{erro}</p>}

      <div className="mt-1.5">
        {permiteClonagemVoz(plano) ? (
          <button
            type="button"
            onClick={() => setModalAberto(true)}
            className="text-xs font-medium text-amber-text hover:text-amber-dim"
          >
            🎙️ Clonar uma voz
          </button>
        ) : (
          plano && (
            <p className="text-xs text-fg/65">
              Clonar sua própria voz é um recurso do plano Growth em diante.{" "}
              <Link href="/billing" className="text-amber-text hover:underline">
                Fazer upgrade
              </Link>
            </p>
          )
        )}
      </div>

      {modalAberto && (
        <VozCloneModal
          onFechar={() => setModalAberto(false)}
          onCriada={(voz) => {
            carregarVozesClonadas();
            onChange(voz.voz_id);
            setModalAberto(false);
          }}
        />
      )}
    </div>
  );
}
