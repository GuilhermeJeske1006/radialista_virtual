"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "../lib/api";
import { useConfiguracaoInicialCompleta } from "../lib/useConfiguracaoInicial";

type StatusPlano = {
  plano: string;
  agentes_usados: number;
  agentes_limite: number;
  mensagens_usadas: number;
  mensagens_limite: number;
};

type SinalUpsell = { titulo: string; mensagem: string; tom: "estouro" | "alerta" };

// Espelha app/billing/upsell.py::calcular_sinal_upsell no backend (mesma ordem de prioridade:
// agentes cheios > mensagens estouradas > mensagens quase estourando) -- o job periodico
// (app/billing/alertar_upsell.py) manda notificacao/e-mail com a mesma regra, esse banner so'
// mostra o mesmo sinal em tempo real pra quem esta' com o painel aberto.
const LIMIAR_ALERTA_MENSAGENS = 0.8;

function calcularSinal(status: StatusPlano): SinalUpsell | null {
  if (status.agentes_usados >= status.agentes_limite) {
    return {
      titulo: "Seus radialistas bateram o limite do plano",
      tom: "estouro",
      mensagem: `Você já usa ${status.agentes_usados} de ${status.agentes_limite} agente(s) do plano ${status.plano}. Adicione um agente extra ou faça upgrade pra continuar crescendo.`,
    };
  }
  if (status.mensagens_usadas >= status.mensagens_limite) {
    return {
      titulo: "Seu plano estourou o limite de mensagens do mês",
      tom: "estouro",
      mensagem: `${status.mensagens_usadas} de ${status.mensagens_limite} mensagens usadas no plano ${status.plano}. Compre um excedente ou faça upgrade pra não deixar ouvinte sem resposta.`,
    };
  }
  if (status.mensagens_usadas >= status.mensagens_limite * LIMIAR_ALERTA_MENSAGENS) {
    return {
      titulo: "Seu plano está perto do limite de mensagens",
      tom: "alerta",
      mensagem: `${status.mensagens_usadas} de ${status.mensagens_limite} mensagens usadas no plano ${status.plano}. Considere um upgrade antes de estourar.`,
    };
  }
  return null;
}

/** Banner de upsell no fluxo do painel -- so' aparece pra conta com marca consolidada (radialista
 * pronto + programa ativo + WhatsApp conectado, ver useConfiguracaoInicial) e uso perto/acima do
 * limite do plano. Onboarding incompleto tem seu proprio aviso (checklist do dashboard); empurrar
 * upgrade antes disso e' ruido. */
export function UpsellBanner() {
  const completa = useConfiguracaoInicialCompleta();
  const [status, setStatus] = useState<StatusPlano | null>(null);

  useEffect(() => {
    if (!completa) return;
    apiFetch<StatusPlano>("/billing/status")
      .then(setStatus)
      .catch(() => {});
  }, [completa]);

  if (!completa || !status) return null;

  const sinal = calcularSinal(status);
  if (!sinal) return null;

  const cores = sinal.tom === "estouro" ? "border-rust/40 bg-rust/10" : "border-amber/40 bg-amber/10";
  const corTexto = sinal.tom === "estouro" ? "text-rust-text" : "text-amber-text";

  return (
    <div className={`flex items-start justify-between gap-4 rounded-2xl border ${cores} px-5 py-4 mb-6`}>
      <div>
        <p className="text-sm font-medium text-fg">{sinal.titulo}</p>
        <p className="text-sm text-fg/65 mt-0.5">{sinal.mensagem}</p>
      </div>
      <Link href="/billing" className={`shrink-0 text-sm font-medium ${corTexto} hover:opacity-80`}>
        Ver planos →
      </Link>
    </div>
  );
}
