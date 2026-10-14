"use client";

import { useState } from "react";
import CheckoutModal from "./CheckoutModal";
import { ResumoFlex } from "./AssinaturaGate";
import { precisaAssinar } from "../lib/assinatura";
import { recarregarConta, useConta } from "../lib/useConta";
import { PRECO_MENSAL_FLEX, formatarReais } from "../lib/planos";

/** Assinatura cancelada: diz o que falta para gerar com IA e ir ao ar, com o checkout a um clique.
 * Conta que nunca pagou nem chega aqui -- o AppShell manda para /onboarding/assinatura. */
export default function AssinaturaPendenteAviso() {
  const conta = useConta();
  const [checkout, setCheckout] = useState(false);
  if (!precisaAssinar(conta)) return null;
  const cancelada = conta?.plano_status === "cancelado";

  return (
    <div role="status" className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-3xl border border-acento-claro/40 bg-acento/10 px-5 py-4">
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-fg">
          {cancelada ? "Sua assinatura foi cancelada." : "Falta ativar a assinatura."}
        </p>
        <p className="mt-0.5 text-sm text-fg/80">
          Para gerar com IA e colocar a rádio no ar, ative o Locufy Flex: R$ {formatarReais(PRECO_MENSAL_FLEX)}/mês + uso,
          com limite financeiro definido por você.
        </p>
      </div>
      <button
        type="button"
        onClick={() => setCheckout(true)}
        className="shrink-0 rounded-xl bg-brand-500 px-4 py-2.5 text-sm font-medium text-on-brand hover:bg-brand-600"
      >
        {cancelada ? "Reativar assinatura" : "Ativar assinatura"}
      </button>
      {checkout && (
        <CheckoutModal
          open
          titulo="Ative o Locufy Flex"
          resumo={<ResumoFlex />}
          endpoint="/billing/checkout"
          body={{ plano_id: "flex" }}
          onClose={() => setCheckout(false)}
          onSuccess={() => {
            setCheckout(false);
            void recarregarConta();
          }}
        />
      )}
    </div>
  );
}
