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
      <Link
        href="/dashboard"
        className="text-sm font-medium text-brand-600 hover:text-brand-700"
      >
        Criar primeiro radialista
      </Link>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <label className="text-sm font-medium text-gray-500 shrink-0">Radialista</label>
      <select
        className="rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:border-brand-300 focus:ring-2 focus:ring-brand-500/20"
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
        href={selecionadoId ? `/dashboard/${selecionadoId}` : "/dashboard"}
        className="text-sm font-medium text-brand-600 hover:text-brand-700 whitespace-nowrap"
      >
        Gerenciar
      </Link>
    </div>
  );
}
