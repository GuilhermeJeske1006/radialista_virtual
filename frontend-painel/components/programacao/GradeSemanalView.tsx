"use client";

import { useRef } from "react";
import { DIAS_SEMANA_LABEL, Programa, Radialista } from "../../lib/types";
import { corPorIndice, MINUTOS_DIA, segmentosDoPrograma } from "../../lib/gradeSemanal";

const ALTURA_HORA_PX = 48;
const ALTURA_TOTAL_PX = 24 * ALTURA_HORA_PX;
const HORAS = Array.from({ length: 24 }, (_, i) => i);

export type ProgramaComRadialista = Programa & { radialista: Radialista };

function minutosParaHorario(minutos: number): string {
  const m = Math.max(0, Math.min(MINUTOS_DIA - 1, minutos));
  const h = Math.floor(m / 60);
  const min = m % 60;
  return `${String(h).padStart(2, "0")}:${String(min).padStart(2, "0")}:00`;
}

function formatarFaixa(p: Programa): string {
  return `${p.horario_inicio.slice(0, 5)}–${p.horario_fim.slice(0, 5)}`;
}

type Props = {
  programas: ProgramaComRadialista[];
  radialistasOrdenados: Radialista[];
  onClickPrograma: (programa: ProgramaComRadialista) => void;
  onClickSlotVazio: (diaSemana: number, horarioAproximado: string) => void;
};

export default function GradeSemanalView({
  programas,
  radialistasOrdenados,
  onClickPrograma,
  onClickSlotVazio,
}: Props) {
  const indicePorRadialista = Object.fromEntries(radialistasOrdenados.map((r, i) => [r.id, i]));

  return (
    <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs overflow-hidden">
      <div className="overflow-x-auto">
        <div className="min-w-[820px]">
          <div className="grid grid-cols-[56px_repeat(7,1fr)] border-b border-border-strong">
            <div />
            {DIAS_SEMANA_LABEL.map((label) => (
              <div
                key={label}
                className="px-2 py-2.5 text-center text-xs font-mono font-semibold uppercase tracking-wide text-fg/55 border-l border-border"
              >
                {label}
              </div>
            ))}
          </div>

          <div className="max-h-[calc(100vh-16rem)] overflow-y-auto">
            <div className="grid grid-cols-[56px_repeat(7,1fr)]">
              <div className="relative" style={{ height: ALTURA_TOTAL_PX }}>
                {HORAS.map((h) => (
                  <div
                    key={h}
                    className="absolute right-2 -translate-y-1/2 font-mono text-[10px] text-fg/35"
                    style={{ top: h * ALTURA_HORA_PX }}
                  >
                    {String(h).padStart(2, "0")}h
                  </div>
                ))}
              </div>

              {DIAS_SEMANA_LABEL.map((_, diaSemana) => (
                <DiaColuna
                  key={diaSemana}
                  diaSemana={diaSemana}
                  programas={programas}
                  indicePorRadialista={indicePorRadialista}
                  onClickPrograma={onClickPrograma}
                  onClickSlotVazio={onClickSlotVazio}
                />
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function DiaColuna({
  diaSemana,
  programas,
  indicePorRadialista,
  onClickPrograma,
  onClickSlotVazio,
}: {
  diaSemana: number;
  programas: ProgramaComRadialista[];
  indicePorRadialista: Record<number, number>;
  onClickPrograma: (programa: ProgramaComRadialista) => void;
  onClickSlotVazio: (diaSemana: number, horarioAproximado: string) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);

  function aoClicarFundo(e: React.MouseEvent<HTMLDivElement>) {
    if (e.target !== containerRef.current) return; // clique caiu num bloco, nao no fundo vazio
    const rect = containerRef.current!.getBoundingClientRect();
    const minutosClicados = ((e.clientY - rect.top) / ALTURA_TOTAL_PX) * MINUTOS_DIA;
    const minutosArredondados = Math.round(minutosClicados / 30) * 30;
    onClickSlotVazio(diaSemana, minutosParaHorario(minutosArredondados));
  }

  const blocos = programas.flatMap((p) =>
    segmentosDoPrograma(p)
      .filter((s) => s.diaSemana === diaSemana)
      .map((s, i) => ({ programa: p, segmento: s, key: `${p.id}-${diaSemana}-${i}` }))
  );

  return (
    <div
      ref={containerRef}
      onClick={aoClicarFundo}
      className="relative border-l border-border cursor-pointer hover:bg-paper/[0.03]"
      style={{ height: ALTURA_TOTAL_PX }}
    >
      {Array.from({ length: 24 }, (_, h) => (
        <div key={h} className="absolute inset-x-0 border-t border-border/60" style={{ top: h * ALTURA_HORA_PX }} />
      ))}

      {blocos.map(({ programa, segmento, key }) => {
        const cor = corPorIndice(indicePorRadialista[programa.radialista.id] ?? 0);
        const top = (segmento.inicioMin / MINUTOS_DIA) * ALTURA_TOTAL_PX;
        const altura = Math.max(16, ((segmento.fimMin - segmento.inicioMin) / MINUTOS_DIA) * ALTURA_TOTAL_PX);
        return (
          <button
            key={key}
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onClickPrograma(programa);
            }}
            title={`${programa.nome} · ${programa.radialista.nome_locutor} · ${formatarFaixa(programa)}`}
            className={`absolute left-0.5 right-0.5 rounded-md border px-1.5 py-0.5 text-left overflow-hidden ${cor.borda} ${cor.fundo} hover:brightness-110`}
            style={{ top, height: altura }}
          >
            <p className={`text-[11px] font-medium leading-tight truncate ${cor.texto} ${!programa.ativo ? "opacity-45" : ""}`}>
              {programa.nome}
            </p>
            <p className="text-[10px] leading-tight text-fg/50 truncate">
              {programa.radialista.nome_locutor} · {formatarFaixa(programa)}
              {programa.data_especifica ? " · avulso" : ""}
            </p>
          </button>
        );
      })}
    </div>
  );
}
