"use client";

import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "../../lib/api";
import { LocufySpin } from "../LocufyLogo";

type PedidoFila = {
  id: number;
  telefone: string;
  nome: string;
  tipo: "abraco" | "musica";
  mensagem_usuario: string;
  musica_query: string | null;
  atendido: boolean;
  estado: string;
  atendido_em: string | null;
  criado_em: string;
};

type FilaHistoricoPaginada = {
  pedidos: PedidoFila[];
  pagina: number;
  tamanho_pagina: number;
  total: number;
  total_paginas: number;
};

type Filtro = "todos" | "atendidos" | "pendentes";

const TAMANHO_PAGINA = 8;

function formatarHora(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

type Props = {
  radialistaId: number | null;
};

export default function HistoricoFilaPanel({ radialistaId }: Props) {
  const [filtro, setFiltro] = useState<Filtro>("todos");
  const [pagina, setPagina] = useState(1);
  const [dados, setDados] = useState<FilaHistoricoPaginada | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");

  useEffect(() => {
    setPagina(1);
  }, [radialistaId, filtro]);

  useEffect(() => {
    if (radialistaId === null) return;
    let ativo = true;
    setCarregando(true);
    setErro("");

    const filtroQuery = filtro === "todos" ? "" : `&atendido=${filtro === "atendidos"}`;
    apiFetch<FilaHistoricoPaginada>(
      `/live/${radialistaId}/fila/historico?pagina=${pagina}&tamanho_pagina=${TAMANHO_PAGINA}${filtroQuery}`
    )
      .then((resposta) => {
        if (ativo) setDados(resposta);
      })
      .catch((err) => {
        if (ativo) setErro(err instanceof ApiError ? err.message : "Erro ao carregar histórico da fila");
      })
      .finally(() => {
        if (ativo) setCarregando(false);
      });

    return () => {
      ativo = false;
    };
  }, [radialistaId, filtro, pagina]);

  return (
    <section className="bg-surface rounded-3xl border border-border-strong shadow-theme-xs p-6">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-display text-base font-bold text-fg">Histórico da fila</h2>
        {dados && <span className="font-mono text-xs text-fg/65">{dados.total} pedido(s)</span>}
      </div>
      <p className="text-xs text-fg/65 mb-3">Pedidos de música e recado recebidos pelo WhatsApp, últimos 30 dias.</p>

      <div className="flex gap-1.5 mb-3">
        {(["todos", "pendentes", "atendidos"] as const).map((opcao) => (
          <button
            key={opcao}
            type="button"
            onClick={() => setFiltro(opcao)}
            className={`rounded-full px-3 py-1 text-xs font-medium capitalize transition-colors ${
              filtro === opcao ? "bg-acento/15 text-acento-claro" : "text-fg/65 hover:bg-fg/5"
            }`}
          >
            {opcao}
          </button>
        ))}
      </div>

      {erro && <p className="text-sm text-laranja mb-3">{erro}</p>}

      {carregando ? (
        <p className="flex items-center gap-2 text-sm text-fg/65">
          <LocufySpin size={16} /> Carregando…
        </p>
      ) : !dados || dados.pedidos.length === 0 ? (
        <p className="text-sm text-fg/65">Nenhum pedido nesse filtro.</p>
      ) : (
        <div tabIndex={0} role="region" aria-label="Pedidos da fila" className="space-y-2 max-h-72 overflow-y-auto pr-1 -mr-1 rounded-xl focus-visible:outline-2 focus-visible:outline-acento-claro">
          {dados.pedidos.map((pedido) => (
            <div key={pedido.id} className="rounded-xl border border-border px-3 py-2">
              <div className="flex items-center justify-between gap-2 mb-1">
                <span className="text-xs font-medium text-fg truncate">
                  {pedido.nome || pedido.telefone} · {pedido.tipo === "musica" ? "🎵 música" : "👋 recado"}
                </span>
                <span
                  className={`shrink-0 text-[11px] font-medium rounded-full px-2 py-0.5 ${
                    pedido.atendido ? "bg-ciano/10 text-ciano" : "bg-acento/10 text-acento-claro"
                  }`}
                >
                  {pedido.estado === "historico_legado" ? "Histórico legado" : pedido.atendido ? "Executado" : ({em_fila: "Na fila", aguardando_revisao: "Em revisão", selecionado: "Selecionado", expirado: "Expirado", cancelado: "Cancelado", nao_atendido: "Não atendido"} as Record<string, string>)[pedido.estado] || "Pendente"}
                </span>
              </div>
              <p className="text-xs text-fg/65 truncate">{pedido.musica_query || pedido.mensagem_usuario}</p>
              <p className="text-[11px] text-fg/65 mt-1">{formatarHora(pedido.criado_em)}</p>
            </div>
          ))}
        </div>
      )}

      {dados && dados.total_paginas > 1 && (
        <div className="flex items-center justify-between mt-3 pt-3 border-t border-border text-xs text-fg/65">
          <button
            onClick={() => setPagina((p) => p - 1)}
            disabled={pagina <= 1 || carregando}
            className="disabled:opacity-40 hover:text-fg"
          >
            ‹ Anterior
          </button>
          <span>
            {dados.pagina}/{dados.total_paginas}
          </span>
          <button
            onClick={() => setPagina((p) => p + 1)}
            disabled={pagina >= dados.total_paginas || carregando}
            className="disabled:opacity-40 hover:text-fg"
          >
            Próxima ›
          </button>
        </div>
      )}
    </section>
  );
}
