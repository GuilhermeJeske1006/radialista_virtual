export const ROTEIRO_MUSICAL = ["musica", "musica", "identificacao", "musica", "musica", "retomada"];

/** Prévia do ciclo musical; abertura só na largada, encerramento pelo horário. */
export function tipoMusical(estrutura: string[], total: number): string {
  if (total === 0) return "abertura";
  const personalizado = estrutura.map((t) => t.trim()).filter((t) => {
    const normalizado = t.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
    return t && normalizado !== "abertura" && !/^encerramento(?: |$)/.test(normalizado);
  });
  const roteiro = personalizado.length ? personalizado : ROTEIRO_MUSICAL;
  return roteiro[(total - 1) % roteiro.length];
}
