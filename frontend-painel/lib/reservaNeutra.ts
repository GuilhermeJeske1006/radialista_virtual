// Reorientação de quem acabou de sintonizar quando o painel não consegue a fala do backend (F5, D16): repetição
// permitida, sem prometer conteúdo. Mesmos modelos do backend (app/live/validacao_fala.py, reserva_neutra).
export function falaReservaNeutra(programa?: string | null, radio?: string | null): string {
  const nomePrograma = (programa ?? "").trim();
  const nomeRadio = (radio ?? "").trim();
  if (nomePrograma && nomeRadio) return `Você está no ${nomePrograma}, na ${nomeRadio}.`;
  if (nomeRadio) return `Você está na ${nomeRadio}.`;
  if (nomePrograma) return `Você está no ${nomePrograma}.`;
  return "Você está na rádio.";
}
