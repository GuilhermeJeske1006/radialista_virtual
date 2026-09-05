"use client";

import { useState } from "react";

export type PontoSerie = { data: string; total: number };

export function formatarDataCurta(iso: string): string {
  const [, mes, dia] = iso.split("-");
  return `${dia}/${mes}`;
}

export function formatarDataLonga(iso: string): string {
  return new Date(`${iso}T12:00:00`).toLocaleDateString("pt-BR", { day: "2-digit", month: "long" });
}

export function GraficoBarras({
  serie,
  corSerie = "#33c2a8",
  corSerieHover = "#279d88",
  rotuloSingular = "mensagem",
  rotuloPlural = "mensagens",
  ariaLabel = "Mensagens recebidas por dia nos últimos 30 dias",
}: {
  serie: PontoSerie[];
  corSerie?: string;
  corSerieHover?: string;
  rotuloSingular?: string;
  rotuloPlural?: string;
  ariaLabel?: string;
}) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  const maximo = Math.max(1, ...serie.map((ponto) => ponto.total));
  const altura = 140;
  const larguraBarra = 8;
  const espaco = 4;
  const largura = serie.length * (larguraBarra + espaco);

  const indicesRotulados = new Set([0, Math.floor((serie.length - 1) / 2), serie.length - 1]);
  const hover = hoverIndex !== null ? serie[hoverIndex] : null;

  return (
    <div className="relative">
      {hover && (
        <div className="absolute -top-1 left-1/2 -translate-x-1/2 -translate-y-full rounded-lg bg-ink px-2.5 py-1.5 text-xs text-paper shadow-theme-sm whitespace-nowrap pointer-events-none z-10">
          <span className="font-semibold">{hover.total.toLocaleString("pt-BR")}</span>{" "}
          {hover.total === 1 ? rotuloSingular : rotuloPlural} · {formatarDataLonga(hover.data)}
        </div>
      )}
      <svg
        viewBox={`0 0 ${largura} ${altura + 20}`}
        width="100%"
        height={altura + 20}
        preserveAspectRatio="none"
        role="img"
        aria-label={ariaLabel}
      >
        {/* linha de base -- unica gridline, recessiva */}
        <line
          x1={0}
          y1={altura}
          x2={largura}
          y2={altura}
          stroke="var(--color-border-strong)"
          strokeWidth={1}
        />
        {serie.map((ponto, indice) => {
          const alturaBarra = Math.max(2, (ponto.total / maximo) * (altura - 8));
          const x = indice * (larguraBarra + espaco);
          const y = altura - alturaBarra;
          const emHover = hoverIndex === indice;
          return (
            <g key={ponto.data}>
              <rect
                x={x}
                y={y}
                width={larguraBarra}
                height={alturaBarra}
                rx={2}
                fill={emHover ? corSerieHover : corSerie}
              >
                <title>
                  {formatarDataLonga(ponto.data)}: {ponto.total} {ponto.total === 1 ? rotuloSingular : rotuloPlural}
                </title>
              </rect>
              {/* hit target maior que a barra, cobre o espaco entre barras tambem */}
              <rect
                x={x - espaco / 2}
                y={0}
                width={larguraBarra + espaco}
                height={altura}
                fill="transparent"
                onMouseEnter={() => setHoverIndex(indice)}
                onMouseLeave={() => setHoverIndex(null)}
              />
              {indicesRotulados.has(indice) && (
                <text
                  x={x + larguraBarra / 2}
                  y={altura + 14}
                  textAnchor="middle"
                  fontSize={9}
                  fill="var(--color-fg)"
                  opacity={0.45}
                >
                  {formatarDataCurta(ponto.data)}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
