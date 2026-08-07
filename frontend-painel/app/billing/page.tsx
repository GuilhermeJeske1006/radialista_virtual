"use client";

import { useEffect, useState } from "react";
import AppShell from "../../components/AppShell";
import { apiFetch, ApiError } from "../../lib/api";
import { OndaLed, OndaSpin } from "../../components/OndaLogo";
import { PLANOS, PRECO_AGENTE_ADICIONAL, PRECO_EXCEDENTE_1000_MSG, formatarReais } from "../../lib/planos";

type StatusPlano = {
  plano_status: string;
  plano: string;
  agentes_usados: number;
  agentes_limite: number;
  mensagens_usadas: number;
  mensagens_limite: number;
};

export default function BillingPage() {
  const [statusPlano, setStatusPlano] = useState<StatusPlano | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [carregandoId, setCarregandoId] = useState<string | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    apiFetch<StatusPlano>("/billing/status")
      .then(setStatusPlano)
      .catch((err) => setErro(err instanceof ApiError ? err.message : "Erro ao carregar plano"))
      .finally(() => setCarregando(false));
  }, []);

  async function assinar(planoId: string) {
    setErro("");
    setCarregandoId(planoId);
    try {
      const { url } = await apiFetch<{ url: string }>("/billing/checkout", { method: "POST" });
      window.location.href = url;
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao iniciar assinatura");
      setCarregandoId(null);
    }
  }

  const ativo = statusPlano?.plano_status === "ativo";
  const planoAtual = PLANOS.find((p) => p.id === statusPlano?.plano);

  return (
    <AppShell title="Assinatura" maxWidthClassName="max-w-6xl">
      <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6 mb-8 max-w-lg">
        <h2 className="font-display text-base font-bold text-fg mb-4">Plano atual</h2>
        {carregando ? (
          <p className="flex items-center gap-2 text-sm text-fg/55">
            <OndaSpin size={16} /> Carregando...
          </p>
        ) : statusPlano ? (
          <>
            <div className="flex items-center gap-2 mb-5">
              <span className="text-sm text-fg/65">Status:</span>
              <span
                className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${
                  ativo ? "bg-teal/10 text-teal" : "bg-amber/10 text-amber"
                }`}
              >
                <OndaLed color={ativo ? "teal" : "amber"} pulse={false} />
                {statusPlano.plano_status}
              </span>
              {planoAtual && (
                <span className="text-sm text-fg/45">— {planoAtual.nome}</span>
              )}
            </div>

            <BarraUso
              rotulo="Agentes de WhatsApp"
              usado={statusPlano.agentes_usados}
              limite={statusPlano.agentes_limite}
            />
            <BarraUso
              rotulo="Mensagens este mês"
              usado={statusPlano.mensagens_usadas}
              limite={statusPlano.mensagens_limite}
              className="mt-4"
            />
          </>
        ) : null}
      </div>

      <div className="mb-8 max-w-2xl">
        <h2 className="font-display text-base font-bold text-fg mb-2">
          {ativo ? "Trocar de plano" : "Escolha seu plano"}
        </h2>
        <p className="text-sm text-fg/55">
          Todos os planos incluem os mesmos agentes de IA (comercial, qualificação, agendamento,
          suporte, pós-venda e mais), sempre atendendo pelo único número de WhatsApp da sua rádio —
          o que muda é quantos agentes você pode rodar ao mesmo tempo.
        </p>
      </div>

      {erro && <p className="text-sm text-rust mb-4">{erro}</p>}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {PLANOS.map((plano) => (
          <div
            key={plano.id}
            className={`relative flex flex-col rounded-2xl border p-6 shadow-theme-xs ${
              plano.destaque
                ? "bg-surface border-amber/50 ring-1 ring-amber/30"
                : "bg-surface border-border-strong"
            }`}
          >
            {plano.destaque && (
              <span className="absolute -top-3 left-6 rounded-full bg-brand-500 px-2.5 py-0.5 text-[11px] font-semibold text-ink">
                Mais escolhido
              </span>
            )}

            <h2 className="font-display text-base font-bold text-fg">{plano.nome}</h2>
            <p className="text-xs text-fg/55 mt-1 mb-5">{plano.descricao}</p>

            <div className="mb-5">
              <span className="font-display text-3xl font-bold text-fg">
                R$ {formatarReais(plano.preco)}
              </span>
              <span className="text-sm text-fg/45">/mês</span>
            </div>

            <ul className="space-y-2.5 mb-6 flex-1">
              <Feature texto={`${plano.agentes} ${plano.agentes === 1 ? "agente" : "agentes"} de IA inclusos`} />
              <Feature texto={`${plano.mensagens.toLocaleString("pt-BR")} mensagens/mês`} />
              <Feature texto="Respostas automáticas com IA" />
              <Feature texto="Encaminhamento pra atendimento humano" />
            </ul>

            <button
              onClick={() => assinar(plano.id)}
              disabled={carregandoId === plano.id}
              className={`flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium disabled:opacity-60 disabled:cursor-not-allowed ${
                plano.destaque
                  ? "bg-brand-500 text-ink hover:bg-brand-600"
                  : "bg-paper/10 text-fg hover:bg-paper/15"
              }`}
            >
              {carregandoId === plano.id ? (
                <>
                  <OndaSpin size={14} /> Redirecionando...
                </>
              ) : (
                "Assinar"
              )}
            </button>
          </div>
        ))}
      </div>

      <div className="mt-6 bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6">
        <h3 className="font-display text-sm font-bold text-fg mb-3">Agentes adicionais</h3>
        <p className="text-sm text-fg/65">
          Precisa de mais agentes que o plano inclui? Adicione quantos quiser por{" "}
          <span className="font-semibold text-fg">R$ {formatarReais(PRECO_AGENTE_ADICIONAL)}/mês cada</span>.
          Sem trocar de plano, sem migração — o agente novo entra no ar na hora.
        </p>
        <p className="text-sm text-fg/45 mt-3">
          Excedente de mensagens acima do limite do plano: R$ {formatarReais(PRECO_EXCEDENTE_1000_MSG)} a cada 1.000
          mensagens adicionais.
        </p>
      </div>
    </AppShell>
  );
}

function BarraUso({
  rotulo,
  usado,
  limite,
  className = "",
}: {
  rotulo: string;
  usado: number;
  limite: number;
  className?: string;
}) {
  const pct = limite > 0 ? Math.min(100, (usado / limite) * 100) : 0;
  const perto = pct >= 90;

  return (
    <div className={className}>
      <div className="flex items-baseline justify-between mb-1.5">
        <span className="text-xs text-fg/55">{rotulo}</span>
        <span className="text-xs font-medium text-fg/70">
          {usado.toLocaleString("pt-BR")} / {limite.toLocaleString("pt-BR")}
        </span>
      </div>
      <div className="h-1.5 rounded-full bg-paper/10 overflow-hidden">
        <div
          className={`h-full rounded-full ${perto ? "bg-rust" : "bg-amber"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function Feature({ texto }: { texto: string }) {
  return (
    <li className="flex items-start gap-2 text-sm text-fg/75">
      <svg
        className="h-4.5 w-4.5 shrink-0 text-teal mt-0.5"
        fill="none"
        viewBox="0 0 24 24"
        strokeWidth={2}
        stroke="currentColor"
      >
        <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
      </svg>
      {texto}
    </li>
  );
}
