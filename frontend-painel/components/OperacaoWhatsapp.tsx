"use client";
import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../lib/api";
import { useEventosOuvintes } from "../hooks/useEventosOuvintes";
import { formatarTelefone } from "../lib/telefone";

type Operacao = { entradas: Record<string, number>; envios: Record<string, number>; falhas: { id: number; telefone: string }[] };
export default function OperacaoWhatsapp() {
  const [dados, setDados] = useState<Operacao | null>(null);
  const [erro, setErro] = useState("");
  const carregar = useCallback(() => {
    apiFetch<Operacao>("/ouvintes/operacao").then(setDados).catch(() => {});
  }, []);
  useEffect(carregar, [carregar]);
  useEventosOuvintes(carregar);
  if (!dados || (!dados.entradas?.falhou && !dados.envios?.incerto)) return null;
  return <details className="rounded-xl border border-laranja/30 bg-surface p-3 text-sm">
    <summary className="cursor-pointer">Conferir atendimento: {dados.entradas.falhou || 0} mensagens com falha e {dados.envios.incerto || 0} envios incertos</summary>
    <p className="my-2 text-xs text-fg/65">Confira os envios incertos na conversa e no WhatsApp antes de tentar novamente.</p>
    {dados.falhas.map(f => <div key={f.id} className="my-2 flex flex-wrap items-center gap-3 text-xs"><span>{formatarTelefone(f.telefone)}</span><button className="underline" onClick={async () => {
      try { await apiFetch(`/ouvintes/entradas/${f.id}/reprocessar`, { method: "POST" }); setErro(""); carregar(); }
      catch (e) { setErro(e instanceof Error ? e.message : "Não foi possível reprocessar"); }
    }}>Retomar processamento</button></div>)}
    {erro && <p role="alert" className="text-laranja">{erro}</p>}
  </details>;
}
