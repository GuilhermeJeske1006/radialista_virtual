import { beforeEach, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const api = vi.hoisted(() => vi.fn());
vi.mock("../../lib/api", async (importOriginal) => ({ ...(await importOriginal<object>()), apiFetch: api }));
vi.mock("@stripe/stripe-js", () => ({ loadStripe: () => Promise.resolve(null) }));
vi.mock("@stripe/react-stripe-js", () => ({
  Elements: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  PaymentElement: () => <div>campo do cartão</div>,
  useStripe: () => null,
  useElements: () => null,
}));

import { CheckoutPagamento } from "../CheckoutModal";

beforeEach(() => api.mockReset());

it("falha ao iniciar o pagamento na página: mostra o erro e deixa tentar de novo", async () => {
  const { ApiError } = await import("../../lib/api");
  let checkouts = 0;
  api.mockImplementation((path: string) => {
    if (path === "/billing/cartao") return Promise.resolve({ cartao: null });
    checkouts += 1;
    return checkouts === 1 ? Promise.reject(new ApiError(503, "Pagamento indisponível")) : Promise.resolve({ client_secret: "pi_secret" });
  });
  render(<CheckoutPagamento endpoint="/billing/checkout" body={{ plano_id: "flex" }} onSuccess={vi.fn()} rotuloBotao="Assinar e continuar" />);

  expect(await screen.findByRole("alert")).toHaveTextContent("Pagamento indisponível");
  await userEvent.click(screen.getByRole("button", { name: "Tentar de novo" }));
  expect(await screen.findByText("campo do cartão")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Assinar e continuar" })).toBeInTheDocument();
  expect(checkouts).toBe(2);
});
