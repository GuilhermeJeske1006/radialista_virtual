// Horário previsto de cada bloco no ao vivo (F1). Puro: o hook só chama.
//
// A fila de preparo gera cada bloco ~2 blocos antes de ele tocar. O relógio do backend precisa saber
// QUANDO o bloco vai ao ar, então o painel encadeia: início bruto do próximo = início bruto deste +
// pausa + duração prevista. O valor enviado soma o desvio medido no último bloco que começou a tocar
// (atraso de rede, áudio mais longo), o que limita o erro a cerca de dois blocos.
import { MusicaBloco, ProgramSegment } from "./liveTypes";

// Estimativa antiga do painel (lib/duracaoBloco.ts), só quando o backend não mandou duracao_prevista_s.
const PALAVRAS_POR_SEGUNDO = 2.5;
const PAUSA_MAX_MS = 5000;

type SegmentoComDuracao = Pick<ProgramSegment, "fala" | "falas" | "musicas" | "video_id" | "inicio_segundos" | "fim_segundos"> & {
  duracao_prevista_s?: number | null;
  duracao_segundos?: number | null;
  pausa_antes_ms?: number | null;
};

function duracaoMusica(musica: Pick<MusicaBloco, "inicio_segundos" | "fim_segundos" | "duracao_segundos">): number {
  const fim = musica.fim_segundos ?? musica.duracao_segundos ?? 0;
  return Math.max(0, fim - (musica.inicio_segundos ?? 0));
}

export function estimarDuracaoSegmento(segmento: SegmentoComDuracao): number {
  if (typeof segmento.duracao_prevista_s === "number") return segmento.duracao_prevista_s;
  const texto = segmento.falas?.length ? segmento.falas.map((f) => f.texto).join(" ") : segmento.fala ?? "";
  const palavras = texto.replace(/\[[^\]]*\]/g, "").trim().split(/\s+/).filter(Boolean).length;
  const musicas = segmento.musicas?.length
    ? segmento.musicas
    : segmento.video_id
      ? [{ inicio_segundos: segmento.inicio_segundos, fim_segundos: segmento.fim_segundos, duracao_segundos: segmento.duracao_segundos }]
      : [];
  return palavras / PALAVRAS_POR_SEGUNDO + musicas.reduce((soma, m) => soma + duracaoMusica(m), 0);
}

function pausaMs(segmento: SegmentoComDuracao): number {
  return Math.max(0, Math.min(PAUSA_MAX_MS, segmento.pausa_antes_ms ?? 0));
}

// Início bruto do bloco seguinte ao `segmento`, que começa (bruto) em `inicioBrutoMs`.
export function proximoInicioBruto(inicioBrutoMs: number, segmento: SegmentoComDuracao): number {
  return inicioBrutoMs + pausaMs(segmento) + estimarDuracaoSegmento(segmento) * 1000;
}

// Valor mandado em inicio_previsto: a cadeia bruta corrigida pelo desvio, nunca no passado.
export function inicioAEnviar(inicioBrutoMs: number, desvioMs: number, agoraMs: number): number {
  return Math.max(agoraMs, inicioBrutoMs + desvioMs);
}

// Desvio medido quando o bloco começa a tocar: quanto o real (sem a pausa aplicada) ficou atrás da cadeia.
export function medirDesvio(inicioBrutoMs: number | undefined, agoraMs: number, pausaAplicadaMs: number): number | null {
  if (inicioBrutoMs === undefined) return null;
  return agoraMs - pausaAplicadaMs - inicioBrutoMs;
}
