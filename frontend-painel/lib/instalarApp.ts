"use client";

import { useEffect, useState } from "react";

// App instalado (PWA) e' o jeito do cliente aceitar UMA vez que o painel toque som sozinho: o
// Chrome/Edge de desktop liberam autoplay com som pra PWA instalada, entao o ao vivo roda com o
// painel so' aberto -- sem ninguem clicar em "Ativar som" depois de reiniciar o computador ou
// recarregar a pagina (ver sondarAutoplayComSom em hooks/useLiveEngine.ts).

// O navegador dispara `beforeinstallprompt` uma vez, cedo no carregamento -- em geral antes do
// React montar a tela. Esse script (injetado em app/layout.tsx) guarda o evento em
// window.__locufyInstalar e avisa quem chegar depois.
export const CAPTURA_INSTALACAO_SCRIPT = `window.addEventListener("beforeinstallprompt",function(e){e.preventDefault();window.__locufyInstalar=e;window.dispatchEvent(new Event("locufy-instalar-disponivel"));});window.addEventListener("appinstalled",function(){window.__locufyInstalar=null;try{localStorage.setItem("locufy-app-configurado","1");}catch(x){}});`;

type EventoInstalacao = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

declare global {
  interface Window {
    __locufyInstalar?: EventoInstalacao | null;
  }
}

export type Navegador = "chrome" | "edge" | "firefox" | "safari" | "outro";

export function detectarNavegador(userAgent: string): Navegador {
  if (/Edg\//.test(userAgent)) return "edge";
  if (/Firefox\//.test(userAgent)) return "firefox";
  if (/Chrome\/|CriOS\//.test(userAgent)) return "chrome";
  if (/Safari\//.test(userAgent)) return "safari";
  return "outro";
}

export function rodandoComoApp(): boolean {
  if (typeof window === "undefined") return false;
  const modo = (m: string) => typeof window.matchMedia === "function" && window.matchMedia(`(display-mode: ${m})`).matches;
  return modo("standalone") || modo("window-controls-overlay") || modo("minimal-ui")
    || (navigator as Navigator & { standalone?: boolean }).standalone === true;
}

// Instalacao e permissao de som sao do APARELHO, nao da conta: o computador da radio pode estar
// pronto e o notebook do dono nao. Por isso o passo "app" do onboarding (lib/tour.ts) fica em
// localStorage, e nao no backend.
const CHAVE_APP_CONFIGURADO = "locufy-app-configurado";
const EVENTO_APP_CONFIGURADO = "locufy-app-configurado";

export function appConfigurado(): boolean {
  if (rodandoComoApp()) return true;
  try {
    return localStorage.getItem(CHAVE_APP_CONFIGURADO) === "1";
  } catch {
    return false;
  }
}

/** Instalou, liberou o som (Firefox) ou escolheu pular -- em todos o passo sai do caminho. */
export function marcarAppConfigurado(): void {
  try {
    localStorage.setItem(CHAVE_APP_CONFIGURADO, "1");
  } catch {
    // sem storage -- vale so' nesta visita (o evento abaixo ainda atualiza a tela)
  }
  window.dispatchEvent(new Event(EVENTO_APP_CONFIGURADO));
}

export function useAppConfigurado(): boolean {
  const [pronto, setPronto] = useState(false);
  useEffect(() => {
    const atualizar = () => setPronto(appConfigurado());
    atualizar();
    window.addEventListener(EVENTO_APP_CONFIGURADO, atualizar);
    window.addEventListener("appinstalled", atualizar);
    return () => {
      window.removeEventListener(EVENTO_APP_CONFIGURADO, atualizar);
      window.removeEventListener("appinstalled", atualizar);
    };
  }, []);
  return pronto;
}

export function useInstalarApp() {
  const [comoApp, setComoApp] = useState(false);
  const [podeInstalar, setPodeInstalar] = useState(false);
  const [instalado, setInstalado] = useState(false);
  const [navegador, setNavegador] = useState<Navegador>("outro");

  useEffect(() => {
    setComoApp(rodandoComoApp());
    setNavegador(detectarNavegador(navigator.userAgent));
    setPodeInstalar(Boolean(window.__locufyInstalar));
    const aoDisponivel = () => setPodeInstalar(Boolean(window.__locufyInstalar));
    const aoInstalar = () => { setInstalado(true); setPodeInstalar(false); };
    window.addEventListener("locufy-instalar-disponivel", aoDisponivel);
    window.addEventListener("appinstalled", aoInstalar);
    return () => {
      window.removeEventListener("locufy-instalar-disponivel", aoDisponivel);
      window.removeEventListener("appinstalled", aoInstalar);
    };
  }, []);

  async function instalar(): Promise<boolean> {
    const evento = window.__locufyInstalar;
    if (!evento) return false;
    // o evento so' pode ser usado uma vez -- recusado, o navegador dispara outro mais tarde
    window.__locufyInstalar = null;
    setPodeInstalar(false);
    await evento.prompt();
    const { outcome } = await evento.userChoice;
    if (outcome === "accepted") {
      setInstalado(true);
      marcarAppConfigurado();
    }
    return outcome === "accepted";
  }

  return { comoApp, podeInstalar, instalado, navegador, instalar };
}
