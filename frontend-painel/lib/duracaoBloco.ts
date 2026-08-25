import { Patrocinador } from "./types";
import { BibliotecaAudioItem } from "./bibliotecaAudio";

// Estimativas grosseiras pra dar noção de tempo na tela de montagem -- o motor real
// (backend/app/live/router.py) varia a duração de cada bloco por LLM/prosódia, e a IA pode
// emendar blocos extra (ver ia_pode_adicionar_blocos). Nunca é medição, sempre estimativa.
const PALAVRAS_POR_SEGUNDO = 2.5;

// segundos médios de fala por tipo de bloco automático (abertura/comentario/noticia/chamada
// tendem a ser falas curtas; "musica" aqui é só a chamada da faixa, a faixa em si soma mais
// abaixo via DURACAO_MUSICA_SEGUNDOS).
const DURACAO_FALA_PADRAO_SEGUNDOS: Record<string, number> = {
  abertura: 40,
  musica: 15,
  comentario: 45,
  noticia: 40,
  chamada_ouvinte: 35,
};

const DURACAO_MUSICA_SEGUNDOS = 180;

const PATROCINADOR_RE = /^patrocinador:(\d+)$/;
const VINHETA_RE = /^vinheta:(\d+)$/;

function duracaoPorContagemDePalavras(texto: string): number {
  const palavras = texto.trim().split(/\s+/).filter(Boolean).length;
  return Math.max(5, Math.round(palavras / PALAVRAS_POR_SEGUNDO));
}

export type DuracaoBloco = { segundos: number; estimada: boolean };

export function estimarDuracaoBloco(
  bloco: string,
  patrocinadores: Patrocinador[],
  vinhetas: BibliotecaAudioItem[] = []
): DuracaoBloco {
  const matchPatrocinador = bloco.match(PATROCINADOR_RE);
  if (matchPatrocinador) {
    const patrocinador = patrocinadores.find((p) => p.id === Number(matchPatrocinador[1]));
    if (!patrocinador) return { segundos: 20, estimada: true };
    if (patrocinador.tipo_conteudo === "audio") {
      return patrocinador.duracao_segundos != null
        ? { segundos: patrocinador.duracao_segundos, estimada: false }
        : { segundos: 20, estimada: true };
    }
    return { segundos: duracaoPorContagemDePalavras(patrocinador.texto || ""), estimada: true };
  }

  const matchVinheta = bloco.match(VINHETA_RE);
  if (matchVinheta) {
    const vinheta = vinhetas.find((v) => v.id === Number(matchVinheta[1]));
    return vinheta?.duracao_segundos != null
      ? { segundos: vinheta.duracao_segundos, estimada: false }
      : { segundos: 20, estimada: true };
  }

  const base = DURACAO_FALA_PADRAO_SEGUNDOS[bloco];
  if (base != null) {
    const total = bloco === "musica" ? base + DURACAO_MUSICA_SEGUNDOS : base;
    return { segundos: total, estimada: true };
  }

  // bloco personalizado (texto livre): sem tipo reconhecido, so' da pra estimar
  // pelo tamanho do proprio rotulo -- e' o pior caso, tende a ser bem impreciso.
  return { segundos: duracaoPorContagemDePalavras(bloco), estimada: true };
}

export function formatarDuracaoBloco(segundos: number): string {
  if (segundos < 60) return `${segundos}s`;
  const h = Math.floor(segundos / 3600);
  const m = Math.floor((segundos % 3600) / 60);
  const s = segundos % 60;
  if (h > 0) return m > 0 ? `${h}h ${m}min` : `${h}h`;
  return s > 0 ? `${m}min ${s}s` : `${m}min`;
}
