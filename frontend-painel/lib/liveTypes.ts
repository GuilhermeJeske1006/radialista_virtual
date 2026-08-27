import { Programa } from "./types";

export type MusicaBloco = {
  video_id: string;
  titulo: string;
  inicio_segundos?: number;
  fim_segundos?: number | null;
  duracao_segundos?: number | null;
};

// Uma linha de dialogo multi-voz (ver ProgramaRadialista no backend) -- so vem preenchido
// quando o programa tem mais de um radialista, uma linha por participante que falou no bloco.
export type FalaItem = { radio_config_id: number; nome_locutor: string; voz_id: string | null; texto: string };

export type ProgramSegment = {
  id: number;
  tipo: string;
  fala: string;
  criado_em: string;
  origem: "ia" | "local" | "manual";
  video_id?: string | null;
  titulo_musica?: string | null;
  inicio_segundos?: number;
  fim_segundos?: number | null;
  musicas?: MusicaBloco[];
  patrocinador_id?: number | null;
  patrocinador_audio?: boolean;
  patrocinador_voz_id?: string | null;
  vinheta_id?: number | null;
  falas?: FalaItem[] | null;
  // Duracao REAL do bloco inteiro (soma do tempo de ar de cada musica + cada fala que
  // compoe esse bloco, medida ao vivo pelo player/audio -- ver atualizarDuracaoFala em
  // useLiveEngine.ts), preenchida so' depois que o bloco termina de tocar.
  duracao_segundos?: number;
};

export type LiveProgramResponse = {
  tipo: string;
  fala: string;
  criado_em: string;
  video_id?: string | null;
  titulo_musica?: string | null;
  inicio_segundos?: number;
  fim_segundos?: number | null;
  musicas?: MusicaBloco[];
  patrocinador_id?: number | null;
  patrocinador_audio?: boolean;
  patrocinador_voz_id?: string | null;
  vinheta_id?: number | null;
  falas?: FalaItem[] | null;
};

export type ProgramaOpcao = Programa & { radialistaId: number; radialistaNome: string };

export type AudioFala = { url: string | null; blob: Blob | null };

export type SegmentoPreparado = {
  segmento: Omit<ProgramSegment, "id">;
  audioUrl: string | null;
  audioBlob: Blob | null;
  // dialogo multi-voz: um audio por linha/radialista, tocados em sequencia -- null quando
  // o bloco e' de um radialista so (usa audioUrl/audioBlob acima, como sempre foi).
  audiosFalas: AudioFala[] | null;
};

// "fala" | "musica": o que esta tocando agora, pro transport de decorrido/restante/termino
// saber se le audioFalaRef ou musicPlayerRef. "idle": nada tocando.
export type EstagioAoVivo = "fala" | "musica" | "idle";
