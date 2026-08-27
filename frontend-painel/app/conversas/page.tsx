"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "../../components/AppShell";
import { apiFetch, apiFetchDownload, ApiError } from "../../lib/api";
import { STATUS_COR, STATUS_LABEL } from "../../lib/statusInteracao";
import { LocufySpin } from "../../components/LocufyLogo";

type Interacao = {
  id: number;
  telefone: string;
  nome: string | null;
  mensagem_usuario: string;
  resposta: string | null;
  status: string;
  criado_em: string;
  radialista_nome: string;
  origem: "ouvinte" | "radio";
};

type Conversa = {
  telefone: string;
  nome: string | null;
  radialista_nome: string;
  ultima_mensagem: string;
  ultimo_status: string;
  ultima_em: string;
  total_mensagens: number;
};

type ConversasPaginadas = {
  conversas: Conversa[];
  pagina: number;
  tamanho_pagina: number;
  total: number;
  total_paginas: number;
};

type MensagensPaginadas = {
  mensagens: Interacao[];
  pagina: number;
  tamanho_pagina: number;
  total: number;
  total_paginas: number;
};

function formatarHora(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function Avatar({ telefone, nome, tamanho }: { telefone: string; nome: string | null; tamanho: number }) {
  const [url, setUrl] = useState<string | null>(null);
  const [falhou, setFalhou] = useState(false);

  useEffect(() => {
    let cancelado = false;
    setUrl(null);
    setFalhou(false);
    apiFetch<{ url: string | null }>(`/metrics/conversations/${encodeURIComponent(telefone)}/avatar`)
      .then((dados) => {
        if (!cancelado) setUrl(dados.url);
      })
      .catch(() => {
        if (!cancelado) setFalhou(true);
      });
    return () => {
      cancelado = true;
    };
  }, [telefone]);

  if (url && !falhou) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={url}
        alt={nome || telefone}
        onError={() => setFalhou(true)}
        style={{ width: tamanho, height: tamanho }}
        className="rounded-full object-cover shrink-0"
      />
    );
  }

  const inicial = (nome || telefone).trim().charAt(0).toUpperCase();
  return (
    <div
      style={{ width: tamanho, height: tamanho }}
      className="rounded-full bg-brand-500/20 text-brand-600 flex items-center justify-center text-xs font-semibold shrink-0"
    >
      {inicial}
    </div>
  );
}

const OPCOES_PERIODO = [
  { valor: "7", label: "Últimos 7 dias" },
  { valor: "30", label: "Últimos 30 dias" },
  { valor: "90", label: "Últimos 90 dias" },
  { valor: "", label: "Tudo" },
];

