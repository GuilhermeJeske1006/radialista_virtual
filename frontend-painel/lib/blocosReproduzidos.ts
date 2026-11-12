import { apiFetch } from "./api";

export type ConfirmacaoBloco = { bloco_id?: number | null; bloco_token?: string | null; bloco_programa_id?: number | null };
let player: string | null = null;
function identidade() {
  // Cada aba é um player distinto; sessionStorage é copiado ao duplicar uma aba.
  if (!player) player = crypto.randomUUID();
  return player;
}

export async function informarBloco(bloco: ConfirmacaoBloco, estado: "reproduzindo" | "concluido" | "falhou" | "interrompido" | "heartbeat") {
  if (!bloco.bloco_id || !bloco.bloco_token) return;
  return apiFetch(`/ouvintes/transmissao/blocos/${bloco.bloco_id}/eventos`, {
    method: "POST", body: JSON.stringify({ token: bloco.bloco_token, player_id: identidade(), estado }),
  });
}
