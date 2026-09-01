import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SuporteChat from "../SuporteChat";

const apiFetchMock = vi.fn();

vi.mock("../../lib/api", () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
  ApiError: class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  },
}));

describe("SuporteChat", () => {
  it("comeca fechado, mostrando so o botao flutuante", () => {
    render(<SuporteChat />);
    expect(screen.queryByPlaceholderText("Digite sua dúvida...")).not.toBeInTheDocument();
    expect(screen.getByTitle("Suporte")).toBeInTheDocument();
  });

  it("abre o painel, envia pergunta e mostra a resposta do backend", async () => {
    const user = userEvent.setup();
    apiFetchMock.mockResolvedValue({ resposta: "Vai em Conta > WhatsApp e escaneia o QR code." });

    render(<SuporteChat />);
    await user.click(screen.getByTitle("Suporte"));

    const input = screen.getByPlaceholderText("Digite sua dúvida...");
    await user.type(input, "como conecto o whatsapp?");
    await user.click(screen.getByRole("button", { name: "Enviar" }));

    expect(await screen.findByText(/escaneia o QR code/)).toBeInTheDocument();
    expect(apiFetchMock).toHaveBeenCalledWith(
      "/suporte/chat",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ mensagem: "como conecto o whatsapp?", historico: [] }),
      })
    );
  });

  it("mostra erro quando o backend falha", async () => {
    const user = userEvent.setup();
    const { ApiError } = await import("../../lib/api");
    apiFetchMock.mockRejectedValue(new ApiError(502, "Não consegui responder agora. Tenta de novo em instantes."));

    render(<SuporteChat />);
    await user.click(screen.getByTitle("Suporte"));
    await user.type(screen.getByPlaceholderText("Digite sua dúvida..."), "oi");
    await user.click(screen.getByRole("button", { name: "Enviar" }));

    expect(await screen.findByText("Não consegui responder agora. Tenta de novo em instantes.")).toBeInTheDocument();
  });
});
