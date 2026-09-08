import { apiFetch } from "./api";
import type { ConfirmacaoPedido } from "./liveTypes";

export async function confirmarParticipacao(pedido: ConfirmacaoPedido, resultado: "executado" | "falhou" | "interrompido") {
  if (!pedido.pedido_id || !pedido.pedido_token || !pedido.pedido_programa_id) return;
  // Endpoint idempotente: repetir o callback nunca executa o pedido novamente.
  for (let tentativa = 0; tentativa < 3; tentativa++) {
    try {
      return await apiFetch(`/ouvintes/pedidos/${pedido.pedido_id}/reproducao`, {
        method: "POST",
        body: JSON.stringify({token: pedido.pedido_token, programa_id: pedido.pedido_programa_id, resultado}),
      });
    } catch (erro) {
      if (tentativa === 2) throw erro;
    }
  }
}
