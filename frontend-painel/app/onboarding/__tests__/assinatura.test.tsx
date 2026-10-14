import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  replace: vi.fn(),
  push: vi.fn(),
  api: vi.fn(),
  conta: null as Record<string, unknown> | null,
  ativou: true,
  recarregar: vi.fn(),
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: mocks.replace, push: mocks.push }) }));
vi.mock("../../../lib/api", async (importOriginal) => ({ ...(await importOriginal<object>()), apiFetch: mocks.api }));
vi.mock("../../../lib/useConta", () => ({
  useConta: () => mocks.conta,
  limparContaCache: vi.fn(),
  obterConta: () => (mocks.conta ? Promise.resolve(mocks.conta) : Promise.reject(new Error("rede"))),
  recarregarConta: () => mocks.recarregar(),
}));
vi.mock("../../../components/ThemeToggle", () => ({ default: () => null }));
vi.mock("../../../components/CheckoutModal", () => ({
  CheckoutPagamento: ({ onSuccess, rotuloBotao }: { onSuccess: () => void; rotuloBotao: string }) => <button onClick={onSuccess}>{rotuloBotao}</button>,
}));
vi.mock("../../../components/AssinaturaGate", () => ({
  ResumoFlex: () => null,
  aguardarAtivacao: () => Promise.resolve(mocks.ativou),
}));

import OnboardingAssinaturaPage from "../assinatura/page";

beforeEach(() => {
  vi.clearAllMocks();
  mocks.api.mockResolvedValue(undefined);
  mocks.ativou = true;
  mocks.conta = { role: "admin", plano_status: "trial" };
  window.history.replaceState(null, "", "/onboarding/assinatura");
});
afterEach(cleanup);

describe("/onboarding/assinatura", () => {
  it("cadastro sem pagamento: mostra a última etapa e segue para o onboarding ao assinar", async () => {
    render(<OnboardingAssinaturaPage />);
    expect(await screen.findByRole("heading", { name: "Ative o Locufy Flex" })).toBeInTheDocument();
    expect(screen.getByRole("listitem", { current: "step" })).toHaveTextContent("Assinatura");
    // sem menu do painel: a saída é assinar ou sair da conta
    expect(screen.queryByRole("link", { name: "Voltar ao painel" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Assinar e continuar" }));
    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith("/onboarding"));
  });

  it("volta do banco (3DS): confirma direto, sem pedir o cartão de novo", async () => {
    mocks.ativou = false;
    window.history.replaceState(null, "", "/onboarding/assinatura?payment_intent=pi_1&redirect_status=succeeded");
    render(<OnboardingAssinaturaPage />);
    expect(await screen.findByText("A confirmação do pagamento ainda não chegou.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Assinar e continuar" })).not.toBeInTheDocument();
    expect(window.location.search).toBe("");
  });

  it("banco recusou no 3DS: avisa e mostra o cartão de novo", async () => {
    window.history.replaceState(null, "", "/onboarding/assinatura?redirect_status=failed");
    render(<OnboardingAssinaturaPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("O banco não aprovou o pagamento");
    expect(screen.getByRole("button", { name: "Assinar e continuar" })).toBeInTheDocument();
  });

  it("cancelada: reativa e pode voltar ao painel", async () => {
    mocks.conta = { role: "admin", plano_status: "cancelado" };
    render(<OnboardingAssinaturaPage />);
    expect(await screen.findByRole("heading", { name: "Reative o Locufy Flex" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reativar assinatura" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Voltar ao painel" })).toHaveAttribute("href", "/dashboard");
    expect(screen.queryByRole("list", { name: "Etapas do cadastro" })).not.toBeInTheDocument();
  });

  it("membro da equipe não paga: pede para o administrador", async () => {
    mocks.conta = { role: "membro", plano_status: "trial" };
    render(<OnboardingAssinaturaPage />);
    expect(await screen.findByText(/Peça a quem administra a conta/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Assinar e continuar" })).not.toBeInTheDocument();
  });

  it("já assinada: vai para o próximo passo do onboarding", async () => {
    mocks.conta = { role: "admin", plano_status: "ativo" };
    render(<OnboardingAssinaturaPage />);
    await act(async () => {});
    expect(mocks.replace).toHaveBeenCalledWith("/onboarding");
  });

  it("cadastro não salvou o nome da rádio: avisa e, depois de assinar, leva ao painel para conferir", async () => {
    window.history.replaceState(null, "", "/onboarding/assinatura?dados=incompletos");
    render(<OnboardingAssinaturaPage />);
    expect(await screen.findByText(/o nome da rádio pode não ter sido salvo/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Assinar e continuar" }));
    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith("/dashboard?onboarding=incompleto"));
    expect(mocks.replace).not.toHaveBeenCalledWith("/onboarding");
  });

  it("falha ao carregar a conta: mostra o erro e deixa tentar de novo", async () => {
    mocks.conta = null;
    mocks.recarregar.mockResolvedValue(undefined);
    render(<OnboardingAssinaturaPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível carregar sua conta");
    await userEvent.click(screen.getByRole("button", { name: "Tentar de novo" }));
    expect(mocks.recarregar).toHaveBeenCalled();
  });

  it("sair da conta encerra a sessão", async () => {
    render(<OnboardingAssinaturaPage />);
    await userEvent.click(await screen.findByRole("button", { name: "Sair da conta" }));
    expect(mocks.api).toHaveBeenCalledWith("/auth/logout", { method: "POST" });
    expect(mocks.push).toHaveBeenCalledWith("/login");
  });
});
