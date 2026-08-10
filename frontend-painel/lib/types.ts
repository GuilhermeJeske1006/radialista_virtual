export type Radialista = {
  id: number;
  ativo: boolean;
  nome_locutor: string;
  personalidade: string;
  voz_id: string | null;
  timezone: string;
};

export const RADIALISTA_VAZIO: Omit<Radialista, "id" | "ativo"> = {
  nome_locutor: "",
  personalidade: "",
  voz_id: null,
  timezone: "America/Sao_Paulo",
};

export type RadioPerfil = {
  nome_radio: string;
  slogan: string;
  frequencia: string;
  telefone: string;
  endereco: string;
  cidade: string;
};

export type RadioConta = RadioPerfil & {
  wuzapi_token: string | null;
};

export const RADIO_PERFIL_VAZIO: RadioPerfil = {
  nome_radio: "",
  slogan: "",
  frequencia: "",
  telefone: "",
  endereco: "",
  cidade: "",
};

export type ConfiguracaoIA = {
  radialista: Radialista;
  programa: Programa;
};

export type Voz = {
  voz_id: string;
  nome: string;
  genero: string;
  descricao: string;
};

export type VozClonada = {
  id: number;
  nome: string;
  voz_id: string;
};

export type Programa = {
  id: number;
  radio_config_id: number;
  nome: string;
  descricao: string;
  dias_semana: number[];
  data_especifica: string | null;
  horario_inicio: string;
  horario_fim: string;
  ativo: boolean;

  tom: string;
  topicos_permitidos: string[];
  topicos_proibidos: string[];
  mensagem_saudacao: string;
  mensagem_recusa: string;
  limite_mensagens_hora: number;

  estrutura_blocos: string[];
  ia_pode_adicionar_blocos: boolean;

  generos_musicais: string[];
  musicas_permitidas: string[];
  musicas_bloqueadas: string[];
  criterios_busca_musicas: string;

  assuntos_ao_vivo: string[];
  tipos_noticias: string[];
  fontes_noticias: string[];

  pode_pesquisar: boolean;
  fontes_pesquisa: string[];
  instrucoes_pesquisa: string;
};

export const PROGRAMA_VAZIO: Omit<Programa, "id" | "radio_config_id"> = {
  nome: "",
  descricao: "",
  dias_semana: [],
  data_especifica: null,
  horario_inicio: "08:00:00",
  horario_fim: "10:00:00",
  ativo: true,

  tom: "informal e descontraido, como um locutor de radio local conversando com o ouvinte",
  topicos_permitidos: [],
  topicos_proibidos: [],
  mensagem_saudacao: "E ai! No que posso ajudar?",
  mensagem_recusa: "Desculpa, nao posso falar sobre isso por aqui. Bora falar de outro assunto?",
  limite_mensagens_hora: 10,

  estrutura_blocos: [],
  ia_pode_adicionar_blocos: true,

  generos_musicais: [],
  musicas_permitidas: [],
  musicas_bloqueadas: [],
  criterios_busca_musicas:
    "Priorizar musicas alinhadas ao perfil da radio, evitar letras explicitas e variar artistas.",

  assuntos_ao_vivo: [],
  tipos_noticias: [],
  fontes_noticias: [],

  pode_pesquisar: false,
  fontes_pesquisa: [],
  instrucoes_pesquisa:
    "Consultar apenas fontes permitidas, confirmar data da noticia e avisar quando nao houver certeza.",
};

// Vinculo de um radialista a um programa (dono ou co-apresentador), com papel e
// comportamento proprios do programa -- ver backend/app/models/programa_radialista.py.
export type RadialistaPrograma = {
  radio_config_id: number;
  nome_locutor: string;
  voz_id: string | null;
  papel: string;
  comportamento: string;
  e_dono: boolean;
};

export const PAPEIS_SUGERIDOS = ["Co-apresentador", "Comentarista", "Repórter convidado"];

export function normalizarPrograma(p: Programa): Programa {
  return {
    ...p,
    topicos_permitidos: p.topicos_permitidos ?? [],
    topicos_proibidos: p.topicos_proibidos ?? [],
    estrutura_blocos: p.estrutura_blocos ?? [],
    generos_musicais: p.generos_musicais ?? [],
    musicas_permitidas: p.musicas_permitidas ?? [],
    musicas_bloqueadas: p.musicas_bloqueadas ?? [],
    assuntos_ao_vivo: p.assuntos_ao_vivo ?? [],
    tipos_noticias: p.tipos_noticias ?? [],
    fontes_noticias: p.fontes_noticias ?? [],
    fontes_pesquisa: p.fontes_pesquisa ?? [],
  };
}

export const DIAS_SEMANA_LABEL = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"];

// Valores (`value`) casam com os tipos de bloco reconhecidos pelo motor do ao vivo
// (backend app/live/router.py) -- so nesses tipos o sistema busca musica de verdade,
// atende fila de pedidos do WhatsApp e ajusta prosodia automaticamente. Blocos digitados
// livremente (fora desse preset) funcionam como falas genericas, sem esse comportamento extra.
export const BLOCOS_PRESET: { value: string; label: string }[] = [
  { value: "abertura", label: "Abertura" },
  { value: "musica", label: "Música" },
  { value: "comentario", label: "Comentário" },
  { value: "noticia", label: "Notícia" },
  { value: "chamada_ouvinte", label: "Chamada ao ouvinte" },
];

const PATROCINADOR_BLOCO_RE = /^patrocinador:(\d+)$/;

// Recebe opcionalmente um mapa id -> nome (lista de patrocinadores da conta) pra resolver
// o label de blocos "patrocinador:<id>" -- ver EstruturaBlocosInput.tsx.
export function rotuloBloco(tipo: string, patrocinadores?: Record<number, string>): string {
  const match = tipo.match(PATROCINADOR_BLOCO_RE);
  if (match) {
    const id = Number(match[1]);
    const nome = patrocinadores?.[id];
    return nome ? `Patrocinador: ${nome}` : `Patrocinador #${id}`;
  }
  return BLOCOS_PRESET.find((b) => b.value === tipo)?.label ?? tipo;
}

export type Patrocinador = {
  id: number;
  nome: string;
  tipo_conteudo: "texto" | "audio";
  texto?: string | null;
  audio_nome_original?: string | null;
  voz_id?: string | null;
  ativo: boolean;
};

export type Conta = {
  id: number;
  nome: string;
  email: string;
  plano_status: string;
  plano: string;
  criado_em: string;
  tem_radio_config: boolean;
};
