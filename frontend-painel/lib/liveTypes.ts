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
  bloco_id?: number | null;
  bloco_token?: string | null;
  bloco_programa_id?: number | null;
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
  // true = /vinhetas/{id}/audio tem o arquivo mixado (voz + trilha). false = vinheta gerada ainda
  // sem audio: toca `fala` via TTS normal, sem trilha (o ao vivo nunca espera a mixagem).
  vinheta_audio?: boolean;
  // So' na fala de encerramento: vinheta de encerramento do programa, tocada logo depois dela.
  vinheta_encerramento_id?: number | null;
  vinheta_encerramento_audio?: boolean;
  vinheta_encerramento_texto?: string | null;
  // Posicoes do roteiro consumidas por este bloco (>1 quando o backend pulou vinheta desativada).
  passos_roteiro?: number;
  falas?: FalaItem[] | null;
  // Duracao REAL do bloco inteiro (soma do tempo de ar de cada musica + cada fala que
  // compoe esse bloco, medida ao vivo pelo player/audio -- ver atualizarDuracaoFala em
  // useLiveEngine.ts), preenchida so' depois que o bloco termina de tocar.
  duracao_segundos?: number;
  // Campo legado. O player aplica apenas pausa_antes_ms, antes do conteúdo preparado.
  intervalo_ms?: number | null;
  pausa_antes_ms?: number | null;
  duracao_alvo_segundos?: [number, number] | null;
  // Estimativa do backend (fala no ritmo calibrado da voz ou medida, músicas, vinhetas) -- encadeia o
  // horário previsto do bloco seguinte (ver lib/relogioAoVivo.ts).
  duracao_prevista_s?: number | null;
  // Só em programa com relógio da hora: etapa, próximo compromisso e espaço (backtiming).
  relogio?: RelogioAoVivo | null;
  // Duração real da fala (F2). Opcionais: o painel ainda não usa, só carrega no segmento.
  duracao_fala_s?: number | null;
  duracao_fala_estimada_s?: number | null;
  orcamento_fala_s?: OrcamentoFala | null;
  fala_ajuste?: FalaAjuste | null;
  // Validador pós-geração (F3): música anunciada sem confirmação ou fragmento abaixo do mínimo. Opcional e só
  // carregado no segmento (o painel não usa); nulo quando nada foi encontrado.
  validacao_fala?: ValidacaoFala | null;
  // Promessas feitas no ar registradas e resolvidas neste bloco (F4). Opcional e só carregado no segmento (o
  // painel não usa; o relatório é da F11); nulo quando não houve nenhuma.
  promessas?: PromessasBloco | null;
  // Horário previsto enviado ao backend e início bruto da cadeia (ms desde a época).
  inicio_previsto_ms?: number;
  inicio_bruto_ms?: number;
};

export type EtapaRelogioAoVivo = {
  hora: number;
  inicio_s: number;
  tipo: string;
  tipo_efetivo: string;
  rotulo: string;
  natureza: string;
  hard_time: boolean;
  inicio: string;
  fim: string;
};

export type RelogioAoVivo = {
  preset: string | null;
  inicio_previsto: string;
  inicio_previsto_aceito: boolean;
  hora: number;
  etapa: EtapaRelogioAoVivo;
  proximo_compromisso: EtapaRelogioAoVivo | null;
  segundos_ate_hard_time: number | null;
  espaco_s: number | null;
  acao: string;
  orcamento_s: [number, number] | null;
  puladas?: string[];
  // F3: de onde veio o horário do bloco. "estimado": painel antigo sem inicio_previsto, cadeia no servidor.
  origem_instante?: "painel" | "estimado" | "agora";
  // F4: etapas com promessa aberta ("hora:inicio_s"), reservadas no backtiming. Nulo sem obrigação.
  obrigacoes?: string[] | null;
};

// Orçamento de duração da fala devolvido pelo /proxima (F2). aplicado=false: só medido (formato padrão
// sem relógio). O /tts com pós-produção devolve a duração medida no cabeçalho X-Duracao-Fala-S.
export type OrcamentoFala = {
  min_s: number;
  alvo_s: number;
  max_s: number;
  fonte: "relogio" | "formato" | "observacao";
  aplicado: boolean;
};

// Validador pós-geração da fala (F3, app/live/validacao_fala.py).
export type ViolacaoFala = {
  regra: string;
  trecho: string;
  ref_id: string;
};

export type ValidacaoFala = {
  violacoes: ViolacaoFala[];
  acao: "nenhuma" | "reescrita" | "mencao_removida" | "fala_neutra" | "fala_removida";
};

// Promessas feitas no ar (F4, app/live/promessas.py e a tabela promessas_no_ar).
export type PromessaRegistrada = {
  id: number;
  tipo: string;
  trecho: string;
  evento_alvo: string;
  prazo?: string | null;
  prazo_posicao?: number | null;
};

export type PromessaResolvida = {
  id: number;
  estado: "cumprida" | "cancelada" | "vencida";
  contingencia?: string | null;
};

export type PromessasBloco = {
  registradas: PromessaRegistrada[];
  resolvidas: PromessaResolvida[];
};

// O que o backend fez para a fala caber no orçamento; nunca acelera a voz.
export type FalaAjuste = "nenhum" | "reescrita" | "encurtada" | "cortada" | "acima_do_teto";

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
  // true = /vinhetas/{id}/audio tem o arquivo mixado (voz + trilha). false = vinheta gerada ainda
  // sem audio: toca `fala` via TTS normal, sem trilha (o ao vivo nunca espera a mixagem).
  vinheta_audio?: boolean;
  // So' na fala de encerramento: vinheta de encerramento do programa, tocada logo depois dela.
  vinheta_encerramento_id?: number | null;
  vinheta_encerramento_audio?: boolean;
  vinheta_encerramento_texto?: string | null;
  // Posicoes do roteiro consumidas por este bloco (>1 quando o backend pulou vinheta desativada).
  passos_roteiro?: number;
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
  // Audio (mp3, base64) de cada linha de `falas` acima, mesmo indice -- sintetizado em paralelo
  // dentro do proprio /proxima pra dialogo multi-voz (ver _sintetizar_falas_multivoz no
  // backend). Item null = aquela linha falhou; prepararAudio cai pro /tts avulso so' pra ela.
  audios_falas_base64?: (string | null)[] | null;
  duracao_prevista_s?: number | null;
  relogio?: RelogioAoVivo | null;
  // F2: duração medida (só com áudio sintetizado no próprio /proxima), estimada, orçamento e ajuste.
  duracao_fala_s?: number | null;
  duracao_fala_estimada_s?: number | null;
  orcamento_fala_s?: OrcamentoFala | null;
  fala_ajuste?: FalaAjuste | null;
  // F4: promessas registradas e resolvidas neste bloco; nulo quando não houve nenhuma.
  promessas?: PromessasBloco | null;
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
