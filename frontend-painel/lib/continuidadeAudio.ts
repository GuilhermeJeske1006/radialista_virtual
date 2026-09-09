/** Um único intervalo antes do conteúdo preparado, com cancelamento ao pausar/pular. */
export function esperarTransicao(ms: number, signal: AbortSignal): Promise<boolean> {
  if (signal.aborted) return Promise.resolve(false);
  if (ms <= 0) return Promise.resolve(true);
  return new Promise((resolve) => {
    const concluir = (tocavel: boolean) => {
      clearTimeout(timer);
      signal.removeEventListener("abort", cancelar);
      resolve(tocavel);
    };
    const cancelar = () => concluir(false);
    const timer = setTimeout(() => concluir(true), ms);
    signal.addEventListener("abort", cancelar, { once: true });
  });
}

export function pausaAntesDoBloco(ms?: number | null): number {
  // Servidores anteriores não conhecem pausa_antes_ms. Não reutilizar intervalo_ms:
  // ele era aplicado depois do bloco e somado a outra espera no navegador.
  return ms != null && Number.isFinite(ms) ? Math.max(0, Math.min(5000, ms)) : 350;
}

export async function reproduzirGrupoDeFalas<T>(
  falas: T[],
  ativo: () => boolean,
  tocar: (fala: T, indice: number) => Promise<number>,
  baixarFundo: (baixo: boolean) => void,
): Promise<number> {
  if (!falas.length || !ativo()) return 0;
  let duracao = 0;
  baixarFundo(true);
  try {
    for (let i = 0; i < falas.length && ativo(); i++) {
      duracao += await tocar(falas[i], i);
    }
    return duracao;
  } finally {
    // Uma execução substituída não deve mexer na cama da nova execução.
    if (ativo()) baixarFundo(false);
  }
}
