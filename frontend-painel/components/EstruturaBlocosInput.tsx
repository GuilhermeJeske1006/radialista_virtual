"use client";

import { useState } from "react";
import { BLOCOS_PRESET, Patrocinador, rotuloBloco } from "../lib/types";

type Props = {
  blocos: string[];
  onChange: (blocos: string[]) => void;
  patrocinadores?: Patrocinador[];
};

export default function EstruturaBlocosInput({ blocos, onChange, patrocinadores = [] }: Props) {
  const [texto, setTexto] = useState("");
  const nomesPatrocinadores = Object.fromEntries(patrocinadores.map((p) => [p.id, p.nome]));

  function adicionar(bloco: string) {
    const valor = bloco.trim();
    if (!valor) return;
    onChange([...blocos, valor]);
    setTexto("");
  }

  function remover(indice: number) {
    onChange(blocos.filter((_, i) => i !== indice));
  }

  function mover(indice: number, direcao: -1 | 1) {
    const novo = indice + direcao;
    if (novo < 0 || novo >= blocos.length) return;
    const copia = [...blocos];
    [copia[indice], copia[novo]] = [copia[novo], copia[indice]];
    onChange(copia);
  }

  return (
    <div className="mb-4 min-w-0">
      <label className="block text-sm font-medium text-fg/80 mb-1.5">Sequência de blocos do programa</label>
      <p className="text-xs text-fg/45 mb-2">
        Monte a ordem que o ao vivo deve seguir (ex.: Abertura → Saudação → Música → Notícia → Música). Pode repetir
        blocos quantas vezes quiser.
      </p>

      {blocos.length > 0 && (
        <ol className="flex flex-wrap items-center gap-1.5 mb-3">
          {blocos.map((bloco, i) => (
            <li key={`${bloco}-${i}`} className="flex items-center gap-1.5">
              <span className="inline-flex items-center gap-1 rounded-full bg-amber/10 text-amber border border-amber/25 pl-2.5 pr-1.5 py-0.5 text-sm">
                <span className="font-mono text-[10px] text-amber/60">{i + 1}</span>
                {rotuloBloco(bloco, nomesPatrocinadores)}
                <span className="flex items-center">
                  <button
                    type="button"
                    onClick={() => mover(i, -1)}
                    disabled={i === 0}
                    className="text-amber/70 hover:text-amber leading-none px-0.5 disabled:opacity-25"
                    title="Mover pra esquerda"
                  >
                    ‹
                  </button>
                  <button
                    type="button"
                    onClick={() => mover(i, 1)}
                    disabled={i === blocos.length - 1}
                    className="text-amber/70 hover:text-amber leading-none px-0.5 disabled:opacity-25"
                    title="Mover pra direita"
                  >
                    ›
                  </button>
                  <button
                    type="button"
                    onClick={() => remover(i)}
                    className="text-amber/70 hover:text-amber leading-none text-base px-0.5"
                    title="Remover"
                  >
                    ×
                  </button>
                </span>
              </span>
              {i < blocos.length - 1 && <span className="text-fg/25 text-xs">→</span>}
            </li>
          ))}
        </ol>
      )}

      <div className="flex flex-wrap items-center gap-1.5 mb-2">
        {BLOCOS_PRESET.map((preset) => (
          <button
            key={preset.value}
            type="button"
            onClick={() => adicionar(preset.value)}
            className="rounded-full px-3 py-1 text-xs font-medium border border-border-strong text-fg/65 hover:border-amber/40 hover:text-amber"
          >
            + {preset.label}
          </button>
        ))}
        {patrocinadores.filter((p) => p.ativo).length > 0 && (
          <select
            value=""
            onChange={(e) => {
              if (e.target.value) adicionar(`patrocinador:${e.target.value}`);
              e.target.value = "";
            }}
            className="rounded-full px-3 py-1 text-xs font-medium border border-border-strong text-fg/65 bg-bg hover:border-amber/40 hover:text-amber"
          >
            <option value="">+ Patrocinador</option>
            {patrocinadores
              .filter((p) => p.ativo)
              .map((p) => (
                <option key={p.id} value={p.id}>
                  {p.nome}
                </option>
              ))}
          </select>
        )}
      </div>

      <div className="flex gap-2">
        <input
          type="text"
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              adicionar(texto);
            }
          }}
          placeholder="Bloco personalizado e pressione Enter"
          className="flex-1 min-w-0 rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg placeholder:text-fg/35 focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
        />
        <button
          type="button"
          onClick={() => adicionar(texto)}
          className="rounded-lg border border-border-strong px-3 py-2 text-sm font-medium text-fg/80 hover:bg-paper/5"
        >
          Adicionar
        </button>
      </div>
      <p className="text-xs text-fg/35 mt-1.5">
        Blocos dos botões acima (Abertura, Música, Comentário, Notícia, Chamada ao ouvinte) têm comportamento
        especial no ao vivo (busca música de verdade, atende pedidos do WhatsApp). Blocos personalizados viram
        falas livres, sem essa automação.
      </p>
    </div>
  );
}
