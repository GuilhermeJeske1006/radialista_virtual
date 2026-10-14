"use client";

import { useEffect, useRef, useState } from "react";
import { CheckoutPagamento } from "./CheckoutModal";
import { ResumoFlex, aguardarAtivacao } from "./AssinaturaGate";
import { LocufySpin } from "./LocufyLogo";

// Volta do banco (3DS com redirecionamento) cai em /onboarding/assinatura, que confirma o pagamento.
const RETORNO_DO_BANCO = "/onboarding/assinatura";

type Etapa = "pagamento" | "confirmando" | "pendente";

/** Passo de assinatura do cadastro e de /onboarding/assinatura: resumo do Locufy Flex, cartão e a
 * espera da confirmação do pagamento. Com `confirmando`, já começa esperando (volta do banco). */
export default function AtivarAssinatura({
  onAtivada,
  confirmando = false,
  rotuloBotao = "Assinar e continuar",
}: {
  onAtivada: () => void;
  confirmando?: boolean;
  rotuloBotao?: string;
}) {
  const [etapa, setEtapa] = useState<Etapa>(confirmando ? "confirmando" : "pagamento");
  const iniciou = useRef(false);

  async function confirmar() {
    setEtapa("confirmando");
    if (await aguardarAtivacao()) onAtivada();
    else setEtapa("pendente");
  }

  useEffect(() => {
    if (!confirmando || iniciou.current) return;
    iniciou.current = true;
    void confirmar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [confirmando]);

  if (etapa === "confirmando") {
    return (
      <p role="status" className="flex items-center gap-2 text-sm text-fg/80">
        <LocufySpin size={16} /> Confirmando o pagamento…
      </p>
    );
  }

  if (etapa === "pendente") {
    return (
      <div role="status" className="rounded-xl border border-border-strong bg-bg p-4 text-sm">
        <p className="font-semibold text-fg">A confirmação do pagamento ainda não chegou.</p>
        <p className="mt-1 text-fg/80">Costuma levar alguns segundos. Não pague de novo: verifique daqui a pouco.</p>
        <button
          type="button"
          onClick={() => void confirmar()}
          className="mt-4 rounded-xl bg-brand-500 px-4 py-2.5 text-sm font-medium text-on-brand hover:bg-brand-600"
        >
          Verificar de novo
        </button>
      </div>
    );
  }

  return (
    <CheckoutPagamento
      endpoint="/billing/checkout"
      body={{ plano_id: "flex" }}
      resumo={<ResumoFlex />}
      returnUrl={RETORNO_DO_BANCO}
      rotuloBotao={rotuloBotao}
      onSuccess={() => void confirmar()}
    />
  );
}
