"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "./api";
import { Programa, Radialista, RadioConta } from "./types";

export type ConfiguracaoInicialEstado = {
  radialistaPronto: boolean;
  programaAtivo: boolean;
  whatsappConectado: boolean;
  completa: boolean;
};

const ESTADO_VAZIO: ConfiguracaoInicialEstado = {
  radialistaPronto: false,
  programaAtivo: false,
  whatsappConectado: false,
  completa: false,
};

// Cache de modulo, mesmo padrao de useConta.ts -- Sidebar e AppShell montam juntos e os
// dois usam esse hook, sem isso duplicaria o fetch a cada navegacao.
let cache: ConfiguracaoInicialEstado | null = null;
let buscaEmVoo: Promise<ConfiguracaoInicialEstado> | null = null;
const assinantes = new Set<(estado: ConfiguracaoInicialEstado) => void>();

function buscar(): Promise<ConfiguracaoInicialEstado> {
  if (!buscaEmVoo) {
    buscaEmVoo = Promise.all([
      apiFetch<RadioConta>("/config/radio"),
      apiFetch<Radialista[]>("/config/radialistas"),
    ])
      .then(async ([radio, radialistas]) => {
        const radialistaPronto = radialistas.some((r) => r.ativo && r.voz_id);
        const listasDeProgramas = await Promise.all(
          radialistas.map((r) =>
            apiFetch<Programa[]>(`/config/radialistas/${r.id}/programas`).catch(() => [] as Programa[])
          )
        );
        const programaAtivo = listasDeProgramas.flat().some((p) => p.ativo);
        const whatsappConectado = Boolean(radio.wuzapi_token);
        const estado: ConfiguracaoInicialEstado = {
          radialistaPronto,
          programaAtivo,
          whatsappConectado,
          completa: whatsappConectado && radialistaPronto && programaAtivo,
        };
        cache = estado;
        assinantes.forEach((avisar) => avisar(estado));
        return estado;
      })
      .catch(() => {
        buscaEmVoo = null;
        return ESTADO_VAZIO;
      });
  }
  return buscaEmVoo;
}

/** Forca um novo fetch e avisa quem ja' esta' montado (OnboardingTour, Sidebar, AppShell
 * sobrevivem a navegacao entre paginas) -- chamar depois de criar/editar radialista,
 * programa ou conectar o WhatsApp, senao o card do tour e o checklist do dashboard ficam
 * presos no estado antigo ate um reload completo da pagina. */
export function invalidarConfiguracaoInicial(): void {
  cache = null;
  buscaEmVoo = null;
  buscar().catch(() => {});
}

/** Estado granular dos 3 passos da configuração inicial (radialista, programa, WhatsApp) --
 * usado pelo checklist do dashboard e pelo tour guiado de onboarding. */
export function useConfiguracaoInicial(): ConfiguracaoInicialEstado {
  const [estado, setEstado] = useState(cache ?? ESTADO_VAZIO);

  useEffect(() => {
    assinantes.add(setEstado);
    if (cache === null) {
      buscar().catch(() => {});
    }
    return () => {
      assinantes.delete(setEstado);
    };
  }, []);

  return estado;
}

/** Enquanto a rádio ainda não tem radialista+programa prontos e WhatsApp conectado, o menu
 * mostra "Configuração inicial" numerada (1/2/3) pra guiar o primeiro uso. Depois disso vira
 * ruído (a rádio já roda há meses) -- some a numeração assim que completo. */
export function useConfiguracaoInicialCompleta(): boolean {
  return useConfiguracaoInicial().completa;
}
