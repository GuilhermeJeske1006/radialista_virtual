"use client";

import { useEffect, useState } from "react";
import { loadStripe, StripeElementsOptions } from "@stripe/stripe-js";
import { Elements, PaymentElement, useElements, useStripe } from "@stripe/react-stripe-js";
import Modal from "./Modal";
import { apiFetch, ApiError } from "../lib/api";
import { LocufySpin } from "./LocufyLogo";

const stripePromise = loadStripe(process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY || "");

// Elements roda o <PaymentElement> num iframe cross-origin, que nao enxerga var(--x) da
// nossa pagina -- precisa de valores literais resolvidos em runtime pra combinar com o
// tema (claro/escuro) ativo no momento em que o modal abre.
function resolverVariaveisDoTema() {
  const raiz = getComputedStyle(document.documentElement);
  const cor = (nome: string) => raiz.getPropertyValue(nome).trim();
  return {
    colorPrimary: cor("--color-amber"),
    colorBackground: cor("--color-surface"),
    colorText: cor("--color-fg"),
    colorDanger: cor("--color-rust"),
    borderRadius: "8px",
  };
}

function Formulario({ onSuccess }: { onSuccess: () => void }) {
  const stripe = useStripe();
  const elements = useElements();
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState("");

  async function pagar(e: React.FormEvent) {
    e.preventDefault();
    if (!stripe || !elements) return;
    setEnviando(true);
    setErro("");

    const { error, paymentIntent } = await stripe.confirmPayment({
      elements,
      confirmParams: { return_url: window.location.href },
      redirect: "if_required",
    });

    if (error) {
      setErro(error.message || "Erro ao processar pagamento");
      setEnviando(false);
      return;
    }
    if (paymentIntent && (paymentIntent.status === "succeeded" || paymentIntent.status === "processing")) {
      onSuccess();
    } else {
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={pagar}>
      <PaymentElement options={{ layout: "tabs" }} />
      {erro && <p className="mt-3 text-sm text-rust-text">{erro}</p>}
      <button
        type="submit"
        disabled={!stripe || enviando}
        className="mt-5 flex w-full items-center justify-center gap-2 rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-ink hover:bg-brand-600 disabled:opacity-60 disabled:cursor-not-allowed"
      >
        {enviando ? (
          <>
            <LocufySpin size={14} /> Processando...
          </>
        ) : (
          "Confirmar pagamento"
        )}
      </button>
    </form>
  );
}

type CheckoutModalProps = {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
  // Endpoint de billing que cria a assinatura/payment intent e devolve { client_secret }
  // (ex.: /billing/checkout, /billing/agentes-extras/checkout, /billing/excedente-mensagens/checkout).
  endpoint: string;
  body?: Record<string, unknown>;
};

// Checkout transparente de verdade: formulario proprio (Tailwind, LocufySpin, texto de
// erro no mesmo padrao do resto do app) -- so' o campo de cartao em si vem do Stripe
// (<PaymentElement>, obrigatorio por PCI compliance), estilizado via `appearance` pra
// combinar com o tema. O client_secret vem de uma Subscription/PaymentIntent criada direto
// via API (ver stripe_client.py), nao de uma Checkout Session -- sem UI pronta do Stripe.
export default function CheckoutModal({ open, onClose, onSuccess, endpoint, body }: CheckoutModalProps) {
  const [clientSecret, setClientSecret] = useState<string | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    if (!open) return;
    setClientSecret(null);
    setErro("");
    apiFetch<{ client_secret: string }>(endpoint, { method: "POST", body: JSON.stringify(body ?? {}) })
      .then((r) => setClientSecret(r.client_secret))
      .catch((err) => setErro(err instanceof ApiError ? err.message : "Erro ao iniciar pagamento"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, endpoint, JSON.stringify(body ?? {})]);

  const tema = typeof document !== "undefined" && document.documentElement.getAttribute("data-theme") === "light" ? "stripe" : "night";
  const options: StripeElementsOptions | undefined = clientSecret
    ? { clientSecret, appearance: { theme: tema, variables: resolverVariaveisDoTema() } }
    : undefined;

  return (
    <Modal open={open} onClose={onClose} title="Pagamento" maxWidthClassName="max-w-lg">
      {erro && <p className="mb-3 text-sm text-rust-text">{erro}</p>}
      {!clientSecret && !erro && (
        <p className="flex items-center gap-2 text-sm text-fg/65">
          <LocufySpin size={16} /> Carregando...
        </p>
      )}
      {clientSecret && options && (
        <Elements key={tema} stripe={stripePromise} options={options}>
          <Formulario onSuccess={onSuccess} />
        </Elements>
      )}
    </Modal>
  );
}
