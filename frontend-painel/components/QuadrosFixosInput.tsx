"use client";

import { useState } from "react";

const inputClass =
  "w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg placeholder:text-fg/65 focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20";

type Props = {
  quadros: Record<string, string[]>;
  onChange: (quadros: Record<string, string[]>) => void;
};

export default function QuadrosFixosInput({ quadros, onChange }: Props) {
  const [novoLabel, setNovoLabel] = useState("");
  const [novoItem, setNovoItem] = useState<Record<string, string>>({});

  function adicionarQuadro() {
    const label = novoLabel.trim();
    if (!label || quadros[label]) return;
    onChange({ ...quadros, [label]: [] });
    setNovoLabel("");
  }

  function removerQuadro(label: string) {
    const { [label]: _removido, ...resto } = quadros;
    onChange(resto);
  }

  function adicionarItem(label: string) {
    const valor = (novoItem[label] ?? "").trim();
    if (!valor) return;
    onChange({ ...quadros, [label]: [...(quadros[label] ?? []), valor] });
    setNovoItem({ ...novoItem, [label]: "" });
  }

  function removerItem(label: string, item: string) {
    onChange({ ...quadros, [label]: quadros[label].filter((i) => i !== item) });
  }

  const labels = Object.keys(quadros);

  return (
    <div>
      <label className="block text-sm font-medium text-fg/80 mb-1.5">Quadros fixos</label>
      <p className="text-xs text-fg/65 mb-3">
        Quadros com identidade fixa (ex.: &quot;Curiosidade das 10&quot;) -- o nome do quadro precisa aparecer
        também na sequência do programa, acima. Cada vez que o bloco sair no roteiro, um item do pool abaixo é
        sorteado em rotação.
      </p>
      <div className="space-y-3 mb-3">
        {labels.map((label) => (
          <div key={label} className="rounded-lg border border-border-strong p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-fg">{label}</span>
              <button
                type="button"
                onClick={() => removerQuadro(label)}
                className="text-xs font-medium text-rust-text hover:text-rust/80"
              >
                Remover quadro
              </button>
            </div>
            {quadros[label].length > 0 && (
              <div className="flex flex-wrap gap-1.5 mb-2">
                {quadros[label].map((item) => (
                  <span
                    key={item}
                    className="inline-flex items-center gap-1 rounded-full bg-amber/10 text-amber-text border border-amber/25 pl-2.5 pr-1.5 py-0.5 text-sm"
                  >
                    {item}
                    <button
                      type="button"
                      onClick={() => removerItem(label, item)}
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
                value={novoItem[label] ?? ""}
                onChange={(e) => setNovoItem({ ...novoItem, [label]: e.target.value })}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    adicionarItem(label);
                  }
                }}
                placeholder="Novo item do pool"
                className={inputClass}
              />
              <button
                type="button"
                onClick={() => adicionarItem(label)}
                className="shrink-0 rounded-lg border border-border-strong px-3 py-2 text-sm font-medium text-fg/80 hover:bg-paper/5"
              >
                Adicionar
              </button>
            </div>
          </div>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          type="text"
          value={novoLabel}
          onChange={(e) => setNovoLabel(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              adicionarQuadro();
            }
          }}
          placeholder="Nome do novo quadro (ex.: Curiosidade das 10)"
          className={inputClass}
        />
        <button
          type="button"
          onClick={adicionarQuadro}
          className="shrink-0 rounded-lg border border-border-strong px-3 py-2 text-sm font-medium text-fg/80 hover:bg-paper/5"
        >
          Novo quadro
        </button>
      </div>
    </div>
  );
}
