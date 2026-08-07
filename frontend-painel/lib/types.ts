export type Radialista = {
  id: number;
  wuzapi_token: string | null;
  ativo: boolean;
  nome_locutor: string;
  voz_id: string | null;
  timezone: string;
};

export const RADIALISTA_VAZIO: Omit<Radialista, "id" | "wuzapi_token" | "ativo"> = {
  nome_locutor: "",
  voz_id: null,
  timezone: "America/Sao_Paulo",
};

export type Voz = {
  voz_id: string;
  nome: string;
  genero: string;
  descricao: string;
};

export type Programa = {
  id: number;
  radio_config_id: number;
  nome: string;
  dias_semana: number[];
  horario_inicio: string;
  horario_fim: string;
  ativo: boolean;

  tom: string;
  topicos_permitidos: string[];
  topicos_proibidos: string[];
  mensagem_saudacao: string;
  mensagem_recusa: string;
  limite_mensagens_hora: number;

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
  dias_semana: [],
  horario_inicio: "08:00:00",
  horario_fim: "10:00:00",
  ativo: true,

  tom: "informal e descontraido, como um locutor de radio local conversando com o ouvinte",
  topicos_permitidos: [],
  topicos_proibidos: [],
  mensagem_saudacao: "E ai! No que posso ajudar?",
  mensagem_recusa: "Desculpa, nao posso falar sobre isso por aqui. Bora falar de outro assunto?",
  limite_mensagens_hora: 10,

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

export function normalizarPrograma(p: Programa): Programa {
  return {
    ...p,
    topicos_permitidos: p.topicos_permitidos ?? [],
    topicos_proibidos: p.topicos_proibidos ?? [],
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
