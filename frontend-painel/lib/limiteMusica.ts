// O limite cobre a faixa inteira; seis minutos não é a duração máxima de uma música.
export function limiteMusicaMs(duracao?: number | null, inicio = 0, fim?: number | null): number {
  const termino = fim != null && fim > inicio ? fim : duracao;
  const segundos = typeof termino === "number" && Number.isFinite(termino) && termino > inicio
    ? termino - inicio + 30 : 6 * 60;
  return Math.min(25 * 60, Math.max(60, segundos)) * 1000;
}
