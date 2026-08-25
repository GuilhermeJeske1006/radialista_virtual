"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api";
import { Patrocinador, Programa, rotuloBloco } from "../../lib/types";
import { BibliotecaAudioItem } from "../../lib/bibliotecaAudio";

// Porta em JS a logica de _tipo_proximo_bloco (backend/app/live/router.py) -- so os TIPOS,
// sem gerar conteudo real (LLM/TTS) antecipadamente. Fiel a parte deterministica do motor;
// duas simplificacoes documentadas abaixo (ambas ja avisadas na legenda da UI):
//
// 1. Nao simula a chance de 15% da IA emendar um "comentario" extra fora da sequencia
//    (programa.ia_pode_adicionar_blocos) -- so mostra um aviso quando essa flag esta ligada.
// 2. Bloco customizado sem prefixo reconhecido (ex.: "chamame e xote") e' classificado no
//    backend via LLM+cache (_classificar_bloco_customizado) pra decidir se e' um "encerramento"
//    disfarcado; aqui tratamos como o proprio texto (sem chamada de LLM), entao um "encerramento"
//    digitado sem esse prefixo pode nao ser filtrado do loop como seria no motor real.
const ROTEIRO_PADRAO = ["musica", "abertura", "comentario", "noticia", "chamada_ouvinte"];

const TIPOS_COM_COMPORTAMENTO = ["musica", "noticia", "chamada_ouvinte", "abertura", "comentario", "encerramento"];

const PATROCINADOR_RE = /^patrocinador:(\d+)$/;
const VINHETA_RE = /^vinheta:(\d+)$/;

function semAcento(texto: string): string {
  return texto.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

function categoriaBlocoAproximada(tipo: string): string {
  if (PATROCINADOR_RE.test(tipo) || VINHETA_RE.test(tipo)) return tipo;
  const normalizado = semAcento(tipo.trim().toLowerCase());
  for (const base of TIPOS_COM_COMPORTAMENTO) {
    if (normalizado === base || normalizado.startsWith(`${base} `)) return base;
  }
  return normalizado;
}

function tipoDoBloco(estruturaBlocos: string[], totalFalas: number): string {
  const roteiroCustom = estruturaBlocos
    .map((t) => t.trim())
    .filter((t) => t && categoriaBlocoAproximada(t) !== "encerramento");

  if (roteiroCustom.length === 0) {
    if (totalFalas === 0) return "abertura";
    return ROTEIRO_PADRAO[(totalFalas - 1) % ROTEIRO_PADRAO.length];
  }
  return roteiroCustom[totalFalas % roteiroCustom.length];
}

function proximosTipos(estruturaBlocos: string[], totalFalasAtual: number, quantidade: number): string[] {
  return Array.from({ length: quantidade }, (_, i) => tipoDoBloco(estruturaBlocos, totalFalasAtual + i));
}

type Props = {
  programa: Programa | null;
  totalFalas: number;
  variant?: "card" | "strip";
};

const QUANTIDADE_PREVIEW = 5;

export default function ProximosBlocosPanel({ programa, totalFalas, variant = "card" }: Props) {
  const [patrocinadores, setPatrocinadores] = useState<Patrocinador[]>([]);
  const [vinhetas, setVinhetas] = useState<BibliotecaAudioItem[]>([]);

  useEffect(() => {
    apiFetch<Patrocinador[]>("/patrocinadores")
      .then(setPatrocinadores)
      .catch(() => setPatrocinadores([]));
    apiFetch<BibliotecaAudioItem[]>("/biblioteca-audio")
      .then(setVinhetas)
      .catch(() => setVinhetas([]));
  }, []);

  if (!programa) return null;

  const nomesPatrocinadores = Object.fromEntries(patrocinadores.map((p) => [p.id, p.nome]));
  const nomesVinhetas = Object.fromEntries(vinhetas.map((v) => [v.id, v.nome]));
  const tipos = proximosTipos(programa.estrutura_blocos, totalFalas, QUANTIDADE_PREVIEW);

  const lista = (
    <ol className={variant === "strip" ? "flex gap-2 overflow-x-auto pb-1" : "mt-4 space-y-2"}>
      {tipos.map((tipo, i) =>
        variant === "strip" ? (
          <li
            key={i}
            className={`shrink-0 whitespace-nowrap rounded-lg border px-3 py-1.5 text-xs ${
              i === 0
                ? "bg-amber/10 border-amber/30 text-amber font-semibold"
                : "bg-bg border-border-strong text-fg/60"
            }`}
          >
            {i === 0 && "▶ "}
            {rotuloBloco(tipo, nomesPatrocinadores, nomesVinhetas)}
          </li>
        ) : (
          <li
            key={i}
            className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm ${
              i === 0 ? "bg-amber/10 border border-amber/25 text-amber font-medium" : "text-fg/65"
            }`}
          >
            <span className="font-mono text-xs w-5 shrink-0">{i === 0 ? "▶" : i + 1}</span>
            <span className="min-w-0 truncate">{rotuloBloco(tipo, nomesPatrocinadores, nomesVinhetas)}</span>
            {i === 0 && <span className="ml-auto text-xs font-mono shrink-0">a seguir</span>}
          </li>
        )
      )}
    </ol>
  );

  if (variant === "strip") {
    return (
      <div>
        <p className="text-xs font-mono font-semibold uppercase tracking-wide text-fg/40 mb-2">A seguir na grade</p>
        <div className="relative">
          {lista}
          <div className="pointer-events-none absolute right-0 top-0 bottom-1.5 w-10 bg-linear-to-l from-surface to-transparent" />
        </div>
        {programa.ia_pode_adicionar_blocos && (
          <p className="text-xs text-fg/40 mt-2">A IA pode ocasionalmente inserir um comentario extra fora dessa sequencia.</p>
        )}
      </div>
    );
  }

  return (
    <section className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6">
      <h2 className="font-display text-base font-bold text-fg">Proximos blocos</h2>
      <p className="text-sm text-fg/55 mt-1">
        Sequencia planejada pra grade deste programa. So os tipos -- o conteudo real (texto, musica) so e' gerado
        na hora de ir ao ar.
      </p>
      {lista}
      {programa.ia_pode_adicionar_blocos && (
        <p className="text-xs text-fg/40 mt-3">
          A IA pode ocasionalmente inserir um comentario extra fora dessa sequencia.
        </p>
      )}
    </section>
  );
}
