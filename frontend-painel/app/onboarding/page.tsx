"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import AppShell from "../../components/AppShell";
import ConfirmDialog from "../../components/ConfirmDialog";
import { apiFetch, ApiError } from "../../lib/api";
import { Programa, Radialista } from "../../lib/types";
import { LocufyLed, LocufySpin } from "../../components/LocufyLogo";

type QrResponse = { data?: { QRCode?: string } };
type StatusResponse = { data?: { loggedIn?: boolean; connected?: boolean } };

export default function OnboardingPage() {
  const [qrCode, setQrCode] = useState<string | null>(null);
  const [conectado, setConectado] = useState(false);
  const [carregando, setCarregando] = useState(false);
  const [verificandoStatus, setVerificandoStatus] = useState(true);
  const [erro, setErro] = useState("");
  const [desconectando, setDesconectando] = useState(false);
  const [confirmandoDesconexao, setConfirmandoDesconexao] = useState(false);
  const [semRadialistaPronto, setSemRadialistaPronto] = useState(false);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    apiFetch<Radialista[]>("/config/radialistas")
      .then(async (radialistas) => {
        const listas = await Promise.all(
          radialistas.map((r) =>
            apiFetch<Programa[]>(`/config/radialistas/${r.id}/programas`).catch(() => [] as Programa[])
          )
        );
        const temProgramaAtivo = listas.flat().some((p) => p.ativo);
        setSemRadialistaPronto(radialistas.length === 0 || !temProgramaAtivo);
      })
      .catch(() => {
        // ignora falha isolada -- o aviso so' ajuda, nao bloqueia a conexao
      });
  }, []);

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

  useEffect(() => {
    verificarStatus();
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
      {semRadialistaPronto && (
        <div className="max-w-lg mb-4 rounded-xl border border-amber/30 bg-amber/10 px-4 py-3">
          <p className="text-sm text-fg/80">
            Conecte o WhatsApp depois de configurar seu primeiro{" "}
            <Link href="/radialista" className="text-amber-text font-medium hover:text-amber-dim">
              radialista
            </Link>{" "}
            e programa, pra já sair respondendo os ouvintes.
          </p>
        </div>
      )}
      <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6 max-w-lg">
        <p className="text-sm text-fg/65 mb-4">
          Sua rádio atende os ouvintes por um único número de WhatsApp, compartilhado por todos os
          radialistas — cada um entra no ar no horário do seu próprio programa.
        </p>
        {verificandoStatus ? (
          <p className="flex items-center gap-2 text-sm text-fg/65">
            <LocufySpin size={16} /> Carregando...
          </p>
        ) : conectado ? (
          <div>
            <div className="flex items-start gap-3">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-teal/10 text-teal-text border border-teal/25 px-2.5 py-0.5 text-xs font-medium">
                <LocufyLed color="teal" pulse={false} /> Conectado
              </span>
              <p className="text-sm text-fg/65">O WhatsApp da sua rádio já está atendendo os ouvintes.</p>
            </div>
            <button
              type="button"
              onClick={() => setConfirmandoDesconexao(true)}
              className="mt-4 text-xs font-medium text-rust-text hover:text-rust/80"
            >
              Desconectar WhatsApp
            </button>
            {erro && <p className="text-sm text-rust-text mt-3">{erro}</p>}
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
            {erro && <p className="text-sm text-rust-text mt-3">{erro}</p>}
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
