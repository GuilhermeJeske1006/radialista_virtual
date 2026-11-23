// F14: espelho de backend app/live/narrativo.py::eh_quadro_narrativo. Quadro fixo cujo nome começa com
// "narrativo" ou "historia" (sem acento, sem diferença de caixa) é contado em quatro passos no ao vivo.
const PREFIXOS_NARRATIVOS = ["narrativo", "historia"];

export function ehQuadroNarrativo(label: string | null | undefined): boolean {
  if (!label) return false;
  const normalizado = label.trim().normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  return PREFIXOS_NARRATIVOS.some((prefixo) => normalizado.startsWith(prefixo));
}
