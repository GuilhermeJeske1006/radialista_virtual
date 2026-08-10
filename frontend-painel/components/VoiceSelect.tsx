"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "../lib/api";
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

  return (
    <div>
      <select
        className="w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value || null)}
      >
        <option value="">Voz padrão do servidor</option>
        {vozesClonadas.length > 0 && (
          <optgroup label="Minhas vozes clonadas">
            {vozesClonadas.map((v) => (
              <option key={v.voz_id} value={v.voz_id}>
                {v.nome}
              </option>
            ))}
          </optgroup>
        )}
        <optgroup label="Catálogo">
          {vozes.map((v) => (
            <option key={v.voz_id} value={v.voz_id}>
              {v.nome} — {v.genero}, {v.descricao}
            </option>
          ))}
        </optgroup>
      </select>

      <div className="mt-1.5">
        {permiteClonagemVoz(plano) ? (
          <button
            type="button"
            onClick={() => setModalAberto(true)}
            className="text-xs font-medium text-amber hover:text-amber-dim"
          >
            🎙️ Clonar uma voz
          </button>
        ) : (
          plano && (
            <p className="text-xs text-fg/45">
              Clonar sua própria voz é um recurso do plano Growth em diante.{" "}
              <Link href="/billing" className="text-amber hover:underline">
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
