import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AppShell from "../AppShell";

const { push, apiFetch, limparContaCache } = vi.hoisted(() => ({
  push: vi.fn(),
  apiFetch: vi.fn().mockResolvedValue(undefined),
  limparContaCache: vi.fn(),
}));
vi.mock("next/navigation", () => ({ usePathname: () => "/perfil", useRouter: () => ({ push }) }));
vi.mock("../../lib/api", () => ({ apiFetch }));
vi.mock("../../lib/useConta", () => ({
  useConta: () => ({ nome: "Rádio Teste", role: "membro" }),
  limparContaCache,
}));
vi.mock("../../lib/useConfiguracaoInicial", () => ({ useConfiguracaoInicialCompleta: () => true }));
vi.mock("../NotificationBell", () => ({ default: () => null }));
vi.mock("../OnboardingTour", () => ({ default: () => null }));
vi.mock("../SuporteChat", () => ({ default: () => null }));

beforeEach(() => vi.clearAllMocks());

describe("navegação da conta", () => {
  it("mantém Ajuda, Perfil e Sair na navegação mobile de membros", async () => {
    render(<AppShell title="Perfil">Conteúdo</AppShell>);
    const nav = within(screen.getByRole("navigation", { name: "Navegação principal" }));
    expect(nav.getByRole("link", { name: "Ajuda" })).toHaveAttribute("href", "/ajuda");
    expect(nav.getByRole("link", { name: "Perfil" })).toHaveAttribute("aria-current", "page");
    expect(nav.queryByRole("link", { name: "Assinatura" })).not.toBeInTheDocument();
    expect(nav.queryByRole("link", { name: "Equipe" })).not.toBeInTheDocument();
    await userEvent.click(nav.getByRole("button", { name: "Sair" }));
    expect(apiFetch).toHaveBeenCalledWith("/auth/logout", { method: "POST" });
    expect(limparContaCache).toHaveBeenCalled();
    expect(push).toHaveBeenCalledWith("/login");
  });

  it("fecha o menu da conta com Escape e devolve o foco ao botão", async () => {
    render(<AppShell title="Perfil">Conteúdo</AppShell>);
    const button = screen.getByRole("button", { name: "Menu da conta" });
    await userEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
    await userEvent.keyboard("{Escape}");
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(button).toHaveFocus();
  });
});
