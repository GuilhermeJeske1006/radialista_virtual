// Categorizacao visual dos blocos da estrutura de um programa, pro roteiro (ver
// RoteiroBlocosEditor.tsx) se ler como uma "roda de programacao" -- musica vs. insercao
// produzida (vinheta/propaganda) vs. fala. So 3 grupos porque o app so tem 3 acentos de
// tema (amber/teal/rust, ver app/globals.css); rust fica reservado pra acoes destrutivas.
export type BlocoKind = "musica" | "insercao" | "fala" | "custom";

const FALA_PRESETS = new Set(["abertura", "comentario", "noticia", "chamada_ouvinte"]);
const VINHETA_RE = /^vinheta:\d+$/;
const PATROCINADOR_RE = /^patrocinador:\d+$/;

export function kindDoBloco(tipo: string): BlocoKind {
  if (tipo === "musica") return "musica";
  if (VINHETA_RE.test(tipo) || PATROCINADOR_RE.test(tipo)) return "insercao";
  if (FALA_PRESETS.has(tipo)) return "fala";
  return "custom";
}

export const CORES_BLOCO: Record<BlocoKind, { dot: string; borda: string; fundo: string }> = {
  musica: { dot: "bg-teal", borda: "border-teal/40", fundo: "bg-teal/10" },
  insercao: { dot: "bg-amber", borda: "border-amber/40", fundo: "bg-amber/10" },
  fala: { dot: "bg-fg/40", borda: "border-border-strong", fundo: "bg-bg" },
  custom: { dot: "bg-fg/20", borda: "border-border-strong border-dashed", fundo: "bg-bg" },
};

export const LEGENDA_BLOCO_KIND: Record<BlocoKind, string> = {
  musica: "Música",
  insercao: "Inserção",
  fala: "Fala",
  custom: "Personalizado",
};
