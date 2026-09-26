"use client";

import { useState } from "react";
import Link from "next/link";
import CheckoutModal from "./CheckoutModal";
import Modal from "./Modal";
import { Conta } from "../lib/types";
import { recarregarConta, useConta } from "../lib/useConta";
import { PRECO_MENSAL_FLEX, formatarReais } from "../lib/planos";

/** Conta criada no cadastro fica em "trial" até pagar: configura tudo, mas geração com IA e ao
 * vivo pedem assinatura ativa. Conta isenta de cobrança gera sem assinatura. */
export function precisaAssinar(conta: Conta | null): boolean {
  if (!conta || conta.cobranca_isenta) return false;
  return conta.plano_status === "trial" || conta.plano_status === "cancelado";
}

// O webhook do Stripe confirma a assinatura alguns segundos depois do pagamento.
async function aguardarAtivacao(tentativas = 6, esperaMs = 1500): Promise<void> {
  for (let i = 0; i < tentativas; i++) {
    const conta = await recarregarConta().catch(() => null);
    if (conta && !precisaAssinar(conta)) return;
    await new Promise((r) => setTimeout(r, esperaMs));
  }
}

export function ResumoFlex() {
  return (
    <div className="mb-4 rounded-xl border border-border-strong bg-bg p-4 text-sm">
      <p className="font-semibold text-fg">Locufy Flex</p>
      <p className="mt-1 text-fg/80">
        <span className="font-semibold text-fg tabular-nums">R$ {formatarReais(PRECO_MENSAL_FLEX)}/mês</span> + uso de IA
        cobrado no fim do ciclo.
      </p>
      <p className="mt-1 text-fg/65">
        Você define um limite financeiro mensal em Assinatura; ao atingir, novas gerações pausam. Reproduzir áudio
        pronto não gera cobrança.
      </p>
    </div>
  );
}

/** Antes de uma ação que gera com IA: sem assinatura, abre o checkout e só executa a ação depois
 * do pagamento. Com assinatura (ou conta isenta), executa direto. */
export function useExigirAssinatura() {
  const conta = useConta();
  const [acaoPendente, setAcaoPendente] = useState<(() => void) | null>(null);

  // Conta ainda carregando: busca antes de decidir, senão um clique rápido passaria sem checkout.
  async function exigir(acao: () => void) {
    const atual = conta ?? (await recarregarConta().catch(() => null));
    if (precisaAssinar(atual)) setAcaoPendente(() => acao);
    else acao();
  }

  const modal = acaoPendente ? (
    <CheckoutModal
      open
      titulo="Ative o Locufy Flex para gerar"
      resumo={<ResumoFlex />}
      endpoint="/billing/checkout"
      body={{ plano_id: "flex" }}
      onClose={() => setAcaoPendente(null)}
      onSuccess={async () => {
        const acao = acaoPendente;
        setAcaoPendente(null);
        await aguardarAtivacao();
        acao();
      }}
    />
  ) : null;

  return { exigir, modal, precisa: precisaAssinar(conta) };
}

/** Resposta 402 do backend: assinatura inativa (abre checkout) ou limite financeiro atingido
 * (leva ao limite em Assinatura). */
export function AvisoPagamento({ mensagem, onClose, onAssinado }: { mensagem: string; onClose: () => void; onAssinado?: () => void }) {
  const [checkout, setCheckout] = useState(false);
  const assinatura = /assinatura/i.test(mensagem);
  if (checkout) {
    return (
      <CheckoutModal
        open
        titulo="Ative o Locufy Flex"
        resumo={<ResumoFlex />}
        endpoint="/billing/checkout"
        body={{ plano_id: "flex" }}
        onClose={() => setCheckout(false)}
        onSuccess={async () => {
          setCheckout(false);
          await aguardarAtivacao();
          onClose();
          onAssinado?.();
        }}
      />
    );
  }
  return (
    <Modal open onClose={onClose} title={assinatura ? "Assinatura necessária" : "Limite financeiro atingido"} maxWidthClassName="max-w-sm">
      <p className="text-sm text-fg/80">{mensagem}</p>
      <div className="mt-5 flex flex-wrap justify-end gap-3">
        <button type="button" onClick={onClose} className="rounded-xl px-4 py-2.5 text-sm font-medium text-fg/65 hover:text-fg">
          Fechar
        </button>
        {assinatura ? (
          <button
            type="button"
            onClick={() => setCheckout(true)}
            className="rounded-xl bg-brand-500 px-4 py-2.5 text-sm font-medium text-on-brand hover:bg-brand-600"
          >
            Ativar assinatura
          </button>
        ) : (
          <Link href="/billing#limite" className="rounded-xl bg-brand-500 px-4 py-2.5 text-sm font-medium text-on-brand hover:bg-brand-600">
            Ajustar limite
          </Link>
        )}
      </div>
    </Modal>
  );
}
