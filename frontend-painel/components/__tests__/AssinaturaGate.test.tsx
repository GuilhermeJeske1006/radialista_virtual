import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Conta } from "../../lib/types";

const estado = vi.hoisted(() => ({ conta: null as Conta | null, buscada: null as Conta | null }));
vi.mock("../../lib/useConta", () => ({ useConta: () => estado.conta, recarregarConta: () => Promise.resolve(estado.buscada) }));
vi.mock("../CheckoutModal", () => ({
  default: ({ titulo }: { titulo?: string }) => <div role="dialog" aria-label={titulo} />,
}));

import { precisaAssinar, useExigirAssinatura } from "../AssinaturaGate";

const base: Conta = { id: 1, nome: "Ana", email: "a@b.c", role: "admin", plano_status: "ativo", plano: "flex", criado_em: "", tem_radio_config: true };

function Gerar({ acao }: { acao: () => void }) {
  const { exigir, modal } = useExigirAssinatura();
  return (
    <>
      <button onClick={() => exigir(acao)}>Gerar</button>
      {modal}
    </>
  );
}

describe("precisaAssinar", () => {
  it("pede assinatura só para conta nova ou cancelada, nunca para isenta", () => {
    expect(precisaAssinar({ ...base, plano_status: "trial" })).toBe(true);
    expect(precisaAssinar({ ...base, plano_status: "cancelado" })).toBe(true);
    expect(precisaAssinar({ ...base, plano_status: "ativo" })).toBe(false);
    expect(precisaAssinar({ ...base, plano_status: "inadimplente" })).toBe(false);
    expect(precisaAssinar({ ...base, plano_status: "trial", cobranca_isenta: true })).toBe(false);
    expect(precisaAssinar(null)).toBe(false);
  });
});

describe("useExigirAssinatura", () => {
  beforeEach(() => { estado.conta = null; estado.buscada = null; });

  it("clique antes de a conta carregar ainda passa pelo checkout", async () => {
    estado.buscada = { ...base, plano_status: "trial" };
    const acao = vi.fn();
    render(<Gerar acao={acao} />);
    await userEvent.click(screen.getByRole("button", { name: "Gerar" }));
    expect(await screen.findByRole("dialog", { name: "Ative o Locufy Flex para gerar" })).toBeInTheDocument();
    expect(acao).not.toHaveBeenCalled();
  });

  it("conta sem assinatura abre o checkout em vez de gerar", async () => {
    estado.conta = { ...base, plano_status: "trial" };
    const acao = vi.fn();
    render(<Gerar acao={acao} />);
    await userEvent.click(screen.getByRole("button", { name: "Gerar" }));
    expect(await screen.findByRole("dialog", { name: "Ative o Locufy Flex para gerar" })).toBeInTheDocument();
    expect(acao).not.toHaveBeenCalled();
  });

  it("conta ativa gera direto", async () => {
    estado.conta = base;
    const acao = vi.fn();
    render(<Gerar acao={acao} />);
    await userEvent.click(screen.getByRole("button", { name: "Gerar" }));
    await waitFor(() => expect(acao).toHaveBeenCalledTimes(1));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
