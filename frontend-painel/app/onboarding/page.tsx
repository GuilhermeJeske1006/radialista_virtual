"use client";

import { useEffect, useRef, useState } from "react";
import AppShell from "../../components/AppShell";
import ConfirmDialog from "../../components/ConfirmDialog";
import { apiFetch, ApiError } from "../../lib/api";
import { OndaLed, OndaSpin } from "../../components/OndaLogo";

type QrResponse = { data?: { QRCode?: string } };
type StatusResponse = { data?: { loggedIn?: boolean; connected?: boolean } };

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

const STATUS_LABEL: Record<string, string> = {
  fila_musica: "Pedido de música enviado ao locutor",
  fila_abraco: "Recado/abraço enviado ao locutor",
  bloqueado_horario: "Bloqueada — fora do horário do programa",
  bloqueado_rate_limit: "Bloqueada — limite de mensagens por hora",
  bloqueado_conteudo: "Bloqueada — conteúdo não permitido",
  bloqueado_plano: "Bloqueada — limite de mensagens do plano",
  guardado: "Registrada, sem ação",
};

const STATUS_COR: Record<string, string> = {
  fila_musica: "text-teal",
  fila_abraco: "text-teal",
  bloqueado_horario: "text-rust",
  bloqueado_rate_limit: "text-rust",
  bloqueado_conteudo: "text-rust",
  bloqueado_plano: "text-rust",
  guardado: "text-fg/55",
};

