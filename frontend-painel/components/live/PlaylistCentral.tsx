"use client";

import { MutableRefObject } from "react";
import { ProgramSegment, EstagioAoVivo } from "../../lib/liveTypes";
import { Programa } from "../../lib/types";
import { formatarDuracao } from "../../lib/bibliotecaAudio";
import { LocufyLed, LocufySpin, LocufyWaveform } from "../LocufyLogo";
import { useElapsedRemaining } from "../../hooks/useElapsedRemaining";
import ProximosBlocosPanel from "./ProximosBlocosPanel";

function formatarHora(iso: string): string {
  return new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

type Props = {
  programaAtivo: boolean;
  musicaAtual: string | null;
  musicaFimSegundos: number | null;
  estagioAtual: EstagioAoVivo;
  gerandoFala: boolean;
  falasPrograma: ProgramSegment[];
  onProximaFala: () => void;
  musicPlayerRef: MutableRefObject<any>;
  audioFalaRef: MutableRefObject<HTMLAudioElement | null>;
  programa: Programa | null;
  totalFalas: number;
};

export default function PlaylistCentral({
  programaAtivo,
  musicaAtual,
  musicaFimSegundos,
  estagioAtual,
  gerandoFala,
  falasPrograma,
  onProximaFala,
  musicPlayerRef,
  audioFalaRef,
  programa,
  totalFalas,
}: Props) {
  const musica = useElapsedRemaining(
    {
      getCurrentTime: () => musicPlayerRef.current?.getCurrentTime?.(),
      getDuration: () => musicaFimSegundos ?? musicPlayerRef.current?.getDuration?.(),
    },
    estagioAtual === "musica"
  );
  const fala = useElapsedRemaining(
    {
      getCurrentTime: () => audioFalaRef.current?.currentTime,
      getDuration: () => audioFalaRef.current?.duration,
    },
    estagioAtual === "fala"
  );
  const transport = estagioAtual === "musica" ? musica : estagioAtual === "fala" ? fala : null;

  return (
    <>
      <section
        className={`rounded-2xl border shadow-theme-xs p-6 transition-colors ${
          programaAtivo ? "bg-surface border-rust/40 ring-1 ring-rust/15" : "bg-surface border-border-strong"
        }`}
      >
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0">
            {programaAtivo && <LocufyLed color="rust" />}
            <p className={`font-mono text-xs font-semibold uppercase tracking-wide truncate ${programaAtivo ? "text-rust-text" : "text-fg/65"}`}>
              {programaAtivo ? "Transmitindo" : "Pausado"}
            </p>
          </div>
          <button
            type="button"
            onClick={onProximaFala}
            disabled={gerandoFala}
            className="shrink-0 rounded-lg border border-border-strong px-4 py-2.5 text-sm font-medium text-fg hover:bg-paper/5 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {gerandoFala ? "Gerando..." : "Proxima fala"}
          </button>
        </div>

        <div className="mt-2">
          {musicaAtual ? (
            <h2 className="font-display text-lg font-bold text-fg flex items-center gap-2.5 min-w-0">
              <LocufyWaveform bars={6} />
              <span className="truncate">{musicaAtual}</span>
            </h2>
          ) : (
            <h2 className="font-display text-lg font-bold text-fg">Programa no ar</h2>
          )}
          <p className="text-sm text-fg/65 mt-1">
            O agente gera chamadas, comentarios, noticias e blocos musicais conforme a configuracao do programa.
          </p>
        </div>

        {transport && (transport.decorridoFmt || transport.restanteFmt) && (
          <div className="mt-4">
            <div className="h-1.5 rounded-full bg-bg overflow-hidden">
              <div
                className="h-full rounded-full bg-linear-to-r from-teal to-amber transition-[width]"
                style={{ width: `${transport.percentConcluido ?? 0}%` }}
              />
            </div>
            <div className="mt-1.5 flex justify-between font-mono text-xs text-fg/65">
              <span>
                Decorrido <b className="text-fg font-semibold">{transport.decorridoFmt ?? "--:--"}</b>
              </span>
              <span>
                Restante <b className="text-fg font-semibold">{transport.restanteFmt ?? "--:--"}</b>
              </span>
              <span>
                Termino previsto <b className="text-fg font-semibold">{transport.terminoPrevistoFmt ?? "--:--"}</b>
              </span>
            </div>
          </div>
        )}

        {programa && (
          <div className="mt-5 border-t border-border pt-4">
            <ProximosBlocosPanel programa={programa} totalFalas={totalFalas} variant="strip" />
          </div>
        )}
      </section>

      <section className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-display text-base font-bold text-fg">Historico de falas</h2>
          <span className="font-mono text-xs text-fg/65">{falasPrograma.length} nesta transmissao</span>
        </div>
        <div className="rounded-xl border border-border bg-bg p-4 min-h-32 max-h-96 overflow-y-auto">
          {falasPrograma.length === 0 ? (
            <p className="text-sm text-fg/65">
              {programaAtivo
                ? "Gerando a primeira fala..."
                : "Clique em comecar transmissao acima, ou aguarde o horario agendado comecar."}
            </p>
          ) : (
            <div className="space-y-3">
              {falasPrograma.map((fala, index) => (
                <article
                  key={fala.id}
                  className={
                    index === 0
                      ? "rounded-lg bg-surface border border-rust/30 p-3 text-fg shadow-theme-xs"
                      : "text-fg/65"
                  }
                >
                  <div className="flex flex-wrap items-center gap-2 mb-1">
                    <span className="rounded-full bg-teal/10 px-2 py-0.5 text-xs font-medium text-teal-text">
                      {fala.tipo.replace("_", " ")}
                    </span>
                    <span className="font-mono text-xs text-fg/65">{formatarHora(fala.criado_em)}</span>
                    {fala.duracao_segundos != null && (
                      <span
                        className="font-mono text-xs text-fg/65"
                        title="Duracao real do bloco (fala + musica), medida ao vivo"
                      >
                        · {formatarDuracao(fala.duracao_segundos)}
                      </span>
                    )}
                    {fala.origem === "local" && (
                      <span className="rounded-full bg-amber/10 px-2 py-0.5 text-xs font-medium text-amber-text">
                        fallback local
                      </span>
                    )}
                    {index === 0 && gerandoFala && (
                      <span className="flex items-center gap-1.5 text-xs text-fg/65 italic">
                        <LocufySpin size={12} /> gerando proxima...
                      </span>
                    )}
                  </div>
                  <p className={`text-sm leading-6 ${index === 0 ? "font-medium" : ""}`}>{fala.fala}</p>
                </article>
              ))}
            </div>
          )}
        </div>
      </section>
    </>
  );
}
