"use client";

import { useState } from "react";
import { apiFetch, ApiError } from "../lib/api";

// F9: glossário de pronúncia da rádio (backend app/tts/glossario.py). Vale para todas as vozes; o glossário de
// uma voz (configuração da voz) sobrescreve o termo igual. Linha sem termo ou sem pronúncia não é salva.
export const MAX_TERMOS_GLOSSARIO_RADIO = 100;

type Linha = { termo: string; pronuncia: string };
type Props = {
  valor: Record<string, string>;
  onChange: (glossario: Record<string, string>) => void;
};

const inputClass =
  "w-full rounded-xl border border-border-strong bg-bg px-3 py-2 text-sm text-fg placeholder:text-fg/65 focus:outline-none focus:border-acento-claro/50 focus:ring-2 focus:ring-acento-claro/20";

function paraGlossario(linhas: Linha[]): Record<string, string> {
  const glossario: Record<string, string> = {};
  for (const { termo, pronuncia } of linhas) {
    const t = termo.trim();
    const p = pronuncia.trim();
    if (t && p && !(t in glossario)) glossario[t] = p;
  }
  return glossario;
}

export default function GlossarioPronunciaRadio({ valor, onChange }: Props) {
  const [linhas, setLinhas] = useState<Linha[]>(() =>
    Object.entries(valor).map(([termo, pronuncia]) => ({ termo, pronuncia })),
  );
  const [sugerindo, setSugerindo] = useState(false);
  const [aviso, setAviso] = useState("");

  function atualizar(novas: Linha[]) {
    setLinhas(novas);
    onChange(paraGlossario(novas));
  }

  function editar(indice: number, campo: keyof Linha, texto: string) {
    atualizar(linhas.map((linha, i) => (i === indice ? { ...linha, [campo]: texto } : linha)));
  }

  async function sugerir() {
    setSugerindo(true);
    setAviso("");
    try {
      const { termos } = await apiFetch<{ termos: string[] }>("/config/radio/glossario/sugestoes");
      const presentes = new Set(linhas.map((l) => l.termo.trim().toLowerCase()));
      const novos = termos.filter((t) => !presentes.has(t.toLowerCase()));
      if (novos.length === 0) {
        setAviso("Nenhum termo novo encontrado nos textos da rádio.");
        return;
      }
      setLinhas([...linhas, ...novos.map((termo) => ({ termo, pronuncia: "" }))]);
      setAviso(`${novos.length} termo(s) sugerido(s). Escreva como cada um deve soar; sem pronúncia, não é salvo.`);
    } catch (err) {
      setAviso(err instanceof ApiError ? err.message : "Erro ao buscar sugestões");
    } finally {
      setSugerindo(false);
    }
  }

  const cheio = linhas.length >= MAX_TERMOS_GLOSSARIO_RADIO;

  return (
    <div>
      <p className="text-sm text-fg/65 mb-4">
        Como a voz deve ler nomes de artistas, bairros, siglas, patrocinadores e convidados. Vale para todas as
        vozes; a configuração de uma voz sobrescreve o mesmo termo. Até {MAX_TERMOS_GLOSSARIO_RADIO} termos.
      </p>
      <div className="space-y-2 mb-3">
        {linhas.map((linha, i) => (
          <div key={i} className="flex gap-2">
            <input
              aria-label={`Termo ${i + 1}`}
              value={linha.termo}
              maxLength={60}
              onChange={(e) => editar(i, "termo", e.target.value)}
              placeholder="Termo (ex.: Kelly)"
              className={inputClass}
            />
            <input
              aria-label={`Pronúncia ${i + 1}`}
              value={linha.pronuncia}
              maxLength={60}
              onChange={(e) => editar(i, "pronuncia", e.target.value)}
              placeholder="Como soa (ex.: Quéli)"
              className={inputClass}
            />
            <button
              type="button"
              onClick={() => atualizar(linhas.filter((_, j) => j !== i))}
              className="shrink-0 text-xs font-medium text-laranja hover:text-laranja/80"
            >
              Remover
            </button>
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={cheio}
          onClick={() => setLinhas([...linhas, { termo: "", pronuncia: "" }])}
          className="rounded-xl border border-border-strong px-3 py-2 text-sm font-medium text-fg/80 hover:bg-fg/5 disabled:opacity-60"
        >
          Adicionar termo
        </button>
        <button
          type="button"
          disabled={sugerindo || cheio}
          onClick={sugerir}
          className="rounded-xl border border-border-strong px-3 py-2 text-sm font-medium text-fg/80 hover:bg-fg/5 disabled:opacity-60"
        >
          {sugerindo ? "Buscando…" : "Sugerir termos"}
        </button>
      </div>
      {aviso && <p role="status" className="text-xs text-fg/70 mt-2">{aviso}</p>}
    </div>
  );
}
