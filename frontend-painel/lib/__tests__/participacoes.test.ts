import { beforeEach, describe, expect, it, vi } from "vitest";
import { confirmarParticipacao } from "../participacoes";
import { apiFetch } from "../api";
vi.mock("../api", () => ({apiFetch: vi.fn()}));
const pedido = {pedido_id: 3, pedido_token: "selecao", pedido_programa_id: 2};
beforeEach(() => vi.clearAllMocks());
describe("confirmação de reprodução", () => {
  it("não confirma segmento sem pedido", async () => {
    await confirmarParticipacao({}, "executado");
    expect(apiFetch).not.toHaveBeenCalled();
  });
  it.each(["executado", "falhou", "interrompido"] as const)("transmite o resultado real %s", async resultado => {
    vi.mocked(apiFetch).mockResolvedValue({});
    await confirmarParticipacao(pedido, resultado);
    expect(apiFetch).toHaveBeenCalledWith("/ouvintes/pedidos/3/reproducao", {method: "POST", body: JSON.stringify({token: "selecao", programa_id: 2, resultado})});
  });
  it("repete callback idempotente após falha de rede", async () => {
    vi.mocked(apiFetch).mockRejectedValueOnce(new Error("rede")).mockResolvedValue({});
    await confirmarParticipacao(pedido, "executado");
    expect(apiFetch).toHaveBeenCalledTimes(2);
  });
  it("limita tentativas e informa falha", async () => {
    vi.mocked(apiFetch).mockRejectedValue(new Error("rede"));
    await expect(confirmarParticipacao(pedido, "falhou")).rejects.toThrow("rede");
    expect(apiFetch).toHaveBeenCalledTimes(3);
  });
});
