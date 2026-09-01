"use client";

import { useEffect, useRef, useState } from "react";
import { apiFetch, ApiError } from "../lib/api";
import { LocufySpin } from "./LocufyLogo";

type Mensagem = { role: "user" | "assistant"; content: string };

const SAUDACAO: Mensagem = {
  role: "assistant",
  content: "Oi! Sou o assistente da Locufy. Pode perguntar sobre como usar o painel — radialistas, programação, WhatsApp, planos etc.",
};

export default function SuporteChat() {
  const [aberto, setAberto] = useState(false);
  const [mensagens, setMensagens] = useState<Mensagem[]>([SAUDACAO]);
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState("");
  const fimRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (aberto) fimRef.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [mensagens, aberto]);

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    const pergunta = texto.trim();
    if (!pergunta || enviando) return;

    const historico = mensagens.filter((m) => m !== SAUDACAO);
    setMensagens((atual) => [...atual, { role: "user", content: pergunta }]);
    setTexto("");
    setErro("");
    setEnviando(true);
    try {
      const resposta = await apiFetch<{ resposta: string }>("/suporte/chat", {
        method: "POST",
        body: JSON.stringify({ mensagem: pergunta, historico }),
      });
      setMensagens((atual) => [...atual, { role: "assistant", content: resposta.resposta }]);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Não consegui responder agora.");
    } finally {
      setEnviando(false);
    }
  }

  if (!aberto) {
    return (
      <button
        type="button"
        onClick={() => setAberto(true)}
        title="Suporte"
        className="fixed bottom-24 right-5 z-40 flex h-12 w-12 items-center justify-center rounded-full bg-amber text-ink shadow-lg hover:bg-amber/90"
      >
        <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z"
          />
        </svg>
      </button>
    );
  }

  return (
    <div className="fixed bottom-5 right-5 z-40 flex h-[32rem] w-96 max-w-[calc(100vw-2.5rem)] flex-col rounded-2xl border border-border-strong bg-surface shadow-lg">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <span className="font-display text-sm font-bold text-fg">Suporte Locufy</span>
        <button type="button" onClick={() => setAberto(false)} className="text-fg/50 hover:text-fg" title="Fechar">
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
        {mensagens.map((m, i) => (
          <div
            key={i}
            className={`max-w-[85%] rounded-xl px-3 py-2 text-sm leading-relaxed ${
              m.role === "user" ? "ml-auto bg-amber/15 text-fg" : "bg-paper/5 text-fg/85"
            }`}
          >
            {m.content}
          </div>
        ))}
        {enviando && (
          <p className="flex items-center gap-2 text-xs text-fg/50">
            <LocufySpin size={14} /> Pensando...
          </p>
        )}
        {erro && <p className="text-xs text-rust-text">{erro}</p>}
        <div ref={fimRef} />
      </div>

      <form onSubmit={enviar} className="flex items-center gap-2 border-t border-border p-3">
        <input
          type="text"
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          disabled={enviando}
          placeholder="Digite sua dúvida..."
          className="flex-1 rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg placeholder:text-fg/50 focus:outline-none focus:ring-2 focus:ring-amber/30 disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={enviando || !texto.trim()}
          className="rounded-lg bg-amber px-3 py-2 text-sm font-medium text-ink hover:bg-amber/90 disabled:opacity-60"
        >
          Enviar
        </button>
      </form>
    </div>
  );
}
