"use client";

import Link from "next/link";
import { Radialista } from "../lib/types";

type Props = {
  radialistas: Radialista[];
  selecionadoId: number | null;
  onSelect: (id: number) => void;
};

export default function RadialistaSwitcher({ radialistas, selecionadoId, onSelect }: Props) {
  if (radialistas.length === 0) {
    return (
      <Link href="/radialista" className="text-sm font-medium text-amber hover:text-amber-dim">
        Criar primeiro radialista
      </Link>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <label className="text-sm font-medium text-fg/55 shrink-0">Radialista</label>
      <select
        className="rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
        value={selecionadoId ?? ""}
        onChange={(e) => onSelect(Number(e.target.value))}
      >
        {radialistas.map((r) => (
          <option key={r.id} value={r.id}>
            {r.nome_locutor || `Radialista #${r.id}`}
          </option>
        ))}
      </select>
      <Link
        href={selecionadoId ? `/radialista/${selecionadoId}` : "/radialista"}
        className="text-sm font-medium text-amber hover:text-amber-dim whitespace-nowrap"
      >
        Gerenciar
      </Link>
    </div>
  );
}
