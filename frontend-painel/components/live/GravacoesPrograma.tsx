"use client";

import { useEffect, useState } from "react";
import { apiFetch, apiFetchDownload } from "../../lib/api";

type Gravacao = { id: number; criado_em: string; tamanho_bytes: number; escopo: string };

export default function GravacoesPrograma({ programaId, ativo }: { programaId: number | null; ativo: boolean }) {
  const [gravacoes, setGravacoes] = useState<Gravacao[]>([]);
  const [erro, setErro] = useState("");
  useEffect(() => {
    setGravacoes([]);
    if (!programaId) return;
    let cancelado = false;
    const carregar = () => apiFetch<Gravacao[]>(`/live/programas/${programaId}/gravacoes`)
      .then(itens => { if (!cancelado) { setGravacoes(itens); setErro(""); } })
      .catch(() => { if (!cancelado) setErro("Não foi possível consultar as gravações."); });
    void carregar();
    const exportada = (evento: Event) => {
      if ((evento as CustomEvent).detail?.arquivada === false) {
        setErro("O MP3 foi exportado, mas não foi possível arquivar a cópia. Guarde o arquivo baixado.");
      } else void carregar();
    };
    window.addEventListener("gravacao-exportada", exportada);
    return () => { cancelado = true; window.removeEventListener("gravacao-exportada", exportada); };
  }, [programaId, ativo]);
  if (!programaId) return null;
  return <section className="rounded-3xl border border-border-strong bg-surface shadow-theme-xs p-6 space-y-3">
    <h2 className="font-display text-base font-bold text-fg">Gravações do programa</h2>
    <p className="text-sm text-fg/65">Ao exportar com o áudio da aba compartilhado, o programa completo fica disponível por sete dias.</p>
    {erro && <p role="alert" className="text-sm text-red-500">{erro}</p>}
    {gravacoes.length === 0 && !erro && <p className="text-sm text-fg/65">Nenhuma gravação arquivada.</p>}
    <ul className="space-y-2">{gravacoes.map(g => <li key={g.id}>
      <button type="button" className="text-sm text-acento-claro underline hover:no-underline focus-visible:outline-2 focus-visible:outline-acento-claro" onClick={() => {
        apiFetchDownload(`/live/programas/${programaId}/gravacoes/${g.id}/audio`, `programa-${programaId}-${g.id}.mp3`)
          .catch(() => setErro("Não foi possível baixar a gravação."));
      }}>Baixar programa de {new Date(g.criado_em).toLocaleString("pt-BR")} ({Math.ceil(g.tamanho_bytes / 1024 / 1024)} MB)</button>
    </li>)}</ul>
  </section>;
}
