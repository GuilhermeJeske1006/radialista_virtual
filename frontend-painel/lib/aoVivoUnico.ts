"use client";

import { useEffect } from "react";
import { rodandoComoApp } from "./instalarApp";

// Um ao vivo por computador. Depois de instalar, o Chrome/Edge abrem a janela do app sozinhos
// (start_url = /live) e ela entra no ar pelo horario -- mas a aba do navegador onde o cliente
// clicou em "Instalar" continua aberta. Se as duas transmitissem, sairia audio dobrado e o
// dobro de LLM/TTS. Regra: o app instalado tem prioridade e a aba do navegador cede.
const CANAL = "locufy-ao-vivo";
const APP_ASSUMIU = "app-assumiu";
const QUEM_E_APP = "quem-e-app";

/**
 * Na janela do app: avisa as abas abertas que o ao vivo e' dele (e responde quem perguntar).
 * Na aba do navegador: chama `ceder` quando o app avisar, ou quando o app acabou de ser
 * instalado a partir desta aba (o app abre sozinho logo em seguida).
 */
export function useAoVivoUnico(ceder: () => void) {
  useEffect(() => {
    if (typeof BroadcastChannel === "undefined") return;
    const canal = new BroadcastChannel(CANAL);
    const souApp = rodandoComoApp();

    if (souApp) {
      canal.onmessage = (evento) => {
        if (evento.data === QUEM_E_APP) canal.postMessage(APP_ASSUMIU);
      };
      canal.postMessage(APP_ASSUMIU);
      return () => canal.close();
    }

    canal.onmessage = (evento) => {
      if (evento.data === APP_ASSUMIU) ceder();
    };
    // app ja' aberto antes desta aba: pergunta
    canal.postMessage(QUEM_E_APP);
    window.addEventListener("appinstalled", ceder);
    return () => {
      canal.close();
      window.removeEventListener("appinstalled", ceder);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}
