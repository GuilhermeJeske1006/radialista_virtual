const CHAVE = "radialista_atual_id";

export function getRadialistaAtualId(): number | null {
  if (typeof window === "undefined") return null;
  const valor = window.localStorage.getItem(CHAVE);
  return valor ? Number(valor) : null;
}

export function setRadialistaAtualId(id: number): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(CHAVE, String(id));
}
