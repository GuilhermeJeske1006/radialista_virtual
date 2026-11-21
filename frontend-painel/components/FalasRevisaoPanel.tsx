"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch, ApiError } from "../lib/api";
import type { FalaRevisao } from "../lib/types";

// F12: falas que o roteamento não deixou ir ao ar sozinhas. Aprovar só libera o texto para conferência;
// a fala não vai ao ar daqui. Decisão só vale dentro do prazo (ver backend app/live/revisao.py).
type Props = { programaId: number };

function formatarPrazo(iso: string | null): string {
  if (!iso) return "sem prazo";
  return new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

export default function FalasRevisaoPanel({ programaId }: Props) {
  const [falas, setFalas] = useState<FalaRevisao[] | null>(null);
  const [erro, setErro] = useState("");
  const [decidindoId, setDecidindoId] = useState<number | null>(null);

  const carregar = useCallback(() => {
    apiFetch<FalaRevisao[]>(`/config/programas/${programaId}/falas-revisao?estado=aguardando_revisao`)
      .then(setFalas)
      .catch((err) => setErro(err instanceof ApiError ? err.message : "Erro ao carregar falas em revisão"));
  }, [programaId]);

  useEffect(carregar, [carregar]);

  async function decidir(fala: FalaRevisao, acao: "aprovar" | "rejeitar") {
    setDecidindoId(fala.id);
    setErro("");
    try {
      await apiFetch(`/config/programas/${programaId}/falas-revisao/${fala.id}/${acao}`, { method: "POST" });
      setFalas((atual) => atual?.filter((f) => f.id !== fala.id) ?? atual);
    } catch (err) {
      setErro(
        err instanceof ApiError && err.status === 409
          ? "Esta fala já passou do prazo ou já foi decidida."
          : err instanceof ApiError ? err.message : "Erro ao registrar a decisão",
      );
      carregar();
    } finally {
      setDecidindoId(null);
    }
  }

  return (
    <section aria-label="Falas em revisão" className="space-y-3">
      <h3 className="font-mono text-xs uppercase tracking-wide text-acento-claro">Falas aguardando revisão</h3>
      <p className="text-xs text-fg/70">
        Aprovar só libera o texto para conferência: a fala não vai ao ar daqui. Cada fala vale até o prazo indicado.
      </p>
      {erro && <p role="alert" className="text-xs text-red-400">{erro}</p>}
      {falas === null && !erro && <p className="text-xs text-fg/60">Carregando…</p>}
      {falas?.length === 0 && <p className="text-xs text-fg/60">Nenhuma fala aguardando revisão.</p>}
      {falas?.map((fala) => (
        <article key={fala.id} className="space-y-2 rounded-xl border border-border p-3">
          <p className="text-xs text-fg/60">
            {fala.categoria} · motivo: {fala.motivo.replace("_", " ")} · até {formatarPrazo(fala.prazo_em)}
          </p>
          <p className="whitespace-pre-line text-sm text-fg">{fala.texto}</p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => decidir(fala, "aprovar")}
              disabled={decidindoId === fala.id}
              className="rounded-xl border border-border-strong px-3 py-1.5 text-xs font-medium text-fg/80 hover:bg-fg/5 disabled:opacity-60"
            >
              Aprovar
            </button>
            <button
              type="button"
              onClick={() => decidir(fala, "rejeitar")}
              disabled={decidindoId === fala.id}
              className="rounded-xl border border-border-strong px-3 py-1.5 text-xs font-medium text-fg/80 hover:bg-fg/5 disabled:opacity-60"
            >
              Rejeitar
            </button>
          </div>
        </article>
      ))}
    </section>
  );
}
