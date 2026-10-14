import { beforeEach, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const api = vi.hoisted(() => vi.fn());
vi.mock("../../../lib/api", async (importOriginal) => ({ ...(await importOriginal<object>()), apiFetch: api }));
const funil = vi.hoisted(() => ({ trackFunnel: vi.fn() }));
vi.mock("../../../lib/funnel", () => ({ captureCampaign: () => ({}), trackFunnel: funil.trackFunnel }));
vi.mock("../../../components/ThemeToggle", () => ({ default: () => null }));

import RegisterPage from "../page";

beforeEach(() => {
  funil.trackFunnel.mockReset();
  api.mockReset();
  api.mockImplementation((path: string) => Promise.resolve(path === "/config/radialistas" ? [{ id: 3 }] : {}));
  Object.defineProperty(window, "location", { value: { ...window.location, href: "http://localhost/register", search: "" }, writable: true });
});

it("erro de campo aparece só junto do campo, sem repetir no rodapé", async () => {
  render(<RegisterPage />);
  await userEvent.click(screen.getByRole("button", { name: "Continuar" }));
  expect(screen.getByText("Preencha seu nome")).toBeInTheDocument();
  expect(screen.getAllByText("Preencha seu nome")).toHaveLength(1);
});

async function criarConta() {
  render(<RegisterPage />);
  await userEvent.type(screen.getByLabelText("Seu nome"), "Ana");
  await userEvent.type(screen.getByLabelText("E-mail"), "ana@radio.com");
  await userEvent.type(screen.getByLabelText("Senha"), "12345678");
  await userEvent.type(screen.getByLabelText("Confirmar senha"), "12345678");
  await userEvent.click(screen.getByRole("button", { name: "Continuar" }));
  await userEvent.type(await screen.findByLabelText("Nome da rádio"), "Rádio Sintonia");
  expect(screen.getByText(/R\$\s69,90\/mês/)).toBeInTheDocument();
  expect(screen.getByRole("listitem", { current: "step" })).toHaveTextContent("Sua rádio");
  await userEvent.click(screen.getByRole("button", { name: "Criar conta" }));
}

it("cria a conta e segue para o passo 3, a assinatura", async () => {
  await criarConta();
  await waitFor(() => expect(window.location.href).toBe("/onboarding/assinatura"));
  expect(api).toHaveBeenCalledWith("/auth/register", expect.objectContaining({ method: "POST" }));
  expect(funil.trackFunnel).toHaveBeenCalledWith("register_checkout_step", { plano: "flex" });
  // o pagamento é na página do passo 3, não aqui
  expect(api).not.toHaveBeenCalledWith("/billing/checkout", expect.anything());
});

it("nome da rádio não salvou: segue para a assinatura avisando", async () => {
  api.mockImplementation((path: string) => (path === "/config/radio" ? Promise.reject(new Error("falhou")) : Promise.resolve({})));
  await criarConta();
  await waitFor(() => expect(window.location.href).toBe("/onboarding/assinatura?dados=incompletos"));
});

it("e-mail já cadastrado: fica no passo da rádio com o erro, sem ir para a assinatura", async () => {
  const { ApiError } = await import("../../../lib/api");
  api.mockImplementation((path: string) => (path === "/auth/register" ? Promise.reject(new ApiError(400, "E-mail ja cadastrado")) : Promise.resolve({})));
  await criarConta();
  expect(await screen.findByRole("alert")).toHaveTextContent("E-mail ja cadastrado");
  expect(window.location.href).toBe("http://localhost/register");
  expect(funil.trackFunnel).not.toHaveBeenCalledWith("register_checkout_step", expect.anything());
});
