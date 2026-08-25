import { CategoriaVinheta } from "./types";

export type BibliotecaAudioItem = {
  id: number;
  nome: string;
  categoria_id: number | null;
  audio_nome_original: string;
  duracao_segundos: number | null;
  cor: string | null;
  ordem: number;
  ativo: boolean;
};

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
