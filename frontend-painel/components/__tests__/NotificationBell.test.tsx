import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import NotificationBell from "../NotificationBell";

const apiFetchMock = vi.fn();
const pushMock = vi.fn();

vi.mock("../../lib/api", () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

const NOTIFICACAO = {
  id: 1,
  tipo: "billing",
  titulo: "Assinatura ativada",
  mensagem: "Seu plano foi ativado com sucesso.",
  link: "/billing",
  lida: false,
  criado_em: "2026-08-31T10:00:00Z",
};

beforeEach(() => {
  apiFetchMock.mockReset();
  pushMock.mockReset();
});

describe("NotificationBell", () => {
  it("mostra o total de nao lidas vindo do polling", async () => {
    apiFetchMock.mockResolvedValue({ total: 2 });
    render(<NotificationBell />);
    expect(await screen.findByText("2")).toBeInTheDocument();
  });

  it("abre o dropdown e lista as notificacoes", async () => {
    const user = userEvent.setup();
    apiFetchMock.mockImplementation((path: string) => {
      if (path === "/notificacoes/contagem-nao-lidas") return Promise.resolve({ total: 1 });
      if (path === "/notificacoes") return Promise.resolve({ notificacoes: [NOTIFICACAO] });
      return Promise.resolve({});
    });

    render(<NotificationBell />);
    await user.click(screen.getByTitle("Notificações"));

    expect(await screen.findByText("Assinatura ativada")).toBeInTheDocument();
    expect(screen.getByText("Seu plano foi ativado com sucesso.")).toBeInTheDocument();
  });

  it("marca como lida e navega ao clicar numa notificacao", async () => {
    const user = userEvent.setup();
    apiFetchMock.mockImplementation((path: string) => {
      if (path === "/notificacoes/contagem-nao-lidas") return Promise.resolve({ total: 1 });
      if (path === "/notificacoes") return Promise.resolve({ notificacoes: [NOTIFICACAO] });
      return Promise.resolve({});
    });

    render(<NotificationBell />);
    await user.click(screen.getByTitle("Notificações"));
    await user.click(await screen.findByText("Assinatura ativada"));

    expect(apiFetchMock).toHaveBeenCalledWith("/notificacoes/1/marcar-lida", { method: "POST" });
    expect(pushMock).toHaveBeenCalledWith("/billing");
  });

  it("mostra estado vazio quando nao ha notificacoes", async () => {
    const user = userEvent.setup();
    apiFetchMock.mockImplementation((path: string) => {
      if (path === "/notificacoes/contagem-nao-lidas") return Promise.resolve({ total: 0 });
      if (path === "/notificacoes") return Promise.resolve({ notificacoes: [] });
      return Promise.resolve({});
    });

    render(<NotificationBell />);
    await user.click(screen.getByTitle("Notificações"));

    expect(await screen.findByText("Nenhuma notificação por aqui.")).toBeInTheDocument();
  });
});
