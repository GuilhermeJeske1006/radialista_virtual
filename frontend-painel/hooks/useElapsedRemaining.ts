"use client";

import { useEffect, useState } from "react";

const POLL_MS = 500;

function formatarMMSS(segundos: number): string {
  const total = Math.max(0, Math.round(segundos));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function formatarHoraFutura(segundosRestantes: number): string {
  const termino = new Date(Date.now() + segundosRestantes * 1000);
  return termino.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

type Adaptador = {
  getCurrentTime: () => number | null | undefined;
  getDuration: () => number | null | undefined;
};

type Resultado = {
  decorridoFmt: string | null;
  restanteFmt: string | null;
  terminoPrevistoFmt: string | null;
  percentConcluido: number | null;
};

// Decorrido/restante/termino calculados no CLIENTE a partir do audio real tocando --
// o backend nao retorna duracao de bloco nenhuma (ver LiveProgramResponse). Cada consumidor
// passa um adaptador fino: musica le musicPlayerRef (YT IFrame API), fala le audioFalaRef
// (HTMLAudioElement nativo).
export function useElapsedRemaining(adaptador: Adaptador, ativo: boolean): Resultado {
  const [resultado, setResultado] = useState<Resultado>({
    decorridoFmt: null,
    restanteFmt: null,
    terminoPrevistoFmt: null,
    percentConcluido: null,
  });

  useEffect(() => {
    if (!ativo) {
      setResultado({ decorridoFmt: null, restanteFmt: null, terminoPrevistoFmt: null, percentConcluido: null });
      return;
    }

    function atualizar() {
      const atual = adaptador.getCurrentTime();
      const duracao = adaptador.getDuration();
      if (typeof atual !== "number" || typeof duracao !== "number" || !Number.isFinite(duracao) || duracao <= 0) {
        return;
      }
      const restante = Math.max(0, duracao - atual);
      setResultado({
        decorridoFmt: formatarMMSS(atual),
        restanteFmt: formatarMMSS(restante),
        terminoPrevistoFmt: formatarHoraFutura(restante),
        percentConcluido: Math.min(100, Math.max(0, (atual / duracao) * 100)),
      });
    }

    atualizar();
    const intervalo = setInterval(atualizar, POLL_MS);
    return () => clearInterval(intervalo);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ativo]);

  return resultado;
}
