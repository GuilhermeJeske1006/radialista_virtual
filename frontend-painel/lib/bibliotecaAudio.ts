import { CategoriaVinheta } from "./types";

export type BibliotecaAudioItem = {
  id: number;
  nome: string;
  categoria_id: number | null;
  audio_nome_original: string | null;
  duracao_segundos: number | null;
  cor: string | null;
  ordem: number;
  ativo: boolean;
  // Vinheta gerada por programa (ver backend app/vinhetas/) -- upload manual vem
  // origem "manual", status "pronta" e o resto nulo.
  programa_id?: number | null;
  papel?: PapelVinheta | null;
  texto?: string | null;
  status?: StatusVinheta;
  origem?: "auto" | "manual";
};

export type PapelVinheta = "abertura" | "passagem" | "encerramento";
export type StatusVinheta = "pendente" | "gerando" | "pronta" | "erro";

// Vinheta de programa como sai de GET /vinhetas (backend app/vinhetas/router.py).
export type Vinheta = {
  id: number;
  nome: string;
  programa_id: number | null;
  categoria_id: number | null;
  papel: PapelVinheta | null;
  texto: string | null;
  voz_id: string | null;
  trilha_id: number | null;
  trilha_origem: OrigemTrilha | null;
  volume_trilha_db: number;
  usar_trilha: boolean;
  status: StatusVinheta;
  erro_msg: string | null;
  origem: "auto" | "manual";
  ativo: boolean;
  tem_audio: boolean;
  duracao_segundos: number | null;
};

export type OrigemTrilha = "ia" | "banco" | "upload";

export type TrilhaVinheta = {
  id: number;
  programa_id: number | null;
  origem: OrigemTrilha;
  estilo: string | null;
  duracao_ms: number | null;
};

// Item da biblioteca que ainda nao tem arquivo (vinheta gerada pendente/sem TTS) nao pode ir pro
// cartwall -- nao ha o que tocar.
export function temAudio(item: BibliotecaAudioItem): boolean {
  return item.audio_nome_original != null;
}

export function formatarDuracao(segundos: number | null): string {
  if (segundos == null) return "--:--";
  const m = Math.floor(segundos / 60);
  const s = segundos % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

const SEM_CATEGORIA = "Sem categoria";

// Agrupa itens (vinhetas ou propagandas) por categoria, na ordem em que as categorias
// aparecem em `categorias`, com o grupo "Sem categoria" sempre por último.
export function agruparPorCategoria<T extends { categoria_id: number | null }>(
  itens: T[],
  categorias: CategoriaVinheta[]
): [{ id: number | null; nome: string }, T[]][] {
  const grupos = new Map<number | null, T[]>();
  for (const item of itens) {
    if (!grupos.has(item.categoria_id)) grupos.set(item.categoria_id, []);
    grupos.get(item.categoria_id)!.push(item);
  }

  const resultado: [{ id: number | null; nome: string }, T[]][] = [];
  for (const categoria of categorias) {
    const itensDaCategoria = grupos.get(categoria.id);
    if (itensDaCategoria) resultado.push([{ id: categoria.id, nome: categoria.nome }, itensDaCategoria]);
  }
  const semCategoria = grupos.get(null);
  if (semCategoria) resultado.push([{ id: null, nome: SEM_CATEGORIA }, semCategoria]);
  return resultado;
}
