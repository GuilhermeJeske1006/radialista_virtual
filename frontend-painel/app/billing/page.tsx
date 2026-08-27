"use client";

import { useEffect, useState } from "react";
import AppShell from "../../components/AppShell";
import { apiFetch, ApiError } from "../../lib/api";
import { LocufyLed, LocufySpin } from "../../components/LocufyLogo";
import { PLANOS, PRECO_AGENTE_ADICIONAL, PRECO_EXCEDENTE_1000_MSG, formatarReais } from "../../lib/planos";

type StatusPlano = {
  plano_status: string;
  plano: string;
  agentes_usados: number;
  agentes_limite: number;
  agentes_extras: number;
  mensagens_usadas: number;
  mensagens_limite: number;
  mensagens_extras: number;
};

export default function BillingPage() {
  const [statusPlano, setStatusPlano] = useState<StatusPlano | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [carregandoId, setCarregandoId] = useState<string | null>(null);
  const [erro, setErro] = useState("");
  const [comprandoAgenteExtra, setComprandoAgenteExtra] = useState(false);
  const [erroAgenteExtra, setErroAgenteExtra] = useState("");
  const [modalExcedenteAberto, setModalExcedenteAberto] = useState(false);
  const [blocosExcedente, setBlocosExcedente] = useState(1);
  const [comprandoExcedente, setComprandoExcedente] = useState(false);
  const [erroExcedente, setErroExcedente] = useState("");

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

  async function comprarAgenteExtra() {
    setComprandoAgenteExtra(true);
    setErroAgenteExtra("");
    try {
      const { url } = await apiFetch<{ url: string }>("/billing/agentes-extras/checkout", { method: "POST" });
      window.location.href = url;
    } catch (err) {
      setErroAgenteExtra(err instanceof ApiError ? err.message : "Erro ao iniciar compra");
      setComprandoAgenteExtra(false);
    }
  }

  async function comprarExcedente() {
    setComprandoExcedente(true);
    setErroExcedente("");
    try {
      const { url } = await apiFetch<{ url: string }>("/billing/excedente-mensagens/checkout", {
        method: "POST",
        body: JSON.stringify({ blocos: blocosExcedente }),
      });
      window.location.href = url;
    } catch (err) {
      setErroExcedente(err instanceof ApiError ? err.message : "Erro ao iniciar compra");
      setComprandoExcedente(false);
    }
  }

  const ativo = statusPlano?.plano_status === "ativo";
  const planoAtual = PLANOS.find((p) => p.id === statusPlano?.plano);

  return (
    <AppShell title="Assinatura" maxWidthClassName="max-w-6xl">
      <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6 mb-8 max-w-lg">
        <h2 className="font-display text-base font-bold text-fg mb-4">Plano atual</h2>
        {carregando ? (
          <p className="flex items-center gap-2 text-sm text-fg/65">
            <LocufySpin size={16} /> Carregando...
          </p>
        ) : statusPlano ? (
          <>
            <div className="flex items-center gap-2 mb-5">
              <span className="text-sm text-fg/65">Status:</span>
              <span
                className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${
                  ativo ? "bg-teal/10 text-teal-text" : "bg-amber/10 text-amber-text"
                }`}
              >
                <LocufyLed color={ativo ? "teal" : "amber"} pulse={false} />
                {statusPlano.plano_status}
              </span>
              {planoAtual && (
                <span className="text-sm text-fg/65">— {planoAtual.nome}</span>
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
        <p className="text-sm text-fg/65">
          Todos os planos incluem os mesmos agentes de IA (comercial, qualificação, agendamento,
          suporte, pós-venda e mais), sempre atendendo pelo único número de WhatsApp da sua rádio —
          o que muda é quantos agentes você pode rodar ao mesmo tempo.
        </p>
      </div>

      {erro && <p className="text-sm text-rust-text mb-4">{erro}</p>}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {PLANOS.map((plano) => {
          const ehPlanoSelecionado = plano.id === statusPlano?.plano;
          const ehPlanoAtual = ativo && ehPlanoSelecionado;
          return (
          <div
            key={plano.id}
            className={`relative flex flex-col rounded-2xl border p-6 shadow-theme-xs ${
              ehPlanoSelecionado
                ? "bg-surface border-teal/50 ring-1 ring-teal/30"
                : plano.destaque
                ? "bg-surface border-amber/50 ring-1 ring-amber/30"
                : "bg-surface border-border-strong"
            }`}
          >
            {ehPlanoSelecionado ? (
              <span className="absolute -top-3 left-6 rounded-full bg-teal px-2.5 py-0.5 text-[11px] font-semibold text-ink">
                Seu plano atual
              </span>
            ) : (
              plano.destaque && (
                <span className="absolute -top-3 left-6 rounded-full bg-brand-500 px-2.5 py-0.5 text-[11px] font-semibold text-ink">
                  Mais escolhido
                </span>
              )
            )}

            <h2 className="font-display text-base font-bold text-fg">{plano.nome}</h2>
            <p className="text-xs text-fg/65 mt-1 mb-5">{plano.descricao}</p>

            <div className="mb-5">
              <span className="font-display text-3xl font-bold text-fg">
                R$ {formatarReais(plano.preco)}
              </span>
              <span className="text-sm text-fg/65">/mês</span>
            </div>

            <ul className="space-y-2.5 mb-6 flex-1">
              <Feature texto={`${plano.agentes} ${plano.agentes === 1 ? "agente" : "agentes"} de IA inclusos`} />
              <Feature texto={`${plano.mensagens.toLocaleString("pt-BR")} mensagens/mês`} />
              <Feature texto="Respostas automáticas com IA" />
              <Feature texto="Encaminhamento pra atendimento humano" />
            </ul>

            {ehPlanoAtual ? (
              <span className="flex items-center justify-center rounded-lg border border-teal/40 bg-teal/10 px-4 py-2.5 text-sm font-medium text-teal-text">
                Plano atual
              </span>
            ) : (
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
                    <LocufySpin size={14} /> Redirecionando...
                  </>
                ) : (
                  "Assinar"
                )}
              </button>
            )}
          </div>
          );
        })}
      </div>

      <div className="mt-6 bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h3 className="font-display text-sm font-bold text-fg mb-3">Agentes adicionais</h3>
            <p className="text-sm text-fg/65">
              Precisa de mais agentes que o plano inclui? Adicione quantos quiser por{" "}
              <span className="font-semibold text-fg">R$ {formatarReais(PRECO_AGENTE_ADICIONAL)}/mês cada</span>.
              Sem trocar de plano, sem migração — o agente novo entra no ar na hora.
              {!!statusPlano?.agentes_extras && (
                <span className="block text-fg/65 mt-1">
                  Você já tem {statusPlano.agentes_extras} agente(s) extra(s) ativo(s).
                </span>
              )}
            </p>
          </div>
          {ativo && (
            <button
              type="button"
              onClick={comprarAgenteExtra}
              disabled={comprandoAgenteExtra}
              className="flex items-center gap-2 shrink-0 rounded-lg bg-paper/10 px-4 py-2.5 text-sm font-medium text-fg hover:bg-paper/15 disabled:opacity-60"
            >
              {comprandoAgenteExtra ? (
                <>
                  <LocufySpin size={14} /> Redirecionando...
                </>
              ) : (
                "+ Agente extra"
              )}
            </button>
          )}
        </div>
        {erroAgenteExtra && <p className="text-sm text-rust-text mt-2">{erroAgenteExtra}</p>}

        <div className="mt-5 pt-5 border-t border-border flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm text-fg/65">
              Excedente de mensagens acima do limite do plano: R$ {formatarReais(PRECO_EXCEDENTE_1000_MSG)} a cada
              1.000 mensagens adicionais.
              {!!statusPlano?.mensagens_extras && (
                <span className="block text-fg/65 mt-1">
                  {statusPlano.mensagens_extras.toLocaleString("pt-BR")} mensagens extras compradas este mês.
                </span>
              )}
            </p>
          </div>
          {ativo && (
            <button
              type="button"
              onClick={() => setModalExcedenteAberto(true)}
              className="shrink-0 rounded-lg bg-paper/10 px-4 py-2.5 text-sm font-medium text-fg hover:bg-paper/15"
            >
              Comprar excedente
            </button>
          )}
        </div>
      </div>

      {modalExcedenteAberto && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/50 px-4"
          onClick={() => !comprandoExcedente && setModalExcedenteAberto(false)}
        >
          <div
            className="w-full max-w-sm rounded-2xl border border-border-strong bg-surface p-6 shadow-theme-xs"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="font-display text-base font-bold text-fg mb-2">Comprar excedente de mensagens</h2>
            <p className="text-sm text-fg/70 mb-4">
              Cada bloco libera 1.000 mensagens a mais neste mês, por R$ {formatarReais(PRECO_EXCEDENTE_1000_MSG)}{" "}
              cada.
            </p>
            <label className="block text-sm font-medium text-fg/80 mb-1.5">Blocos de 1.000 mensagens</label>
            <input
              type="number"
              min={1}
              max={50}
              value={blocosExcedente}
              onChange={(e) => setBlocosExcedente(Math.min(50, Math.max(1, Number(e.target.value) || 1)))}
              disabled={comprandoExcedente}
              className="w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:ring-2 focus:ring-amber/40 disabled:opacity-60"
            />
            <p className="text-sm text-fg/65 mt-2">
              Total: <span className="font-semibold text-fg">R$ {formatarReais(blocosExcedente * PRECO_EXCEDENTE_1000_MSG)}</span>
            </p>
            {erroExcedente && <p className="text-sm text-rust-text mt-2">{erroExcedente}</p>}
            <div className="flex justify-end gap-3 mt-5">
              <button
                type="button"
                onClick={() => setModalExcedenteAberto(false)}
                disabled={comprandoExcedente}
                className="rounded-lg px-4 py-2.5 text-sm font-medium text-fg/60 hover:text-fg disabled:opacity-60"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={comprarExcedente}
                disabled={comprandoExcedente}
                className="flex items-center gap-2 rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-ink hover:bg-brand-600 disabled:opacity-60"
              >
                {comprandoExcedente ? (
                  <>
                    <LocufySpin size={14} /> Redirecionando...
                  </>
                ) : (
                  "Comprar"
                )}
              </button>
            </div>
          </div>
        </div>
      )}
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
        <span className="text-xs text-fg/65">{rotulo}</span>
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
        className="h-4.5 w-4.5 shrink-0 text-teal-text mt-0.5"
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
