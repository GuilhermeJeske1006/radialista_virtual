"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import AppShell from "../../components/AppShell";
import RadialistaSwitcher from "../../components/RadialistaSwitcher";
import { apiFetch, ApiError } from "../../lib/api";
import { getRadialistaAtualId, setRadialistaAtualId } from "../../lib/radialistas";
import { Radialista } from "../../lib/types";
import { OndaLed, OndaSpin } from "../../components/OndaLogo";

type QrResponse = { data?: { QRCode?: string } };
type StatusResponse = { data?: { loggedIn?: boolean; connected?: boolean } };

export default function OnboardingPage() {
  return (
    <Suspense
      fallback={
        <AppShell title="Conectar WhatsApp">
          <p className="flex items-center gap-2 text-sm text-fg/55">
            <OndaSpin size={16} /> Carregando...
          </p>
        </AppShell>
      }
    >
      <OnboardingContent />
    </Suspense>
  );
}

function OnboardingContent() {
  const searchParams = useSearchParams();
  const [radialistas, setRadialistas] = useState<Radialista[]>([]);
  const [radialistaId, setRadialistaId] = useState<number | null>(null);
  const [qrCode, setQrCode] = useState<string | null>(null);
  const [conectado, setConectado] = useState(false);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState("");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const radialistaIdRef = useRef<number | null>(null);

  function pararPoll() {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  async function verificarStatus(id: number) {
    try {
      const status = await apiFetch<StatusResponse>(`/onboarding/${id}/status`);
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
    }
  }

  function selecionarRadialista(id: number) {
    pararPoll();
    radialistaIdRef.current = id;
    setRadialistaId(id);
    setRadialistaAtualId(id);
    setQrCode(null);
    setConectado(false);
    verificarStatus(id);
  }

  useEffect(() => {
    apiFetch<Radialista[]>("/config/radialistas")
      .then((lista) => {
        setRadialistas(lista);
        const daUrl = Number(searchParams.get("radialista"));
        const preferido = daUrl || getRadialistaAtualId();
        const alvo = lista.find((r) => r.id === preferido) ?? lista[0];
        if (alvo) selecionarRadialista(alvo.id);
      })
      .catch((err) => setErro(err instanceof ApiError ? err.message : "Erro ao carregar radialistas"));
    return pararPoll;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function conectarWhatsapp() {
    if (!radialistaId) return;
    setCarregando(true);
    setErro("");
    try {
      await apiFetch(`/onboarding/${radialistaId}/wuzapi-user`, { method: "POST" });
      await apiFetch(`/onboarding/${radialistaId}/connect`, { method: "POST" });

      await new Promise((resolve) => setTimeout(resolve, 1500));
      const qr = await apiFetch<QrResponse>(`/onboarding/${radialistaId}/qrcode`);
      const imagem = qr.data?.QRCode;
      if (imagem) {
        setQrCode(imagem);
      }

      pararPoll();
      pollRef.current = setInterval(() => verificarStatus(radialistaId), 3000);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao conectar com o WhatsApp");
    } finally {
      setCarregando(false);
    }
  }

  return (
    <AppShell title="Conectar WhatsApp">
      <div className="mb-4">
        <RadialistaSwitcher radialistas={radialistas} selecionadoId={radialistaId} onSelect={selecionarRadialista} />
      </div>
      <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6 max-w-lg">
        {!radialistaId ? (
          <p className="text-sm text-fg/55">Crie um radialista primeiro para conectar um número de WhatsApp.</p>
        ) : conectado ? (
          <div className="flex items-start gap-3">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-teal/10 text-teal border border-teal/25 px-2.5 py-0.5 text-xs font-medium">
              <OndaLed color="teal" pulse={false} /> Conectado
            </span>
            <p className="text-sm text-fg/65">Este radialista já está atendendo os ouvintes.</p>
          </div>
        ) : (
          <>
            <p className="text-sm text-fg/65 mb-4">
              Clique abaixo para gerar o código de pareamento e escaneie com o WhatsApp do número que vai
              atender os ouvintes deste radialista.
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
    </AppShell>
  );
}
