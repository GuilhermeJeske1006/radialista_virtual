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

// Cada linha do dialogo multi-voz e' sintetizada isolada (uma chamada de API por locutor,
// ver _sintetizar_falas_multivoz no backend) e tocada aqui uma logo apos a outra -- sem
// nenhum intervalo, o corte entre quem fala soa como edicao digital, nao como alguem
// esperando a vez de falar. 280ms e' o "beat" curto de troca de turno em conversa real,
// perto do que ja se usa como pausa padrao entre blocos (ver pausaAntesDoBloco).
const PAUSA_ENTRE_LINHAS_MS = 280;

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
      if (i < falas.length - 1 && ativo()) {
        await new Promise((resolver) => setTimeout(resolver, PAUSA_ENTRE_LINHAS_MS));
        duracao += PAUSA_ENTRE_LINHAS_MS / 1000;
      }
    }
    return duracao;
  } finally {
    // Uma execução substituída não deve mexer na cama da nova execução.
    if (ativo()) baixarFundo(false);
  }
}
