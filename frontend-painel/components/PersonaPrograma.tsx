"use client";

import { useState } from "react";
import {
  PERSONA_MAX_CARACTERES_EXEMPLO,
  PERSONA_MAX_EXEMPLOS,
  PERSONA_PADRAO,
  type Persona,
} from "../lib/types";

const inputClass =
  "w-full rounded-xl border border-border-strong bg-bg px-3 py-2 text-sm text-fg placeholder:text-fg/65 focus:outline-none focus:border-acento-claro/50 focus:ring-2 focus:ring-acento-claro/20";
const labelClass = "block text-sm font-medium text-fg/80 mb-1.5";

const ESCALAS: { campo: keyof Omit<Persona, "exemplos">; rotulo: string; dica: string }[] = [
  { campo: "proximidade", rotulo: "Proximidade", dica: "1 distante · 5 como conhecido" },
  { campo: "formalidade", rotulo: "Formalidade", dica: "1 informal · 5 formal" },
  { campo: "energia", rotulo: "Energia", dica: "1 calmo · 5 vibrante" },
  { campo: "humor", rotulo: "Humor", dica: "1 sério · 5 bem-humorado" },
  { campo: "ritmo", rotulo: "Ritmo", dica: "1 pausado · 5 rápido" },
];

function exemplosDoTexto(texto: string): string[] {
  return texto.split("\n").map((linha) => linha.trim()).filter((linha) => linha.length > 0);
}

function ExemplosPersona({ exemplos, onChange }: { exemplos: string[]; onChange: (exemplos: string[]) => void }) {
  // Rascunho local: o texto com quebras de linha não pode ser reescrito a cada tecla, senão o Enter some.
  const [texto, setTexto] = useState(exemplos.join("\n"));
  const linhas = exemplosDoTexto(texto);
  const excesso = linhas.length > PERSONA_MAX_EXEMPLOS;
  const longo = linhas.some((linha) => linha.length > PERSONA_MAX_CARACTERES_EXEMPLO);

  return (
    <div>
      <label htmlFor="persona-exemplos" className={labelClass}>
        Exemplos de fala aprovados (um por linha, até {PERSONA_MAX_EXEMPLOS})
      </label>
      <textarea
        id="persona-exemplos"
        className={inputClass}
        rows={4}
        value={texto}
        onChange={(e) => {
          setTexto(e.target.value);
          onChange(exemplosDoTexto(e.target.value));
        }}
      />
      {excesso && (
        <p role="alert" className="mt-1 text-xs text-red-400">
          Use no máximo {PERSONA_MAX_EXEMPLOS} exemplos. Os excedentes não serão aceitos ao salvar.
        </p>
      )}
      {longo && (
        <p role="alert" className="mt-1 text-xs text-red-400">
          Cada exemplo pode ter até {PERSONA_MAX_CARACTERES_EXEMPLO} caracteres.
        </p>
      )}
    </div>
  );
}

export default function PersonaPrograma({
  persona,
  onChange,
}: {
  persona: Persona | null;
  onChange: (persona: Persona | null) => void;
}) {
  if (persona === null) {
    return (
      <div className="space-y-2">
        <p className="text-xs text-fg/65">
          Persona define o jeito da emissora (escalas e exemplos aprovados). Não é uma pessoa: não use nome nem
          jeito de apresentador real.
        </p>
        <button
          type="button"
          className="rounded-xl border border-border-strong px-3 py-2 text-sm text-fg hover:border-acento-claro/50"
          onClick={() => onChange({ ...PERSONA_PADRAO })}
        >
          Definir persona da rádio
        </button>
      </div>
    );
  }

  return (
    <fieldset className="space-y-3" aria-label="Persona da rádio">
      <legend className="text-sm font-medium text-fg/80">Persona da rádio</legend>
      <p className="text-xs text-fg/65">
        Persona define o jeito da emissora, não de uma pessoa. Não use nome nem jeito de apresentador real.
      </p>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {ESCALAS.map(({ campo, rotulo, dica }) => (
          <div key={campo}>
            <label htmlFor={`persona-${campo}`} className={labelClass}>
              {rotulo}
            </label>
            <select
              id={`persona-${campo}`}
              className={inputClass}
              value={persona[campo]}
              onChange={(e) => onChange({ ...persona, [campo]: Number(e.target.value) })}
              aria-describedby={`persona-${campo}-dica`}
            >
              {[1, 2, 3, 4, 5].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
            <p id={`persona-${campo}-dica`} className="mt-1 text-xs text-fg/65">
              {dica}
            </p>
          </div>
        ))}
      </div>
      <ExemplosPersona exemplos={persona.exemplos} onChange={(exemplos) => onChange({ ...persona, exemplos })} />
      <button
        type="button"
        className="text-sm text-fg/70 underline"
        onClick={() => onChange(null)}
      >
        Remover persona (volta ao comportamento padrão)
      </button>
    </fieldset>
  );
}
