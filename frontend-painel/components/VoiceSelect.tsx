"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch, ApiError } from "../lib/api";
import { permiteClonagemVoz } from "../lib/planos";
import { Conta, Voz, VozClonada } from "../lib/types";
import AudioPreviewButton from "./AudioPreviewButton";
import VozCloneModal from "./VozCloneModal";
import VozConfigModal from "./VozConfigModal";

type Props = {
  value: string | null;
  onChange: (vozId: string | null) => void;
};

export default function VoiceSelect({ value, onChange }: Props) {
  const [vozes, setVozes] = useState<Voz[]>([]);
  const [vozesClonadas, setVozesClonadas] = useState<VozClonada[]>([]);
  const [vozesCompartilhadas, setVozesCompartilhadas] = useState<VozClonada[]>([]);
  const [plano, setPlano] = useState<string | null>(null);
  const [modalAberto, setModalAberto] = useState(false);
  const [editandoId, setEditandoId] = useState<number | null>(null);
  const [nomeEdicao, setNomeEdicao] = useState("");
  const [erro, setErro] = useState("");
  const [configVoz, setConfigVoz] = useState<string | null | undefined>(undefined);

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
    apiFetch<VozClonada[]>("/tts/vozes-compartilhadas")
      .then(setVozesCompartilhadas)
      .catch(() => setVozesCompartilhadas([]));
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
        className="max-h-80 space-y-1 overflow-y-auto rounded-xl border border-border-strong bg-surface-2/40 p-1.5"
      >
        <label
          className={`flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition-colors ${
            !value ? "bg-acento-claro/10 ring-1 ring-inset ring-acento-claro/30" : "hover:bg-fg/5"
          }`}
        >
          <input
            type="radio"
            name="voz"
            checked={!value}
            onChange={() => onChange(null)}
            className="h-4 w-4 shrink-0 accent-acento-claro"
          />
          <span className="text-fg/85">Voz padrão do servidor</span>
        </label>

        {vozesClonadas.length > 0 && (
          <>
            <p className="px-2.5 pt-3 pb-1 text-xs font-semibold tracking-wide text-fg/50 uppercase">
              Minhas vozes clonadas
            </p>
            {vozesClonadas.map((v) =>
              editandoId === v.id ? (
                <div key={v.voz_id} className="flex items-center gap-2 rounded-lg px-2.5 py-2 text-sm">
                  <input
                    autoFocus
                    className="min-w-0 flex-1 rounded-xl border border-border-strong bg-bg px-2 py-1 text-sm text-fg focus:outline-none focus:border-acento-claro/50 focus:ring-2 focus:ring-acento-claro/20"
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
                    className="shrink-0 text-xs font-medium text-acento-claro hover:text-acento-dim"
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
                <div
                  key={v.voz_id}
                  className={`flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg px-2.5 py-2 text-sm transition-colors ${
                    value === v.voz_id ? "bg-acento-claro/10 ring-1 ring-inset ring-acento-claro/30" : "hover:bg-fg/5"
                  }`}
                >
                  <label className="flex min-w-0 flex-1 cursor-pointer items-center gap-2.5">
                    <input
                      type="radio"
                      name="voz"
                      checked={value === v.voz_id}
                      disabled={v.requer_verificacao}
                      onChange={() => onChange(v.voz_id)}
                      className="h-4 w-4 shrink-0 accent-acento-claro"
                    />
                    <span className="min-w-0 truncate text-fg/85">
                      {v.nome}
                      {v.requer_verificacao && (
                        <span className="text-fg/55"> · aguardando verificação</span>
                      )}
                    </span>
                  </label>
                  <div className="flex shrink-0 items-center gap-3">
                    {v.requer_verificacao && (
                      <button
                        type="button"
                        className="text-xs font-medium text-acento-claro hover:text-acento-dim"
                        onClick={() => setConfigVoz(v.voz_id)}
                      >
                        Verificar status
                      </button>
                    )}
                    {v.preview_url && <AudioPreviewButton src={v.preview_url} />}
                    <div className="flex items-center gap-1">
                      <button
                        type="button"
                        onClick={() => iniciarEdicao(v)}
                        title="Renomear"
                        className="rounded-md p-1 text-fg/55 hover:bg-fg/10 hover:text-fg"
                      >
                        ✏️
                      </button>
                      <button
                        type="button"
                        onClick={() => excluirVozClonada(v)}
                        title="Excluir"
                        className="rounded-md p-1 text-fg/55 hover:bg-laranja/10 hover:text-laranja"
                      >
                        🗑️
                      </button>
                    </div>
                  </div>
                </div>
              )
            )}
          </>
        )}

        {vozesCompartilhadas.length > 0 && (
          <>
            <p className="px-2.5 pt-3 pb-1 text-xs font-semibold tracking-wide text-fg/50 uppercase">
              Vozes clonadas compartilhadas
            </p>
            {vozesCompartilhadas.map((v) => (
              <div
                key={v.voz_id}
                className={`flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg px-2.5 py-2 text-sm transition-colors ${
                  value === v.voz_id ? "bg-acento-claro/10 ring-1 ring-inset ring-acento-claro/30" : "hover:bg-fg/5"
                }`}
              >
                <label className="flex min-w-0 flex-1 cursor-pointer items-center gap-2.5">
                  <input
                    type="radio"
                    name="voz"
                    checked={value === v.voz_id}
                    disabled={v.requer_verificacao}
                    onChange={() => onChange(v.voz_id)}
                    className="h-4 w-4 shrink-0 accent-acento-claro"
                  />
                  <span className="min-w-0 truncate text-fg/85">{v.nome}</span>
                </label>
                {v.preview_url && <AudioPreviewButton src={v.preview_url} className="shrink-0" />}
              </div>
            ))}
          </>
        )}

        <p className="px-2.5 pt-3 pb-1 text-xs font-semibold tracking-wide text-fg/50 uppercase">
          Catálogo (com amostra de áudio)
        </p>
        {vozes.map((v) => (
          <div
            key={v.voz_id}
            className={`flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg px-2.5 py-2 text-sm transition-colors ${
              value === v.voz_id ? "bg-acento-claro/10 ring-1 ring-inset ring-acento-claro/30" : "hover:bg-fg/5"
            }`}
          >
            <label className="flex min-w-0 flex-1 cursor-pointer items-center gap-2.5">
              <input
                type="radio"
                name="voz"
                checked={value === v.voz_id}
                onChange={() => onChange(v.voz_id)}
                className="h-4 w-4 shrink-0 accent-acento-claro"
              />
              <span className="min-w-0 truncate text-fg/85">
                {v.nome} — {v.genero}, {v.descricao}
              </span>
            </label>
            {v.preview_url && <AudioPreviewButton src={v.preview_url} className="shrink-0" />}
          </div>
        ))}
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
        <button
          type="button"
          className="text-xs font-medium text-acento-claro hover:text-acento-dim"
          onClick={() => setConfigVoz(value)}
        >
          Ajustar voz selecionada
        </button>
        {permiteClonagemVoz(plano) && (
          <button
            type="button"
            onClick={() => setModalAberto(true)}
            className="text-xs font-medium text-acento-claro hover:text-acento-dim"
          >
            🎙️ Clonar uma voz
          </button>
        )}
      </div>
      {configVoz !== undefined && <VozConfigModal vozId={configVoz} onFechar={() => setConfigVoz(undefined)} onAtualizada={carregarVozesClonadas} />}
      {erro && <p className="mt-1.5 text-xs text-laranja">{erro}</p>}

      {!permiteClonagemVoz(plano) && plano && (
        <p className="mt-1.5 text-xs text-fg/65">
          Clonagem de voz disponível no Locufy Flex.{" "}
          <Link href="/billing" className="text-acento-claro hover:underline">
            Ver assinatura
          </Link>
        </p>
      )}

      {modalAberto && (
        <VozCloneModal
          onFechar={() => setModalAberto(false)}
          onCriada={(voz) => {
            carregarVozesClonadas();
            if (!voz.requer_verificacao) onChange(voz.voz_id);
            else setErro("Voz criada e aguardando verificação. Use Verificar status após concluir na ElevenLabs.");
            setModalAberto(false);
          }}
        />
      )}
    </div>
  );
}
