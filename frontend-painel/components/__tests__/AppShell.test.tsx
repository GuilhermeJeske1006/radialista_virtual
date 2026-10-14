import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AppShell from "../AppShell";

const { push, replace, apiFetch, limparContaCache, estado } = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
  apiFetch: vi.fn().mockResolvedValue(undefined),
  limparContaCache: vi.fn(),
  estado: { conta: { nome: "Rádio Teste", role: "membro" } as Record<string, unknown> },
}));
vi.mock("next/navigation", () => ({ usePathname: () => "/perfil", useRouter: () => ({ push, replace }) }));
vi.mock("../../lib/api", () => ({ apiFetch }));
vi.mock("../../lib/useConta", () => ({
  useConta: () => estado.conta,
  limparContaCache,
}));
vi.mock("../../lib/useConfiguracaoInicial", () => ({
  useConfiguracaoInicialCompleta: () => true,
  useConfiguracaoInicial: () => ({ radialistaPronto: true, programaAtivo: true, whatsappConectado: true, completa: true }),
}));
vi.mock("../NotificationBell", () => ({ default: () => null }));
vi.mock("../OnboardingTour", () => ({ default: () => null }));
vi.mock("../SuporteChat", () => ({ default: () => null }));

beforeEach(() => {
  vi.clearAllMocks();
  estado.conta = { nome: "Rádio Teste", role: "membro" };
});

describe("conta sem assinatura", () => {
  it("cadastro parou antes de pagar: manda para a assinatura e não mostra o painel", () => {
    estado.conta = { nome: "Ana", role: "admin", plano_status: "trial" };
    render(<AppShell title="Perfil">Tela da rádio</AppShell>);
    expect(replace).toHaveBeenCalledWith("/onboarding/assinatura");
    expect(screen.queryByText("Tela da rádio")).not.toBeInTheDocument();
  });

  it.each([
    ["cancelada", { plano_status: "cancelado" }],
    ["isenta de cobrança", { plano_status: "trial", cobranca_isenta: true }],
    ["ativa", { plano_status: "ativo" }],
  ])("conta %s entra no painel", (_, extra) => {
    estado.conta = { nome: "Ana", role: "admin", ...extra };
    render(<AppShell title="Perfil">Tela da rádio</AppShell>);
    expect(replace).not.toHaveBeenCalled();
    expect(screen.getByText("Tela da rádio")).toBeInTheDocument();
  });
});

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

  it("cabeçalho acende 'No ar' pelo horário da grade quando a tela não informa", async () => {
    apiFetch.mockImplementation((path: string) =>
      Promise.resolve(path === "/live/no-ar" ? { no_ar: true, radialista_id: 1, radialista_nome: "Marina", programa_id: 1, programa_nome: "Manhã" } : undefined)
    );
    render(<AppShell title="Perfil">Conteúdo</AppShell>);
    expect(await screen.findByText("No ar")).toBeInTheDocument();
    apiFetch.mockResolvedValue(undefined);
  });

  it("tela pode forçar o estado (ao vivo transmitindo)", () => {
    render(<AppShell title="Ao vivo" noAr>Conteúdo</AppShell>);
    expect(screen.getByText("No ar")).toBeInTheDocument();
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
