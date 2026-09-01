"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "../lib/api";
import { Notificacao } from "../lib/types";

const INTERVALO_CONTAGEM_MS = 30_000;

function useContagemNaoLidas(atualizarQuando: number) {
  const [total, setTotal] = useState(0);

  useEffect(() => {
    let cancelado = false;
    function buscar() {
      apiFetch<{ total: number }>("/notificacoes/contagem-nao-lidas")
        .then((r) => {
          if (!cancelado) setTotal(r.total);
        })
        .catch(() => {
          // ignora falha isolada, mantem o ultimo total conhecido
        });
    }
    buscar();
    const intervalo = setInterval(buscar, INTERVALO_CONTAGEM_MS);
    return () => {
      cancelado = true;
      clearInterval(intervalo);
    };
  }, [atualizarQuando]);

  return total;
}

export default function NotificationBell() {
  const [aberto, setAberto] = useState(false);
  const [notificacoes, setNotificacoes] = useState<Notificacao[]>([]);
  const [carregando, setCarregando] = useState(false);
  const [versao, setVersao] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const totalNaoLidas = useContagemNaoLidas(versao);

  useEffect(() => {
    if (!aberto) return;
    function aoClicarFora(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setAberto(false);
      }
    }
    document.addEventListener("mousedown", aoClicarFora);
    return () => document.removeEventListener("mousedown", aoClicarFora);
  }, [aberto]);

  function abrir() {
    setAberto((atual) => !atual);
    if (!aberto) {
      setCarregando(true);
      apiFetch<{ notificacoes: Notificacao[] }>("/notificacoes")
        .then((r) => setNotificacoes(r.notificacoes))
        .catch(() => setNotificacoes([]))
        .finally(() => setCarregando(false));
    }
  }

  async function marcarTodasLidas() {
    await apiFetch("/notificacoes/marcar-todas-lidas", { method: "POST" }).catch(() => {});
    setNotificacoes((atual) => atual.map((n) => ({ ...n, lida: true })));
    setVersao((v) => v + 1);
  }

  async function clicarNotificacao(n: Notificacao) {
    if (!n.lida) {
      await apiFetch(`/notificacoes/${n.id}/marcar-lida`, { method: "POST" }).catch(() => {});
      setNotificacoes((atual) => atual.map((item) => (item.id === n.id ? { ...item, lida: true } : item)));
      setVersao((v) => v + 1);
    }
    setAberto(false);
    if (n.link) router.push(n.link);
  }

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={abrir}
        title="Notificações"
        className="relative flex h-8 w-8 items-center justify-center rounded-full text-fg/70 hover:bg-paper/10 hover:text-fg"
      >
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0"
          />
        </svg>
        {totalNaoLidas > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-rust px-1 text-[10px] font-semibold text-white">
            {totalNaoLidas > 9 ? "9+" : totalNaoLidas}
          </span>
        )}
      </button>

      {aberto && (
        <div className="absolute right-0 top-10 z-20 w-80 max-w-[calc(100vw-2.5rem)] rounded-xl border border-border-strong bg-surface shadow-lg">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <span className="font-display text-sm font-bold text-fg">Notificações</span>
            {notificacoes.some((n) => !n.lida) && (
              <button type="button" onClick={marcarTodasLidas} className="text-xs text-amber-text hover:underline">
                Marcar todas como lidas
              </button>
            )}
          </div>
          <div className="max-h-80 overflow-y-auto">
            {carregando && <p className="px-4 py-6 text-center text-xs text-fg/50">Carregando...</p>}
            {!carregando && notificacoes.length === 0 && (
              <p className="px-4 py-6 text-center text-xs text-fg/50">Nenhuma notificação por aqui.</p>
            )}
            {notificacoes.map((n) => (
              <button
                key={n.id}
                type="button"
                onClick={() => clicarNotificacao(n)}
                className={`block w-full border-b border-border px-4 py-3 text-left text-sm last:border-b-0 hover:bg-paper/5 ${
                  n.lida ? "text-fg/60" : "text-fg"
                }`}
              >
                <span className="font-medium">{n.titulo}</span>
                <p className="mt-0.5 text-xs text-fg/60">{n.mensagem}</p>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
