"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import ConfirmDialog from "./ConfirmDialog";
import { apiFetch, ApiError } from "../lib/api";
import { invalidarConfiguracaoInicial } from "../lib/useConfiguracaoInicial";
import { LocufyLed, LocufySpin } from "./LocufyLogo";

type QrResponse = { data?: { QRCode?: string } };
type StatusResponse = { data?: { loggedIn?: boolean; connected?: boolean } };

/** Conexão do número de WhatsApp da rádio (QR Code via WuzAPI). A seção completa mora em
 * Configuração; Conversas mostra só a faixa de status, com link para cá quando conectado. */
export default function WhatsAppConexao({ compacta = false }: { compacta?: boolean }) {
  const [qrCode, setQrCode] = useState<string | null>(null);
  const [conectado, setConectado] = useState(false);
  const [conectando, setConectando] = useState(false);
  const [verificando, setVerificando] = useState(true);
  const [erro, setErro] = useState("");
  const [desconectando, setDesconectando] = useState(false);
  const [confirmandoDesconexao, setConfirmandoDesconexao] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function pararPoll() {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  async function verificarConexao() {
    try {
      const status = await apiFetch<StatusResponse>("/onboarding/status");
      const ok = status?.data?.loggedIn ?? false;
      if (ok) {
        setConectado(true);
        setQrCode(null);
        pararPoll();
        invalidarConfiguracaoInicial();
      } else {
        setConectado(false);
      }
    } catch {
      // ignora falha de poll isolada, tenta de novo no proximo tick
    } finally {
      setVerificando(false);
    }
  }

  useEffect(() => {
    verificarConexao();
    return pararPoll;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function conectar() {
    setConectando(true);
    setErro("");
    try {
      await apiFetch("/onboarding/wuzapi-user", { method: "POST" });
      await apiFetch("/onboarding/connect", { method: "POST" });

      await new Promise((resolve) => setTimeout(resolve, 1500));
      const qr = await apiFetch<QrResponse>("/onboarding/qrcode");
      const imagem = qr.data?.QRCode;
      if (imagem) setQrCode(imagem);

      pararPoll();
      pollRef.current = setInterval(verificarConexao, 3000);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao conectar com o WhatsApp");
    } finally {
      setConectando(false);
    }
  }

  async function desconectar() {
    setDesconectando(true);
    setErro("");
    try {
      await apiFetch("/onboarding/logout", { method: "POST" });
      setConectado(false);
      setQrCode(null);
      invalidarConfiguracaoInicial();
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao desconectar o WhatsApp");
    } finally {
      setDesconectando(false);
      setConfirmandoDesconexao(false);
    }
  }

  const botaoConectar = (
    <button
      type="button"
      onClick={conectar}
      disabled={conectando}
      className="rounded-xl bg-brand-500 px-4 py-2 text-sm font-medium text-on-brand hover:bg-brand-600 disabled:opacity-60 disabled:cursor-not-allowed"
    >
      {conectando ? "Gerando QR Code…" : qrCode ? "Gerar outro QR Code" : "Conectar WhatsApp"}
    </button>
  );

  return (
    <div aria-live="polite">
      {verificando ? (
        <p className="flex items-center gap-2 text-sm text-fg/65">
          <LocufySpin size={16} /> Verificando conexão do WhatsApp…
        </p>
      ) : conectado ? (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-ciano/10 text-ciano border border-ciano/25 px-2.5 py-0.5 text-xs font-medium">
            <LocufyLed color="ciano" pulse={false} /> WhatsApp conectado
          </span>
          {compacta ? (
            <Link href="/configuracoes#whatsapp" className="text-xs font-medium text-acento-claro underline hover:text-acento-dim">
              Gerenciar conexão
            </Link>
          ) : (
            <button
              type="button"
              onClick={() => setConfirmandoDesconexao(true)}
              className="rounded-xl border border-laranja/40 px-3 py-1.5 text-xs font-medium text-laranja hover:bg-laranja/10"
            >
              Desconectar WhatsApp
            </button>
          )}
        </div>
      ) : (
        <div>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm text-fg/80">
              <span className="font-medium text-laranja">WhatsApp desconectado</span> — os ouvintes não estão sendo
              atendidos.
            </p>
            {botaoConectar}
          </div>
          {!compacta && !qrCode && (
            <ol className="mt-4 list-decimal space-y-1 pl-5 text-sm text-fg/80">
              <li>Clique em Conectar WhatsApp para gerar o QR Code.</li>
              <li>No celular da rádio, abra o WhatsApp → Aparelhos conectados → Conectar um aparelho.</li>
              <li>Aponte a câmera para o QR Code. A conexão é confirmada aqui sozinha.</li>
            </ol>
          )}
          {qrCode && (
            <div className="mt-4 flex flex-col items-center gap-2">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={qrCode}
                alt="QR Code para conectar o WhatsApp da rádio"
                width={256}
                height={256}
                className="max-w-64 rounded-xl bg-branco p-2 border border-border-strong"
              />
              <p className="text-xs text-fg/65">Aguardando leitura do QR Code…</p>
            </div>
          )}
        </div>
      )}
      {erro && <p role="alert" className="text-sm text-laranja mt-3">{erro}</p>}

      <ConfirmDialog
        open={confirmandoDesconexao}
        title="Desconectar WhatsApp"
        mensagem="Isso desliga o número do WhatsApp da rádio. Os radialistas param de atender os ouvintes até você conectar de novo escaneando um novo QR Code."
        onConfirmar={desconectar}
        onCancelar={() => !desconectando && setConfirmandoDesconexao(false)}
      />
    </div>
  );
}
