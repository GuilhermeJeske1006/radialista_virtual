import { beforeEach, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const api = vi.hoisted(() => vi.fn());
vi.mock("../../../lib/api", () => ({ apiFetch: api }));
vi.mock("../../../components/AppShell", () => ({ default: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }));
vi.mock("../../../components/ConsumoIACard", () => ({ default: () => null }));
vi.mock("../../../components/ModelosConsumo", () => ({ default: () => null }));
vi.mock("../../../components/TarifasModelos", () => ({ default: () => null }));
vi.mock("../../../components/CheckoutModal", () => ({ default: () => null }));

import BillingPage from "../page";

beforeEach(() => { api.mockReset(); });

it("status legível e botão de regularizar com estado de envio", async () => {
  let abrir: (v: { url: string }) => void = () => {};
  api.mockImplementation((path: string) => path === "/billing/status"
    ? Promise.resolve({ plano_status: "inadimplente" })
    : new Promise(r => { abrir = r; }));
  render(<BillingPage />);
  expect(await screen.findByText("Pagamento pendente")).toBeInTheDocument();
  expect(screen.queryByText("inadimplente")).not.toBeInTheDocument();
  expect(screen.getByText(/R\$\s69,90\/mês/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Regularizar pagamento" }));
  // Segundo clique não abre outra sessão do portal enquanto a primeira carrega.
  expect(screen.getByRole("button", { name: "Abrindo…" })).toBeDisabled();
  expect(api).toHaveBeenCalledTimes(2);
  abrir({ url: "about:blank" });
});

it("conta sem assinatura vê o botão de assinar", async () => {
  api.mockResolvedValue({ plano_status: "trial" });
  render(<BillingPage />);
  expect(await screen.findByRole("button", { name: "Assinar Locufy Flex" })).toBeInTheDocument();
  expect(screen.getByText("Aguardando assinatura")).toBeInTheDocument();
});
