// Fala do locutor sobre a introdução da música (o "ramp" de rádio: o locutor entra com a música já tocando,
// baixinha, e termina de falar antes do vocal entrar -- "bater o poste"). O início do vocal vem do backend
// (app/live/audio_analysis.py::obter_inicio_vocal, medido pela 1a palavra cantada); sem ele, o locutor fala
// ANTES da música, como sempre falou. Posições abaixo são em segundos do VÍDEO (o mesmo eixo de
// inicio_segundos e de player.getCurrentTime()).

export const FALA_SOBRE_INTRO = {
  // música sozinha antes da voz entrar: o ouvinte reconhece a faixa e o fade de entrada termina (1,5 s)
  ENTRADA_S: 2,
  // a fala termina ao menos isso antes do vocal -- cobre a imprecisão de ±0,5 s da transcrição, a volta do
  // volume da música (fade) e o respiro antes da voz cantada
  MARGEM_VOCAL_S: 1.5,
  // introdução menor que isso não comporta fala nenhuma que valha a pena (cold intro: vocal quase no início)
  INTRO_MIN_S: 8,
  // fala longa demais pra "ramp": passa a ser bloco de conversa, não frase de entrada
  FALA_MAX_S: 15,
  // volume da música enquanto o locutor fala (0-100); o volume cheio volta ao terminar
  VOLUME_MUSICA_SOB_FALA: 30,
  FADE_ABAIXAR_MS: 600,
  FADE_VOLTAR_MS: 900,
  // se a fala ainda está no ar quando a posição chega a (vocal - isso), é cortada: nunca fala por cima do vocal
  CORTE_ANTES_VOCAL_S: 0.4,
  // quanto esperar a música chegar na posição de entrada (buffering) antes de desistir de falar por cima
  ESPERA_MAX_ENTRADA_MS: 8000,
} as const;

export type PlanoFalaSobreIntro = {
  /** posição (s do vídeo) em que a voz entra */
  posicaoEntradaS: number;
  /** posição (s do vídeo) a partir da qual a fala é cortada se ainda estiver no ar */
  posicaoCorteS: number;
};

export function planejarFalaSobreIntro(entrada: {
  inicioSegundos?: number | null;
  inicioVocalSegundos?: number | null;
  duracaoFalaSegundos?: number | null;
}): PlanoFalaSobreIntro | null {
  const { inicioSegundos, inicioVocalSegundos, duracaoFalaSegundos } = entrada;
  if (inicioVocalSegundos == null || !Number.isFinite(inicioVocalSegundos)) return null;
  if (duracaoFalaSegundos == null || !Number.isFinite(duracaoFalaSegundos) || duracaoFalaSegundos <= 0) return null;
  if (duracaoFalaSegundos > FALA_SOBRE_INTRO.FALA_MAX_S) return null;

  const inicio = inicioSegundos ?? 0;
  if (inicioVocalSegundos - inicio < FALA_SOBRE_INTRO.INTRO_MIN_S) return null;

  const posicaoEntradaS = inicio + FALA_SOBRE_INTRO.ENTRADA_S;
  const fimDaFalaS = posicaoEntradaS + duracaoFalaSegundos;
  if (fimDaFalaS + FALA_SOBRE_INTRO.MARGEM_VOCAL_S > inicioVocalSegundos) return null;

  return { posicaoEntradaS, posicaoCorteS: inicioVocalSegundos - FALA_SOBRE_INTRO.CORTE_ANTES_VOCAL_S };
}

/** Duração (s) de um áudio já em memória (blob URL); null se o navegador não informar a tempo. */
export function medirDuracaoAudio(url: string, timeoutMs = 2000): Promise<number | null> {
  return new Promise((resolve) => {
    let audio: HTMLAudioElement;
    try {
      audio = new Audio(url);
    } catch {
      resolve(null);
      return;
    }
    const concluir = (duracao: number | null) => {
      clearTimeout(timer);
      resolve(duracao);
    };
    const timer = setTimeout(() => concluir(null), timeoutMs);
    audio.addEventListener(
      "loadedmetadata",
      () => concluir(Number.isFinite(audio.duration) && audio.duration > 0 ? audio.duration : null),
      { once: true },
    );
    audio.addEventListener("error", () => concluir(null), { once: true });
    try {
      audio.preload = "metadata";
    } catch {
      // ambiente sem suporte: o timeout resolve
    }
  });
}
