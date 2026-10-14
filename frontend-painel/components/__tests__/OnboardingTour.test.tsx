import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ usePathname: () => "/dashboard" }));
vi.mock("../../lib/useConfiguracaoInicial", () => ({
  useConfiguracaoInicial: () => ({ radialistaPronto: true, programaAtivo: true, whatsappConectado: true, completa: true }),
}));
const estado = vi.hoisted(() => ({ conta: { role: "admin", plano_status: "ativo" } as Record<string, unknown> }));
vi.mock("../../lib/useConta", () => ({ useConta: () => estado.conta }));

import OnboardingTour from "../OnboardingTour";
import { CAPTURA_INSTALACAO_SCRIPT } from "../../lib/instalarApp";

beforeEach(() => {
  estado.conta = { role: "admin", plano_status: "ativo" };
  localStorage.clear();
  window.__locufyInstalar = null;
  vi.stubGlobal("matchMedia", (q: string) => ({ matches: false, media: q }));
  new Function(CAPTURA_INSTALACAO_SCRIPT)();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("passo do app instala direto do cartão, sem passar pela página do passo", async () => {
  const evento = Object.assign(new Event("beforeinstallprompt"), {
    prompt: vi.fn(() => Promise.resolve()), userChoice: Promise.resolve({ outcome: "accepted" }),
  });
  window.dispatchEvent(evento);
  render(<OnboardingTour />);

  expect(await screen.findByText("Instale o app e libere o som")).toBeTruthy();
  await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Instalar Locufy" })); });
  expect(evento.prompt).toHaveBeenCalledTimes(1);
  // instalado = passo feito neste aparelho -> cartao some
  expect(screen.queryByText("Instale o app e libere o som")).toBeNull();
});

it("sem oferta de instalação do navegador: leva pro passo a passo", async () => {
  render(<OnboardingTour />);
  const link = await screen.findByRole("link", { name: /Instalar e liberar som/ });
  expect(link.getAttribute("href")).toBe("/onboarding/app");
});

it("assinatura cancelada: o primeiro passo pendente é reativar", async () => {
  estado.conta = { role: "admin", plano_status: "cancelado" };
  render(<OnboardingTour />);
  expect(await screen.findByText("Ative sua assinatura")).toBeTruthy();
  expect(screen.getByText("Passo 1 de 5")).toBeTruthy();
  expect(screen.getByRole("link", { name: /Ativar assinatura/ }).getAttribute("href")).toBe("/onboarding/assinatura");
});
