import { beforeEach, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const api = vi.hoisted(() => vi.fn());
vi.mock("../../../lib/api", async (importOriginal) => ({ ...(await importOriginal<object>()), apiFetch: api }));
vi.mock("../../../lib/funnel", () => ({ captureCampaign: () => ({}), trackFunnel: vi.fn() }));
vi.mock("../../../components/ThemeToggle", () => ({ default: () => null }));

import RegisterPage from "../page";

beforeEach(() => {
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

it("cria a conta em dois passos, sem checkout, e leva ao primeiro radialista", async () => {
  render(<RegisterPage />);
  await userEvent.type(screen.getByLabelText("Seu nome"), "Ana");
  await userEvent.type(screen.getByLabelText("E-mail"), "ana@radio.com");
  await userEvent.type(screen.getByLabelText("Senha"), "12345678");
  await userEvent.type(screen.getByLabelText("Confirmar senha"), "12345678");
  await userEvent.click(screen.getByRole("button", { name: "Continuar" }));
  await userEvent.type(await screen.findByLabelText("Nome da rádio"), "Rádio Sintonia");
  expect(screen.getByText(/R\$\s69,90\/mês/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Criar conta" }));
  await waitFor(() => expect(window.location.href).toBe("/onboarding/locutor"));
  expect(api).toHaveBeenCalledWith("/auth/register", expect.objectContaining({ method: "POST" }));
  expect(api).not.toHaveBeenCalledWith("/billing/checkout", expect.anything());
});
