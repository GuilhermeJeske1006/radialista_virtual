import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ sondar: vi.fn(), push: vi.fn(), replace: vi.fn(), configuracao: vi.fn() }));
vi.mock("../../../lib/autoplay", () => ({ sondarAutoplayComSom: mocks.sondar }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mocks.push, replace: mocks.replace }) }));
vi.mock("../../../components/AppShell", () => ({ default: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }));
vi.mock("../../../lib/useConfiguracaoInicial", () => ({ obterConfiguracaoInicial: mocks.configuracao }));

import OnboardingAppPage from "../app/page";
import OnboardingPage from "../page";
import { CAPTURA_INSTALACAO_SCRIPT } from "../../../lib/instalarApp";

let interagiu = false;

beforeEach(() => {
  vi.resetAllMocks();
  localStorage.clear();
  window.__locufyInstalar = null;
  interagiu = false;
  Object.defineProperty(navigator, "userActivation", { configurable: true, get: () => ({ hasBeenActive: interagiu }) });
  vi.stubGlobal("matchMedia", (q: string) => ({ matches: false, media: q }));
  new Function(CAPTURA_INSTALACAO_SCRIPT)();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  delete (navigator as { userActivation?: unknown }).userActivation;
});

describe("/onboarding/app", () => {
  it("som liberado sem clique: mostra que a rádio toca sozinha", async () => {
    mocks.sondar.mockResolvedValue(true);
    render(<OnboardingAppPage />);
    expect(await screen.findByText(/Som automático liberado neste navegador/)).toBeTruthy();
  });

  it("som bloqueado: avisa e oferece instalar", async () => {
    mocks.sondar.mockResolvedValue(false);
    const evento = Object.assign(new Event("beforeinstallprompt"), {
      prompt: vi.fn(() => Promise.resolve()), userChoice: Promise.resolve({ outcome: "accepted" }),
    });
    window.dispatchEvent(evento);
    render(<OnboardingAppPage />);

    expect(await screen.findByText(/Som automático bloqueado neste navegador/)).toBeTruthy();
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Instalar Locufy" })); });
    expect(evento.prompt).toHaveBeenCalled();
    // um clique: o navegador abre o app sozinho, a pagina so' confirma -- sem "Concluir"
    expect(screen.getByText(/O Locufy abriu numa janela própria, já no Ao Vivo/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Pular por enquanto" })).toBeNull();
    // instalar ja' conta o passo como feito neste aparelho
    expect(localStorage.getItem("locufy-app-configurado")).toBe("1");
  });

  it("página que já recebeu clique não testa (daria falso 'liberado') e pede pra recarregar", async () => {
    interagiu = true;
    render(<OnboardingAppPage />);
    expect(await screen.findByRole("button", { name: "Recarregar e testar" })).toBeTruthy();
    expect(mocks.sondar).not.toHaveBeenCalled();
  });

  it("Firefox: ensina a liberar a reprodução automática, sem instalar", async () => {
    mocks.sondar.mockResolvedValue(false);
    vi.spyOn(navigator, "userAgent", "get").mockReturnValue("Mozilla/5.0 Gecko/20100101 Firefox/130.0");
    render(<OnboardingAppPage />);
    expect(await screen.findByText("Libere a reprodução automática")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Já liberei" })).toBeTruthy();
  });

  it("aberto como app: tudo pronto, sem botão de instalar", async () => {
    vi.stubGlobal("matchMedia", (q: string) => ({ matches: q.includes("standalone"), media: q }));
    mocks.sondar.mockResolvedValue(true);
    render(<OnboardingAppPage />);
    expect(await screen.findByText(/Tudo pronto: você está no app Locufy/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Instalar Locufy" })).toBeNull();
  });

  it.each([["Já instalei", "/live"], ["Pular por enquanto", "/dashboard"]])(
    "'%s' marca o passo feito neste aparelho e vai pra %s",
    async (botao, destino) => {
      mocks.sondar.mockResolvedValue(false);
      render(<OnboardingAppPage />);
      fireEvent.click(await screen.findByRole("button", { name: botao }));
      expect(localStorage.getItem("locufy-app-configurado")).toBe("1");
      expect(mocks.push).toHaveBeenCalledWith(destino);
    },
  );
});

describe("/onboarding", () => {
  const pronto = { radialistaPronto: true, programaAtivo: true, whatsappConectado: true, completa: true };

  it("manda pro próximo passo pendente", async () => {
    mocks.configuracao.mockResolvedValue({ ...pronto, whatsappConectado: false, completa: false });
    render(<OnboardingPage />);
    await act(async () => {});
    expect(mocks.replace).toHaveBeenCalledWith("/conversas");
  });

  it("conta pronta mas app não configurado neste aparelho: vai pro passo do app", async () => {
    mocks.configuracao.mockResolvedValue(pronto);
    render(<OnboardingPage />);
    await act(async () => {});
    expect(mocks.replace).toHaveBeenCalledWith("/onboarding/app");
  });

  it("tudo pronto: vai pro painel", async () => {
    localStorage.setItem("locufy-app-configurado", "1");
    mocks.configuracao.mockResolvedValue(pronto);
    render(<OnboardingPage />);
    await act(async () => {});
    expect(mocks.replace).toHaveBeenCalledWith("/dashboard");
  });
});
