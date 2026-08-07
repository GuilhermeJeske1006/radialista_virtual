"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "../lib/api";
import { Voz } from "../lib/types";

type Props = {
  value: string | null;
  onChange: (vozId: string | null) => void;
};

export default function VoiceSelect({ value, onChange }: Props) {
  const [vozes, setVozes] = useState<Voz[]>([]);

  useEffect(() => {
    apiFetch<Voz[]>("/tts/voices")
      .then(setVozes)
      .catch(() => setVozes([]));
  }, []);

  return (
    <select
      className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:border-brand-300 focus:ring-2 focus:ring-brand-500/20"
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value || null)}
    >
      <option value="">Voz padrão do servidor</option>
      {vozes.map((v) => (
        <option key={v.voz_id} value={v.voz_id}>
          {v.nome} — {v.genero}, {v.descricao}
        </option>
      ))}
    </select>
  );
}
