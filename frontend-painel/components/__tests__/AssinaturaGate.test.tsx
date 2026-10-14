import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Conta } from "../../lib/types";

const estado = vi.hoisted(() => ({ conta: null as Conta | null, buscada: null as Conta | null }));
const recarregar = vi.hoisted(() => vi.fn());
const api = vi.hoisted(() => vi.fn());
vi.mock("../../lib/api", () => ({ apiFetch: api }));
vi.mock("../../lib/useConta", () => ({ useConta: () => estado.conta, recarregarConta: () => recarregar() }));
vi.mock("../CheckoutModal", () => ({
  default: ({ titulo }: { titulo?: string }) => <div role="dialog" aria-label={titulo} />,
}));

import { aguardarAtivacao, useExigirAssinatura } from "../AssinaturaGate";
import { precisaAssinar } from "../../lib/assinatura";

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

describe("aguardarAtivacao", () => {
  beforeEach(() => { api.mockReset(); recarregar.mockReset(); });

  it("só busca a conta quando o Stripe confirma o pagamento", async () => {
    api.mockResolvedValueOnce({ plano_status: "trial" }).mockResolvedValueOnce({ plano_status: "ativo" });
    recarregar.mockResolvedValue({ ...base, plano_status: "ativo" });
    expect(await aguardarAtivacao(3, 0)).toBe(true);
    expect(api).toHaveBeenCalledTimes(2);
    expect(api).toHaveBeenCalledWith("/billing/confirmar", { method: "POST" });
    expect(recarregar).toHaveBeenCalledTimes(1);
  });

  it("sem confirmação ao fim das tentativas: devolve false", async () => {
    api.mockResolvedValue({ plano_status: "trial" });
    expect(await aguardarAtivacao(3, 0)).toBe(false);
    expect(api).toHaveBeenCalledTimes(3);
    expect(recarregar).not.toHaveBeenCalled();
  });

  it("/confirmar indisponível: decide pela conta", async () => {
    api.mockRejectedValue(new Error("rede"));
    recarregar.mockResolvedValue({ ...base, plano_status: "ativo" });
    expect(await aguardarAtivacao(3, 0)).toBe(true);
  });
});

describe("useExigirAssinatura", () => {
  beforeEach(() => {
    estado.conta = null;
    estado.buscada = null;
    recarregar.mockImplementation(() => Promise.resolve(estado.buscada));
  });

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
