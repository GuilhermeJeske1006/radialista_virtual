"use client";

import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "../lib/api";
import { AssuntoPauta } from "../lib/types";
import { LocufySpin } from "./LocufyLogo";

const ORIGEM_LABEL: Record<string, string> = {
  noticia: "Notícia",
  musica: "Música",
  efemeride: "Efeméride",
  ouvinte: "Ouvinte",
  reserva: "Reserva",
};

type PautaDoDiaSectionProps = {
  programaId: number;
};

// Ver Fase H do plano-assuntos.md e backend app/topics/router.py -- lista os ganchos que o
// pipeline (derivação + casamento, ver app/topics/matcher.py) já preparou pra este programa,
// com controle editorial: fixar sobe a prioridade, descartar tira da pauta. Lista vazia é
// normal logo após ligar o recurso (o worker roda em ciclo de ~10min, ver app/news/worker.py) --
// não é erro nem trava o programa, o comentário livre continua funcionando enquanto isso.
export default function PautaDoDiaSection({ programaId }: PautaDoDiaSectionProps) {
  const [pauta, setPauta] = useState<AssuntoPauta[] | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");
  const [processandoId, setProcessandoId] = useState<number | null>(null);

  function carregar() {
    setCarregando(true);
    apiFetch<AssuntoPauta[]>(`/topics/programas/${programaId}/pauta`)
      .then((dados) => setPauta(Array.isArray(dados) ? dados : []))
      .catch((err) => setErro(err instanceof ApiError ? err.message : "Erro ao carregar a pauta do dia"))
      .finally(() => setCarregando(false));
  }

  useEffect(carregar, [programaId]);

  async function fixar(id: number) {
    setProcessandoId(id);
    setErro("");
    try {
      const atualizado = await apiFetch<AssuntoPauta>(`/topics/programas/${programaId}/pauta/${id}/fixar`, {
        method: "POST",
      });
      setPauta((atual) =>
        (atual ?? []).map((item) => (item.id === atualizado.id ? atualizado : item)).sort((a, b) => b.score - a.score)
      );
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao fixar assunto");
    } finally {
      setProcessandoId(null);
    }
  }

  async function descartar(id: number) {
    setProcessandoId(id);
    setErro("");
    try {
      await apiFetch(`/topics/programas/${programaId}/pauta/${id}`, { method: "DELETE" });
      setPauta((atual) => (atual ?? []).filter((item) => item.id !== id));
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao descartar assunto");
    } finally {
      setProcessandoId(null);
    }
  }

  if (carregando) {
    return (
      <p className="flex items-center gap-2 text-sm text-fg/65">
        <LocufySpin size={16} /> Carregando pauta do dia...
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-fg/65">
        Ganchos de conversa que o sistema já casou com este programa (notícia, música, pedido de
        ouvinte, reserva estratégica) -- o comentário ao vivo escolhe entre eles automaticamente.
        Fixe pra garantir prioridade ou descarte o que não fizer sentido.
      </p>

      {erro && <p className="text-sm text-rust-text">{erro}</p>}

      <div className="space-y-2">
        {(pauta ?? []).map((item) => (
          <div key={item.id} className="rounded-lg border border-border-strong p-3 space-y-1.5">
            <div className="flex items-start justify-between gap-2">
              <div>
                <span className="mr-2 rounded-full border border-border-strong px-2 py-0.5 text-[10px] uppercase tracking-wide text-fg/60">
                  {ORIGEM_LABEL[item.origem] ?? item.origem}
                </span>
                <span className="text-sm font-medium text-fg">{item.titulo}</span>
              </div>
              <span className="shrink-0 text-xs text-fg/50">score {item.score.toFixed(1)}</span>
            </div>
            <p className="text-sm text-fg/80">{item.gancho}</p>
            {item.ponte && <p className="text-xs italic text-fg/60">{item.ponte}</p>}
            <div className="flex items-center gap-3 pt-1">
              <button
                type="button"
                onClick={() => fixar(item.id)}
                disabled={processandoId === item.id}
                className="text-xs font-medium text-amber-text hover:text-amber-dim disabled:opacity-60"
              >
                Fixar
              </button>
              <button
                type="button"
                onClick={() => descartar(item.id)}
                disabled={processandoId === item.id}
                className="text-xs font-medium text-rust-text hover:text-rust/80 disabled:opacity-60"
              >
                Descartar
              </button>
            </div>
          </div>
        ))}
        {(pauta ?? []).length === 0 && (
          <p className="text-sm text-fg/65">
            Nenhum assunto casado ainda. O worker de apuração roda a cada ~10 minutos e preenche
            isso sozinho conforme notícia, música e pedido de ouvinte forem entrando.
          </p>
        )}
      </div>
    </div>
  );
}
