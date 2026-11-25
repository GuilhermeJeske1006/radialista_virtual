"use client";

import { useId, useState } from "react";
import {
  PERSONA_MAX_CARACTERES_EXEMPLO,
  PERSONA_MAX_EXEMPLOS,
  PERSONA_PADRAO,
  PERSONA_MAX_ORIENTACOES,
  type Persona,
} from "../lib/types";
import { ESTILOS_PROGRAMA, estiloSelecionado, type EscalaPersona } from "../lib/estilosPrograma";

const inputClass =
  "w-full rounded-xl border border-border-strong bg-bg px-3 py-2 text-sm text-fg placeholder:text-fg/65 focus:outline-none focus:border-acento-claro/50 focus:ring-2 focus:ring-acento-claro/20";
const labelClass = "block text-sm font-medium text-fg/80 mb-1.5";

const ESCALAS: { campo: EscalaPersona; rotulo: string; dica: string }[] = [
  { campo: "proximidade", rotulo: "Proximidade", dica: "1 distante · 5 como conhecido" },
  { campo: "formalidade", rotulo: "Formalidade", dica: "1 informal · 5 formal" },
  { campo: "energia", rotulo: "Energia", dica: "1 calmo · 5 vibrante" },
  { campo: "humor", rotulo: "Humor", dica: "1 sério · 5 bem-humorado" },
  { campo: "ritmo", rotulo: "Ritmo", dica: "1 pausado · 5 rápido" },
];

function exemplosDoTexto(texto: string): string[] {
  return texto.split("\n").map((linha) => linha.trim()).filter((linha) => linha.length > 0);
}

function ExemplosPersona({ exemplos, onChange, id }: { exemplos: string[]; onChange: (exemplos: string[]) => void; id: string }) {
  // Rascunho local: o texto com quebras de linha não pode ser reescrito a cada tecla, senão o Enter some.
  const [texto, setTexto] = useState(exemplos.join("\n"));
  const linhas = exemplosDoTexto(texto);
  const excesso = linhas.length > PERSONA_MAX_EXEMPLOS;
  const longo = linhas.some((linha) => linha.length > PERSONA_MAX_CARACTERES_EXEMPLO);

  return (
    <div>
      <label htmlFor={id} className={labelClass}>
        Exemplos de fala aprovados (um por linha, até {PERSONA_MAX_EXEMPLOS})
      </label>
      <textarea
        id={id}
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
  const id = useId();
  const estilo = persona ? estiloSelecionado(persona) : "";
  if (persona === null) {
    return (
      <div className="space-y-2">
        <p className="text-xs text-fg/65">
          O mesmo radialista pode ser descontraído em um programa e sério em outro, mantendo a mesma voz.
          Personalize o jeito de falar para esta atração.
        </p>
        <button
          type="button"
          className="rounded-xl border border-border-strong px-3 py-2 text-sm text-fg hover:border-acento-claro/50"
          onClick={() => onChange({ ...PERSONA_PADRAO })}
        >
          Personalizar jeito de falar
        </button>
      </div>
    );
  }

  return (
    <fieldset className="space-y-4" aria-label="Jeito de falar neste programa">
      <legend className="text-sm font-medium text-fg/80">Jeito de falar neste programa</legend>
      <p className="text-xs text-fg/65">
        Estas escolhas valem para este programa e prevalecem sobre a personalidade geral do radialista.
        A voz cadastrada é mantida.
      </p>
      <div>
        <label htmlFor={`${id}-estilo`} className={labelClass}>Perfil de fala</label>
        <select
          id={`${id}-estilo`}
          className={inputClass}
          value={estilo}
          aria-describedby={`${id}-estilo-dica`}
          onChange={(e) => {
            const escolhido = ESTILOS_PROGRAMA[e.target.value];
            if (escolhido) onChange({ ...persona, ...escolhido.valores });
          }}
        >
          {Object.entries(ESTILOS_PROGRAMA).map(([valor, item]) => (
            <option key={valor} value={valor}>{item.nome}</option>
          ))}
          <option value="personalizado" disabled>Ajustes personalizados</option>
        </select>
        <p id={`${id}-estilo-dica`} className="mt-1 text-xs text-fg/65">
          {ESTILOS_PROGRAMA[estilo]?.descricao ?? "Seu estilo combina os ajustes abaixo."}
          {" "}Você pode ajustar cada característica. As orientações e os exemplos são preservados ao trocar o perfil.
        </p>
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {ESCALAS.map(({ campo, rotulo, dica }) => (
          <div key={campo}>
            <label htmlFor={`${id}-${campo}`} className={labelClass}>
              {rotulo}
            </label>
            <select
              id={`${id}-${campo}`}
              className={inputClass}
              value={persona[campo]}
              onChange={(e) => onChange({ ...persona, [campo]: Number(e.target.value) })}
              aria-describedby={`${id}-${campo}-dica`}
            >
              {[1, 2, 3, 4, 5].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
            <p id={`${id}-${campo}-dica`} className="mt-1 text-xs text-fg/65">
              {dica}
            </p>
          </div>
        ))}
      </div>
      <div>
        <label htmlFor={`${id}-girias`} className={labelClass}>Uso de gírias</label>
        <select id={`${id}-girias`} className={inputClass} value={persona.girias ?? "automatico"}
          onChange={(e) => onChange({ ...persona, girias: e.target.value as Persona["girias"] })}>
          <option value="automatico">Conforme a formalidade</option>
          <option value="evitar">Evitar gírias</option>
          <option value="moderadas">Gírias leves, ocasionalmente</option>
          <option value="frequentes">Mais gírias nos trechos leves</option>
        </select>
      </div>
      <div>
        <label htmlFor={`${id}-orientacoes`} className={labelClass}>Orientações para este programa</label>
        <textarea id={`${id}-orientacoes`} className={inputClass} rows={3}
          value={persona.orientacoes ?? ""} maxLength={PERSONA_MAX_ORIENTACOES}
          aria-describedby={`${id}-orientacoes-dica`}
          placeholder="Ex.: use expressões regionais nos comentários e seja direto nas notícias."
          onChange={(e) => onChange({ ...persona, orientacoes: e.target.value })} />
        <p id={`${id}-orientacoes-dica`} className="mt-1 text-xs text-fg/65">
          Descreva o vocabulário, a postura e a forma de interagir. Até {PERSONA_MAX_ORIENTACOES} caracteres.
        </p>
      </div>
      <ExemplosPersona id={`${id}-exemplos`} exemplos={persona.exemplos}
        onChange={(exemplos) => onChange({ ...persona, exemplos })} />
      <p className="text-xs text-fg/65">Use referências próprias de fala, sem imitar apresentadores reais.</p>
      <button
        type="button"
        className="text-sm text-fg/70 underline"
        onClick={() => onChange(null)}
      >
        Usar personalidade geral do radialista
      </button>
    </fieldset>
  );
}
