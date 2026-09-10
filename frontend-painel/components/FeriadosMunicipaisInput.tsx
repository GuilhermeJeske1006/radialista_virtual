"use client";

import { useState } from "react";
import { FeriadoMunicipal } from "../lib/types";

const inputClass =
  "w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg placeholder:text-fg/65 focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20";

const DATA_MM_DD_RE = /^\d{2}-\d{2}$/;

type Props = {
  feriados: FeriadoMunicipal[];
  onChange: (feriados: FeriadoMunicipal[]) => void;
};

export default function FeriadosMunicipaisInput({ feriados, onChange }: Props) {
  const [data, setData] = useState("");
  const [nome, setNome] = useState("");

  function adicionar() {
    if (!DATA_MM_DD_RE.test(data.trim()) || !nome.trim()) return;
    onChange([...feriados, { data: data.trim(), nome: nome.trim() }]);
    setData("");
    setNome("");
  }

  function remover(indice: number) {
    onChange(feriados.filter((_, i) => i !== indice));
  }

  return (
    <div>
      <label className="block text-sm font-medium text-fg/80 mb-1.5">Feriados municipais</label>
      <p className="text-xs text-fg/65 mb-2">
        Feriados só da sua cidade (formato MM-DD) -- os feriados nacionais já são calculados automaticamente.
      </p>
      {feriados.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2">
          {feriados.map((f, i) => (
            <span
              key={`${f.data}-${f.nome}-${i}`}
              className="inline-flex items-center gap-1 rounded-full bg-amber/10 text-amber-text border border-amber/25 pl-2.5 pr-1.5 py-0.5 text-sm"
            >
              {f.data} · {f.nome}
              <button
                type="button"
                onClick={() => remover(i)}
                className="text-amber-text/70 hover:text-amber-text leading-none text-base"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}
      <div className="flex gap-2">
        <input
          type="text"
          value={data}
          onChange={(e) => setData(e.target.value)}
          placeholder="MM-DD"
          maxLength={5}
          className={`${inputClass} w-24 shrink-0`}
        />
        <input
          type="text"
          value={nome}
          onChange={(e) => setNome(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              adicionar();
            }
          }}
          placeholder="Nome do feriado"
          className={inputClass}
        />
        <button
          type="button"
          onClick={adicionar}
          className="shrink-0 rounded-lg border border-border-strong px-3 py-2 text-sm font-medium text-fg/80 hover:bg-paper/5"
        >
          Adicionar
        </button>
      </div>
    </div>
  );
}
