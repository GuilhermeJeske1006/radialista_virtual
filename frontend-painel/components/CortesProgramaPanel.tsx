"use client";

import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "../lib/api";
import type { CorteAsRun } from "../lib/types";

// F14 item 2: cortes que fazem sentido sozinhos, marcados a partir do as-run (só leitura).
type Props = { programaId: number };

export default function CortesProgramaPanel({ programaId }: Props) {
  const [cortes, setCortes] = useState<CorteAsRun[] | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    apiFetch<CorteAsRun[]>(`/config/programas/${programaId}/cortes`)
      .then(setCortes)
      .catch((err) => setErro(err instanceof ApiError ? err.message : "Erro ao carregar cortes"));
  }, [programaId]);

  return (
    <section aria-label="Cortes do programa" className="space-y-3">
      <h3 className="font-mono text-xs uppercase tracking-wide text-acento-claro">Cortes</h3>
      <p className="text-xs text-fg/70">
        Trechos do que foi ao ar que começam e terminam em fala, sem falha nem pedido no meio.
      </p>
      {erro && <p role="alert" className="text-xs text-red-400">{erro}</p>}
      {cortes === null && !erro && <p className="text-xs text-fg/60">Carregando…</p>}
      {cortes?.length === 0 && (
        <p className="text-xs text-fg/60">Nenhum corte ainda. Eles aparecem conforme o programa vai ao ar.</p>
      )}
      <ul className="space-y-1 text-sm text-fg">
        {cortes?.map((c) => (
          <li key={c.ordem_inicio}>
            Eventos {c.ordem_inicio}–{c.ordem_fim} ({c.eventos}): {c.tipos.join(" → ")}
          </li>
        ))}
      </ul>
    </section>
  );
}
