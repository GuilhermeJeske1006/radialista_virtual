"use client";

import { useEffect, useRef, useState } from "react";

type Estado = "conectando" | "conectado" | "reconectando";
type Assinante = { atualizar: () => void; estado: (estado: Estado) => void };
const assinantes = new Set<Assinante>();
let fonte: EventSource | null = null;
let fallback: ReturnType<typeof setInterval> | null = null;
let estado: Estado = "conectando";

function avisar() { assinantes.forEach(a => a.atualizar()); }
function mudar(proximo: Estado) { estado = proximo; assinantes.forEach(a => a.estado(estado)); }

/** Um stream por aplicação. Reconexão nativa usa Last-Event-ID e o servidor faz replay. */
export function useEventosOuvintes(atualizar: () => void) {
  const callback = useRef(atualizar);
  callback.current = atualizar;
  const [conexao, setConexao] = useState<Estado>(estado);
  useEffect(() => {
    const assinante = { atualizar: () => callback.current(), estado: setConexao };
    assinantes.add(assinante);
    if (!fonte && typeof EventSource !== "undefined") {
      fonte = new EventSource(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/ouvintes/eventos`, { withCredentials: true });
      fonte.onopen = () => mudar("conectado");
      fonte.onerror = () => mudar("reconectando");
      let agendado = false;
      fonte.addEventListener("atualizacao", () => {
        if (agendado) return;
        agendado = true;
        window.setTimeout(() => { agendado = false; avisar(); }, 150);
      });
      fallback = setInterval(() => { if (estado !== "conectado") avisar(); }, 15000);
    }
    setConexao(estado);
    return () => {
      assinantes.delete(assinante);
      if (!assinantes.size) {
        fonte?.close(); fonte = null;
        if (fallback) clearInterval(fallback);
        fallback = null; estado = "conectando";
      }
    };
  }, []);
  return conexao;
}