export default function OnboardingPage() {
  const [qrCode, setQrCode] = useState<string | null>(null);
  const [conectado, setConectado] = useState(false);
  const [carregando, setCarregando] = useState(false);
  const [verificandoStatus, setVerificandoStatus] = useState(true);
  const [erro, setErro] = useState("");
  const [desconectando, setDesconectando] = useState(false);
  const [confirmandoDesconexao, setConfirmandoDesconexao] = useState(false);

  const [conversas, setConversas] = useState<Conversa[]>([]);
  const [carregandoConversas, setCarregandoConversas] = useState(true);
  const [paginaConversas, setPaginaConversas] = useState(1);
  const [totalPaginasConversas, setTotalPaginasConversas] = useState(1);

  const [telefoneSelecionado, setTelefoneSelecionado] = useState<string | null>(null);
  const [mensagens, setMensagens] = useState<Interacao[]>([]);
  const [carregandoMensagens, setCarregandoMensagens] = useState(false);
  const [paginaMensagens, setPaginaMensagens] = useState(1);
  const [totalPaginasMensagens, setTotalPaginasMensagens] = useState(1);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function pararPoll() {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  async function verificarStatus() {
    try {
      const status = await apiFetch<StatusResponse>("/onboarding/status");
      const ok = status.data?.loggedIn ?? false;
      if (ok) {
        setConectado(true);
        setQrCode(null);
        pararPoll();
      } else {
        setConectado(false);
      }
    } catch {
      // ignora falhas de poll isoladas, tenta de novo no proximo tick
    } finally {
      setVerificandoStatus(false);
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
    verificarStatus();
    carregarConversas(1);
    return pararPoll;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function conectarWhatsapp() {
    setCarregando(true);
    setErro("");
    try {
      await apiFetch("/onboarding/wuzapi-user", { method: "POST" });
      await apiFetch("/onboarding/connect", { method: "POST" });

      await new Promise((resolve) => setTimeout(resolve, 1500));
      const qr = await apiFetch<QrResponse>("/onboarding/qrcode");
      const imagem = qr.data?.QRCode;
      if (imagem) {
        setQrCode(imagem);
      }

      pararPoll();
      pollRef.current = setInterval(verificarStatus, 3000);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao conectar com o WhatsApp");
    } finally {
      setCarregando(false);
    }
  }

  async function desconectarWhatsapp() {
    setDesconectando(true);
    setErro("");
    try {
      await apiFetch("/onboarding/logout", { method: "POST" });
      setConectado(false);
      setQrCode(null);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao desconectar o WhatsApp");
    } finally {
      setDesconectando(false);
      setConfirmandoDesconexao(false);
    }
  }

  return (
    <AppShell title="Conectar WhatsApp">
      <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6 max-w-lg">
        <p className="text-sm text-fg/55 mb-4">
          Sua rádio atende os ouvintes por um único número de WhatsApp, compartilhado por todos os
          radialistas — cada um entra no ar no horário do seu próprio programa.
        </p>
        {verificandoStatus ? (
          <p className="flex items-center gap-2 text-sm text-fg/55">
            <OndaSpin size={16} /> Carregando...
          </p>
        ) : conectado ? (
          <div>
            <div className="flex items-start gap-3">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-teal/10 text-teal border border-teal/25 px-2.5 py-0.5 text-xs font-medium">
                <OndaLed color="teal" pulse={false} /> Conectado
              </span>
              <p className="text-sm text-fg/65">O WhatsApp da sua rádio já está atendendo os ouvintes.</p>
            </div>
            <button
              type="button"
              onClick={() => setConfirmandoDesconexao(true)}
              className="mt-4 text-xs font-medium text-rust hover:text-rust/80"
            >
              Desconectar WhatsApp
            </button>
            {erro && <p className="text-sm text-rust mt-3">{erro}</p>}
          </div>
        ) : (
          <>
            <p className="text-sm text-fg/65 mb-4">
              Clique abaixo para gerar o código de pareamento e escaneie com o WhatsApp do número que vai
              atender os ouvintes.
            </p>
            <button
              onClick={conectarWhatsapp}
              disabled={carregando}
              className="rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-ink hover:bg-brand-600 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {carregando ? "Gerando..." : "Conectar WhatsApp"}
            </button>
            {erro && <p className="text-sm text-rust mt-3">{erro}</p>}
            {qrCode && (
              <div className="flex justify-center mt-5">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={qrCode}
                  alt="QR Code do WhatsApp"
                  className="max-w-64 rounded-lg bg-paper p-2 border border-border-strong"
                />
              </div>
            )}
          </>
        )}
      </div>

      <div className="mt-6 max-w-4xl">
        <h2 className="text-sm font-semibold text-fg mb-1">Mensagens recebidas</h2>
        <p className="text-xs text-fg/55 mb-4">
          Conversas dos ouvintes, separadas por número, e o que o sistema fez com cada mensagem.
        </p>

        <div className="flex gap-4 h-130">
          {/* Lista de conversas, tipo lista de chats do WhatsApp */}
          <div className="w-72 shrink-0 bg-surface rounded-2xl border border-border-strong shadow-theme-xs flex flex-col overflow-hidden">
            <div className="flex-1 overflow-y-auto divide-y divide-border-strong">
              {carregandoConversas ? (
                <p className="flex items-center gap-2 text-sm text-fg/55 p-4">
                  <OndaSpin size={16} /> Carregando...
                </p>
              ) : conversas.length === 0 ? (
                <p className="text-sm text-fg/55 p-4">Nenhuma conversa ainda.</p>
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
                          <span className="text-[11px] text-fg/45 shrink-0">{formatarHora(conversa.ultima_em)}</span>
                        </div>
                        <p className="text-xs text-fg/55 truncate mt-0.5">{conversa.ultima_mensagem}</p>
                        <div className="flex items-center justify-between mt-1">
                          <span className="text-[11px] text-fg/45 truncate">
                            {conversa.nome ? `${conversa.telefone} · ` : ""}
                            {conversa.radialista_nome}
                          </span>
                          <span className="text-[11px] rounded-full bg-paper px-1.5 py-0.5 text-fg/55 shrink-0">
                            {conversa.total_mensagens}
                          </span>
                        </div>
                      </div>
                    </div>
                  </button>
                ))
              )}
            </div>
            <div className="flex items-center justify-between p-2.5 border-t border-border-strong text-xs text-fg/55">
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
              <p className="text-sm text-fg/55 m-auto">Selecione uma conversa para ver as mensagens.</p>
            ) : (
              <>
                <div className="p-3 border-b border-border-strong flex items-center gap-3">
                  <Avatar telefone={telefoneSelecionado} nome={nomeSelecionado} tamanho={40} />
                  <div>
                    <p className="text-sm font-medium text-fg">{nomeSelecionado || telefoneSelecionado}</p>
                    {nomeSelecionado && <p className="text-xs text-fg/55">{telefoneSelecionado}</p>}
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
                    <p className="flex items-center gap-2 text-sm text-fg/55 m-auto">
                      <OndaSpin size={16} /> Carregando...
                    </p>
                  ) : (
                    mensagens.map((mensagem) => {
                      const enviadaPelaRadio = mensagem.origem === "radio";
                      return (
                        <div
                          key={mensagem.id}
                          className={`max-w-[80%] ${enviadaPelaRadio ? "self-end" : "self-start"}`}
                        >
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
                            className={`flex items-center gap-2 mt-1 ${
                              enviadaPelaRadio ? "justify-end mr-1" : "ml-1"
                            }`}
                          >
                            <span className="text-[11px] text-fg/45">{formatarHora(mensagem.criado_em)}</span>
                            <span className="text-[11px] text-fg/30">·</span>
                            <span className="text-[11px] text-fg/45">
                              {enviadaPelaRadio ? `${mensagem.radialista_nome} (rádio)` : mensagem.radialista_nome}
                            </span>
                          </div>
                          {!enviadaPelaRadio && (
                            <p className={`text-[11px] mt-0.5 ml-1 ${STATUS_COR[mensagem.status] ?? "text-fg/55"}`}>
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

                <div className="flex items-center justify-center p-2 border-t border-border-strong text-xs text-fg/45">
                  página {paginaMensagens}/{totalPaginasMensagens}
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      <ConfirmDialog
        open={confirmandoDesconexao}
        title="Desconectar WhatsApp"
        mensagem="Isso desliga o número do WhatsApp da rádio. Os radialistas param de atender os ouvintes até você conectar de novo escaneando um novo QR Code."
        onConfirmar={desconectarWhatsapp}
        onCancelar={() => !desconectando && setConfirmandoDesconexao(false)}
      />
    </AppShell>
  );
}
