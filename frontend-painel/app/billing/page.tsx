"use client";
import { useEffect, useState } from "react";
import AppShell from "../../components/AppShell";
import CheckoutModal from "../../components/CheckoutModal";
import ConsumoIACard from "../../components/ConsumoIACard";
import ModelosConsumo from "../../components/ModelosConsumo";
import TarifasModelos from "../../components/TarifasModelos";
import { apiFetch } from "../../lib/api";
import { reais } from "../../lib/combinacoes";
import { rotuloStatusAssinatura } from "../../lib/rotulosConsumo";

const MENSALIDADE_BRL = 69.9;
const BOTAO = "rounded-xl bg-brand-500 px-4 py-2.5 text-sm font-medium text-on-brand hover:bg-brand-600 disabled:opacity-60 disabled:cursor-not-allowed";
const BOTAO_SECUNDARIO = "rounded-xl border border-border-strong px-4 py-2.5 text-sm font-medium text-fg hover:bg-fg/5 disabled:opacity-60 disabled:cursor-not-allowed";

export default function BillingPage() {
  const [status, setStatus] = useState("");
  const [checkout, setCheckout] = useState(false);
  const [abrindoPortal, setAbrindoPortal] = useState(false);
  const [erro, setErro] = useState("");
  function atualizar() {
    apiFetch<{ plano_status: string }>("/billing/status")
      .then(s => setStatus(s.plano_status))
      .catch(() => setErro("Não foi possível carregar a assinatura. Atualize a página para tentar de novo."));
  }
  useEffect(atualizar, []);
  async function portal() {
    setAbrindoPortal(true); setErro("");
    try { const { url } = await apiFetch<{ url: string }>("/billing/portal", { method: "POST" }); window.location.href = url; }
    catch (e) { setErro(e instanceof Error ? e.message : "Não foi possível abrir o pagamento. Tente novamente."); setAbrindoPortal(false); }
  }
  const pendente = status === "inadimplente";
  return <AppShell title="Assinatura e consumo" maxWidthClassName="max-w-6xl"><div className="space-y-6">
    <section className="bg-surface rounded-3xl border border-border-strong shadow-theme-xs p-6" aria-labelledby="assinatura-titulo">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="assinatura-titulo" className="font-display text-lg font-bold text-fg">Locufy Flex</h2>
          <p className="mt-1 text-xl font-bold text-fg tabular-nums">{reais(MENSALIDADE_BRL)}/mês <span className="text-sm font-medium text-fg/65">+ uso pós-pago</span></p>
        </div>
        <p className={`rounded-full px-3 py-1 text-xs font-medium ${pendente ? "bg-laranja/15 text-laranja" : "bg-fg/5 text-fg/80"}`} role="status">
          {status ? rotuloStatusAssinatura(status) : "Carregando…"}
        </p>
      </div>
      <p className="mt-3 text-sm text-fg/80">WhatsApp completo, programas, vozes e vinhetas. Sem franquia ou pacotes de mensagens. O preço de cada processamento é o custo de referência das unidades medidas, convertido pelo câmbio da tarifa, com acréscimo de 100%.</p>
      <p className="mt-2 text-sm text-fg/65">Primeira mensalidade na adesão. Na renovação: mensalidade do próximo período + consumo do período encerrado. Sem consumo, apenas {reais(MENSALIDADE_BRL)}.</p>
      <div className="mt-4">
        {(status === "trial" || status === "cancelado")
          ? <button type="button" className={BOTAO} onClick={() => setCheckout(true)}>Assinar Locufy Flex</button>
          : status && <button type="button" className={pendente ? BOTAO : BOTAO_SECUNDARIO} disabled={abrindoPortal} onClick={() => void portal()}>
            {abrindoPortal ? "Abrindo…" : pendente ? "Regularizar pagamento" : "Gerenciar pagamento"}
          </button>}
      </div>
      {erro && <p role="alert" className="mt-3 text-sm text-laranja">{erro}</p>}
    </section>
    <ModelosConsumo />
    <ConsumoIACard plano="flex" />
    <TarifasModelos />
    {checkout && <CheckoutModal open endpoint="/billing/checkout" body={{ plano_id: "flex" }} onClose={() => setCheckout(false)} onSuccess={() => { setCheckout(false); atualizar(); }} />}
  </div></AppShell>;
}
