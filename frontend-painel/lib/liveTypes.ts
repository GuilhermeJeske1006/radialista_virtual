import { Programa } from "./types";

export type MusicaBloco = {
  video_id: string;
  titulo: string;
  // Canal/artista da faixa -- usado pro historico mandado de volta pro backend carregar
  // "Titulo - Canal" de cada musica do bloco (ver prepararSegmento em useLiveEngine.ts),
  // pra IA poder comentar as faixas assim que a sequencia acabar.
  canal?: string;
  inicio_segundos?: number;
  fim_segundos?: number | null;
  duracao_segundos?: number | null;
};

// Uma linha de dialogo multi-voz (ver ProgramaRadialista no backend) -- so vem preenchido
// quando o programa tem mais de um radialista, uma linha por participante que falou no bloco.
export type FalaItem = { radio_config_id: number; nome_locutor: string; voz_id: string | null; texto: string };

export type PesquisaNoticias = {
  status: "nao_solicitada" | "desabilitada" | "ok" | "sem_resultados" | "indisponivel";
  fontes: { titulo: string; url: string }[];
  consultado_em: string | null;
};

export type ConfirmacaoPedido = {
  pedido_id?: number | null;
  pedido_token?: string | null;
  pedido_programa_id?: number | null;
  pedido_radialista_id?: number | null;
};

export type ProgramSegment = ConfirmacaoPedido & {
  pesquisa_noticias?: PesquisaNoticias | null;
  id: number;
  tipo: string;
  fala: string;
  tom?: "calmo" | "neutro" | "energico" | null;
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
  // Campo legado. O player aplica apenas pausa_antes_ms, antes do conteúdo preparado.
  intervalo_ms?: number | null;
  pausa_antes_ms?: number | null;
  duracao_alvo_segundos?: [number, number] | null;
};

export type LiveProgramResponse = ConfirmacaoPedido & {
  pesquisa_noticias?: PesquisaNoticias | null;
  tipo: string;
  fala: string;
  tom?: "calmo" | "neutro" | "energico" | null;
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
  intervalo_ms?: number | null;
  pausa_antes_ms?: number | null;
  duracao_alvo_segundos?: [number, number] | null;
  // Audio ja sintetizado (mp3, base64) do texto de `fala` -- preenchido so' pra bloco de fala
  // unica quando o backend conseguiu sintetizar dentro do proprio /proxima (ver Plano B.3).
  // Ausente/null: frontend cai pro fallback antigo de chamar POST /tts em separado.
  audio_base64?: string | null;
  // Diferencia "nao ha audio porque o bloco nao usa TTS" de uma falha ja conhecida pelo
  // backend, evitando uma segunda chamada cara e a voz sintetica do navegador.
  audio_status?: "pronto" | "pendente" | "falhou" | "indisponivel" | "nao_aplicavel";
  audio_erro?: string | null;
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