export default function ConversasPage() {
  const [conversas, setConversas] = useState<Conversa[]>([]);
  const [carregandoConversas, setCarregandoConversas] = useState(true);
  const [paginaConversas, setPaginaConversas] = useState(1);
  const [totalPaginasConversas, setTotalPaginasConversas] = useState(1);

  const [telefoneSelecionado, setTelefoneSelecionado] = useState<string | null>(null);
  const [mensagens, setMensagens] = useState<Interacao[]>([]);
  const [carregandoMensagens, setCarregandoMensagens] = useState(false);
  const [paginaMensagens, setPaginaMensagens] = useState(1);
  const [totalPaginasMensagens, setTotalPaginasMensagens] = useState(1);

  const [periodoExport, setPeriodoExport] = useState("30");
  const [exportando, setExportando] = useState(false);
  const [erroExport, setErroExport] = useState("");

  async function exportarCsv() {
    setExportando(true);
    setErroExport("");
    try {
      const params = periodoExport ? `?dias=${periodoExport}` : "";
      const hoje = new Date().toISOString().slice(0, 10);
      await apiFetchDownload(`/metrics/export${params}`, `interacoes-${hoje}.csv`);
    } catch (err) {
      setErroExport(err instanceof ApiError ? err.message : "Erro ao exportar CSV");
    } finally {
      setExportando(false);
    }
  }

  async function carregarConversas(pagina: number) {
    setCarregandoConversas(true);
    try {
      const dados = await apiFetch<ConversasPaginadas>(
        `/metrics/conversations?pagina=${pagina}&tamanho_pagina=10`
      );
      setConversas(dados.conversas);
      setPaginaConversas(dados.pagina);
      setTotalPaginasConversas(dados.total_paginas);
    } catch {
      // ignora falha isolada, mantem lista anterior
    } finally {
      setCarregandoConversas(false);
    }
  }

  async function carregarMensagens(telefone: string, pagina: number) {
    setCarregandoMensagens(true);
    try {
      const dados = await apiFetch<MensagensPaginadas>(
        `/metrics/conversations/${encodeURIComponent(telefone)}/messages?pagina=${pagina}&tamanho_pagina=20`
      );
      setMensagens(dados.mensagens);
      setPaginaMensagens(dados.pagina);
      setTotalPaginasMensagens(dados.total_paginas);
    } catch {
      // ignora falha isolada, mantem lista anterior
    } finally {
      setCarregandoMensagens(false);
    }
  }

  function selecionarConversa(telefone: string) {
    setTelefoneSelecionado(telefone);
    carregarMensagens(telefone, 1);
  }

  const nomeSelecionado =
    conversas.find((c) => c.telefone === telefoneSelecionado)?.nome ??
    mensagens.find((m) => m.nome)?.nome ??
    null;

  useEffect(() => {
    carregarConversas(1);
  }, []);

  return (
    <AppShell title="Conversas" maxWidthClassName="max-w-4xl">
      <div className="flex flex-wrap items-end justify-between gap-4 mb-4">
        <p className="text-sm text-fg/65">
          Conversas dos ouvintes, separadas por número, e o que o sistema fez com cada mensagem. Pra ver
          totais e gráficos,{" "}
          <Link href="/metrics" className="text-amber-text hover:text-amber-dim font-medium">
            acesse Métricas
          </Link>
          .
        </p>
        <div className="flex items-end gap-2">
          <div>
            <label className="block text-sm font-medium text-fg/80 mb-1.5">Período do CSV</label>
            <select
              aria-label="Período do CSV"
              value={periodoExport}
              onChange={(e) => setPeriodoExport(e.target.value)}
              className="rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
            >
              {OPCOES_PERIODO.map((opcao) => (
                <option key={opcao.valor} value={opcao.valor}>
                  {opcao.label}
                </option>
              ))}
            </select>
          </div>
          <button
            type="button"
            onClick={exportarCsv}
            disabled={exportando}
            className="rounded-lg border border-border-strong px-4 py-2 text-sm font-medium text-fg hover:bg-paper/5 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {exportando ? "Exportando..." : "Exportar CSV"}
          </button>
        </div>
      </div>
      {erroExport && <p className="text-sm text-rust-text mb-4">{erroExport}</p>}

      <div className="flex gap-4 h-130">
        {/* Lista de conversas, tipo lista de chats do WhatsApp */}
        <div className="w-72 shrink-0 bg-surface rounded-2xl border border-border-strong shadow-theme-xs flex flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto divide-y divide-border-strong">
            {carregandoConversas ? (
              <p className="flex items-center gap-2 text-sm text-fg/65 p-4">
                <LocufySpin size={16} /> Carregando...
              </p>
            ) : conversas.length === 0 ? (
              <p className="text-sm text-fg/65 p-4">Nenhuma conversa ainda.</p>
            ) : (
              conversas.map((conversa) => (
                <button
                  key={conversa.telefone}
                  onClick={() => selecionarConversa(conversa.telefone)}
                  className={`w-full text-left p-3 hover:bg-paper/70 transition-colors ${
                    telefoneSelecionado === conversa.telefone ? "bg-brand-500/10" : ""
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <Avatar telefone={conversa.telefone} nome={conversa.nome} tamanho={36} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-sm font-medium text-fg truncate">
                          {conversa.nome || conversa.telefone}
                        </span>
                        <span className="text-[11px] text-fg/65 shrink-0">{formatarHora(conversa.ultima_em)}</span>
                      </div>
                      <p className="text-xs text-fg/65 truncate mt-0.5">{conversa.ultima_mensagem}</p>
                      <div className="flex items-center justify-between mt-1">
                        <span className="text-[11px] text-fg/65 truncate">
                          {conversa.nome ? `${conversa.telefone} · ` : ""}
                          {conversa.radialista_nome}
                        </span>
                        <span className="text-[11px] rounded-full bg-paper px-1.5 py-0.5 text-fg/65 shrink-0">
                          {conversa.total_mensagens}
                        </span>
                      </div>
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>
          <div className="flex items-center justify-between p-2.5 border-t border-border-strong text-xs text-fg/65">
            <button
              onClick={() => carregarConversas(paginaConversas - 1)}
              disabled={paginaConversas <= 1 || carregandoConversas}
              className="disabled:opacity-40 hover:text-fg"
            >
              ‹ Anterior
            </button>
            <span>
              {paginaConversas}/{totalPaginasConversas}
            </span>
            <button
              onClick={() => carregarConversas(paginaConversas + 1)}
              disabled={paginaConversas >= totalPaginasConversas || carregandoConversas}
              className="disabled:opacity-40 hover:text-fg"
            >
              Próxima ›
            </button>
          </div>
        </div>

        {/* Thread da conversa selecionada, tipo tela de chat do WhatsApp */}
        <div className="flex-1 bg-surface rounded-2xl border border-border-strong shadow-theme-xs flex flex-col overflow-hidden">
          {!telefoneSelecionado ? (
            <p className="text-sm text-fg/65 m-auto">Selecione uma conversa para ver as mensagens.</p>
          ) : (
            <>
              <div className="p-3 border-b border-border-strong flex items-center gap-3">
                <Avatar telefone={telefoneSelecionado} nome={nomeSelecionado} tamanho={40} />
                <div>
                  <p className="text-sm font-medium text-fg">{nomeSelecionado || telefoneSelecionado}</p>
                  {nomeSelecionado && <p className="text-xs text-fg/65">{telefoneSelecionado}</p>}
                </div>
              </div>

              <div className="flex-1 overflow-y-auto p-4 bg-paper/40 flex flex-col gap-3">
                {paginaMensagens < totalPaginasMensagens && (
                  <button
                    onClick={() => carregarMensagens(telefoneSelecionado, paginaMensagens + 1)}
                    disabled={carregandoMensagens}
                    className="text-xs text-brand-600 hover:underline self-center disabled:opacity-40"
                  >
                    ↑ Carregar mensagens mais antigas
                  </button>
                )}

                {carregandoMensagens ? (
                  <p className="flex items-center gap-2 text-sm text-fg/65 m-auto">
                    <LocufySpin size={16} /> Carregando...
                  </p>
                ) : (
                  mensagens.map((mensagem) => {
                    const enviadaPelaRadio = mensagem.origem === "radio";
                    return (
                      <div key={mensagem.id} className={`max-w-[80%] ${enviadaPelaRadio ? "self-end" : "self-start"}`}>
                        <div
                          className={`border px-3 py-2 shadow-theme-xs rounded-xl ${
                            enviadaPelaRadio
                              ? "bg-teal/15 border-teal/25 rounded-tr-none"
                              : "bg-surface border-border-strong rounded-tl-none"
                          }`}
                        >
                          <p className="text-sm text-fg">{mensagem.mensagem_usuario}</p>
                        </div>
                        <div
                          className={`flex items-center gap-2 mt-1 ${enviadaPelaRadio ? "justify-end mr-1" : "ml-1"}`}
                        >
                          <span className="text-[11px] text-fg/65">{formatarHora(mensagem.criado_em)}</span>
                          <span className="text-[11px] text-fg/65">·</span>
                          <span className="text-[11px] text-fg/65">
                            {enviadaPelaRadio ? `${mensagem.radialista_nome} (rádio)` : mensagem.radialista_nome}
                          </span>
                        </div>
                        {!enviadaPelaRadio && (
                          <p className={`text-[11px] mt-0.5 ml-1 ${STATUS_COR[mensagem.status] ?? "text-fg/65"}`}>
                            {STATUS_LABEL[mensagem.status] ?? mensagem.status}
                          </p>
                        )}
                      </div>
                    );
                  })
                )}

                {paginaMensagens > 1 && !carregandoMensagens && (
                  <button
                    onClick={() => carregarMensagens(telefoneSelecionado, paginaMensagens - 1)}
                    className="text-xs text-brand-600 hover:underline self-center"
                  >
                    Mensagens mais recentes ↓
                  </button>
                )}
              </div>

              <div className="flex items-center justify-center p-2 border-t border-border-strong text-xs text-fg/65">
                página {paginaMensagens}/{totalPaginasMensagens}
              </div>
            </>
          )}
        </div>
      </div>
    </AppShell>
  );
}
