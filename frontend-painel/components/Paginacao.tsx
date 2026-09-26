"use client";

type Props = {
  // Página atual, a partir de 1.
  pagina: number;
  onMudar: (pagina: number) => void;
  // Total conhecido mostra "2 de 5"; sem ele (extrato), basta saber se há próxima.
  totalPaginas?: number;
  temProxima?: boolean;
  carregando?: boolean;
  rotulo: string;
};

const BOTAO = "rounded-lg px-3 py-1.5 text-xs font-medium text-fg/80 hover:bg-fg/5 hover:text-fg disabled:opacity-40 disabled:hover:bg-transparent disabled:cursor-not-allowed";

export default function Paginacao({ pagina, onMudar, totalPaginas, temProxima, carregando = false, rotulo }: Props) {
  const haProxima = totalPaginas != null ? pagina < totalPaginas : !!temProxima;
  if (pagina <= 1 && !haProxima) return null;
  return (
    <nav aria-label={rotulo} className="flex items-center justify-between gap-3">
      <button type="button" className={BOTAO} disabled={pagina <= 1 || carregando} onClick={() => onMudar(pagina - 1)}>
        ‹ Anterior
      </button>
      <span className="text-xs text-fg/65 tabular-nums" aria-live="polite">
        {totalPaginas != null ? `Página ${pagina} de ${totalPaginas}` : `Página ${pagina}`}
      </span>
      <button type="button" className={BOTAO} disabled={!haProxima || carregando} onClick={() => onMudar(pagina + 1)}>
        Próxima ›
      </button>
    </nav>
  );
}

// Fatia de uma lista já carregada; página fora do intervalo cai na última.
export function paginar<T>(itens: T[], pagina: number, porPagina: number) {
  const totalPaginas = Math.max(1, Math.ceil(itens.length / porPagina));
  const atual = Math.min(Math.max(1, pagina), totalPaginas);
  return { itens: itens.slice((atual - 1) * porPagina, atual * porPagina), pagina: atual, totalPaginas };
}
