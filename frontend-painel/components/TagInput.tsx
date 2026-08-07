"use client";

import { useState } from "react";

type Props = {
  label: string;
  tags: string[];
  onChange: (tags: string[]) => void;
};

export default function TagInput({ label, tags, onChange }: Props) {
  const [texto, setTexto] = useState("");

  function adicionar() {
    const valor = texto.trim();
    if (valor && !tags.includes(valor)) {
      onChange([...tags, valor]);
    }
    setTexto("");
  }

  function remover(tag: string) {
    onChange(tags.filter((t) => t !== tag));
  }

  return (
    <div className="mb-4 min-w-0">
      <label className="block text-sm font-medium text-gray-700 mb-1.5">{label}</label>
      {tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2">
          {tags.map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center gap-1 rounded-full bg-brand-50 text-brand-700 border border-brand-200 pl-2.5 pr-1.5 py-0.5 text-sm"
            >
              {tag}
              <button
                type="button"
                onClick={() => remover(tag)}
                className="text-brand-500 hover:text-brand-700 leading-none text-base"
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
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              adicionar();
            }
          }}
          placeholder="Digite e pressione Enter"
          className="flex-1 min-w-0 rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:border-brand-300 focus:ring-2 focus:ring-brand-500/20"
        />
        <button
          type="button"
          onClick={adicionar}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          Adicionar
        </button>
      </div>
    </div>
  );
}
