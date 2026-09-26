"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "./api";
import { useConfiguracaoInicial } from "./useConfiguracaoInicial";

export type NoArResponse = {
  no_ar: boolean;
  radialista_id: number | null;
  radialista_nome: string | null;
  programa_id: number | null;
  programa_nome: string | null;
};

const INTERVALO_MS = 30_000;

// Um polling só para o painel inteiro (cabeçalho + dashboard), mesmo padrão de cache de
// módulo de useConta.ts -- sem isso cada tela abria o próprio intervalo.
let ultimo: NoArResponse | null = null;
let intervalo: ReturnType<typeof setInterval> | null = null;
const assinantes = new Set<(estado: NoArResponse | null) => void>();

function buscar() {
  apiFetch<NoArResponse>("/live/no-ar")
    .then((estado) => {
      if (!estado || typeof estado.no_ar !== "boolean") return;
      ultimo = estado;
      assinantes.forEach((avisar) => avisar(estado));
    })
    .catch(() => {
      // falha isolada: mantém o último estado conhecido
    });
}

/** Programa no horário agora. "No ar de verdade" também exige o WhatsApp conectado: sem ele
 * nenhum ouvinte fala com o radialista (mesma regra do card do dashboard). */
export function useNoAr(): { estado: NoArResponse | null; noAr: boolean } {
  const [estado, setEstado] = useState<NoArResponse | null>(ultimo);
  const { whatsappConectado } = useConfiguracaoInicial();

  useEffect(() => {
    assinantes.add(setEstado);
    if (!intervalo) {
      buscar();
      intervalo = setInterval(buscar, INTERVALO_MS);
    }
    return () => {
      assinantes.delete(setEstado);
      if (assinantes.size === 0 && intervalo) {
        clearInterval(intervalo);
        intervalo = null;
      }
    };
  }, []);

  return { estado, noAr: Boolean(estado?.no_ar) && whatsappConectado };
}
