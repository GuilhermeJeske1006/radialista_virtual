"use client";

import { useEffect, useState } from "react";
import AppShell from "../../components/AppShell";
import CheckoutModal from "../../components/CheckoutModal";
import { apiFetch, ApiError } from "../../lib/api";
import { LocufyLed, LocufySpin } from "../../components/LocufyLogo";
import {
  PLANOS,
  PRECO_AGENTE_ADICIONAL,
  PRECO_EXCEDENTE_1000_MSG,
  formatarReais,
  permiteClonagemVoz,
} from "../../lib/planos";
import { Radialista } from "../../lib/types";
import { UpsellBanner } from "../../components/UpsellBanner";

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
  const [checkoutAgenteExtraAberto, setCheckoutAgenteExtraAberto] = useState(false);
  const [modalExcedenteAberto, setModalExcedenteAberto] = useState(false);
  const [blocosExcedente, setBlocosExcedente] = useState(1);
  const [checkoutExcedenteBlocos, setCheckoutExcedenteBlocos] = useState<number | null>(null);
  const [assinaturaConfirmada, setAssinaturaConfirmada] = useState(false);
  const [compraConfirmada, setCompraConfirmada] = useState<string | null>(null);
  const [planoTrocado, setPlanoTrocado] = useState(false);
  const [abrindoPortal, setAbrindoPortal] = useState(false);
  const [erroPortal, setErroPortal] = useState("");
  const [checkoutPlanoId, setCheckoutPlanoId] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<StatusPlano>("/billing/status")
      .then(setStatusPlano)
      .catch((err) => setErro(err instanceof ApiError ? err.message : "Erro ao carregar plano"))
      .finally(() => setCarregando(false));
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("success") !== "true") return;
    window.history.replaceState(null, "", "/billing");
    confirmarAssinatura();
  }, []);

  // primeira assinatura confirmada e ainda sem locutor pronto -- manda pro wizard guiado em
  // vez de deixar o usuario "cair" direto no painel sem saber o proximo passo. Chamada tanto
  // pelo fallback de redirect (?success=true, caso raro de 3DS) quanto pelo onSuccess do
  // checkout embutido (caminho comum, sem navegar a pagina).
  function confirmarAssinatura() {
    apiFetch<Radialista[]>("/config/radialistas")
      .then((radialistas) => {
        const jaTemLocutorPronto = radialistas.some((r) => r.ativo && r.voz_id);
        if (jaTemLocutorPronto) {
          setAssinaturaConfirmada(true);
        } else {
          window.location.href = "/onboarding/locutor";
        }
      })
      .catch(() => setAssinaturaConfirmada(true));
  }

  // Webhook confirma a compra de forma assincrona (um instante depois do confirmPayment
  // resolver no navegador) -- reconsulta /billing/status algumas vezes pra pegar o estado
  // atualizado (plano ativo, contador de agentes extras, etc.) sem precisar recarregar a pagina.
  function repollStatus(tentativas = 5) {
    apiFetch<StatusPlano>("/billing/status")
      .then(setStatusPlano)
      .catch(() => {});
    if (tentativas > 1) setTimeout(() => repollStatus(tentativas - 1), 1500);
  }

  async function assinar(planoId: string) {
    setErro("");
    setPlanoTrocado(false);
    if (!ativo) {
      // ainda sem assinatura: abre o checkout transparente (embutido na pagina) --
      // o pagamento acontece sem sair do painel.
      setCheckoutPlanoId(planoId);
      return;
    }
    // ja assinante: troca o price da assinatura existente na hora (com proration),
    // sem passar pelo checkout de novo -- ver POST /billing/trocar-plano.
    setCarregandoId(planoId);
    try {
      const atualizado = await apiFetch<StatusPlano>("/billing/trocar-plano", {
        method: "POST",
        body: JSON.stringify({ plano_id: planoId }),
      });
      setStatusPlano(atualizado);
      setPlanoTrocado(true);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao trocar de plano");
    } finally {
      setCarregandoId(null);
    }
  }

  async function abrirPortal() {
    setErroPortal("");
    setAbrindoPortal(true);
    try {
      const { url } = await apiFetch<{ url: string }>("/billing/portal", { method: "POST" });
      window.location.href = url;
    } catch (err) {
      setErroPortal(err instanceof ApiError ? err.message : "Erro ao abrir portal de pagamento");
      setAbrindoPortal(false);
    }
  }

  function comprarExcedente() {
    // fecha o seletor de quantidade e abre o checkout transparente ja' travado
    // na quantidade escolhida.
    setModalExcedenteAberto(false);
    setCheckoutExcedenteBlocos(blocosExcedente);
  }

  const ativo = statusPlano?.plano_status === "ativo";
  const planoAtual = PLANOS.find((p) => p.id === statusPlano?.plano);

  return (
    <AppShell title="Assinatura" maxWidthClassName="max-w-6xl">
      <UpsellBanner />

      {assinaturaConfirmada && (
        <div className="flex items-center justify-between gap-4 rounded-2xl border border-teal/40 bg-teal/10 px-5 py-3 mb-6 max-w-2xl">
          <p className="text-sm font-medium text-fg">Assinatura confirmada.</p>
          <button
            type="button"
            onClick={() => setAssinaturaConfirmada(false)}
            aria-label="Dispensar aviso"
            className="shrink-0 text-fg/50 hover:text-fg"
          >
            ✕
          </button>
        </div>
      )}

      {compraConfirmada && (
        <div className="flex items-center justify-between gap-4 rounded-2xl border border-teal/40 bg-teal/10 px-5 py-3 mb-6 max-w-2xl">
          <p className="text-sm font-medium text-fg">{compraConfirmada}</p>
          <button
            type="button"
            onClick={() => setCompraConfirmada(null)}
            aria-label="Dispensar aviso"
            className="shrink-0 text-fg/50 hover:text-fg"
          >
            ✕
          </button>
        </div>
      )}

      {planoTrocado && (
        <div className="flex items-center justify-between gap-4 rounded-2xl border border-teal/40 bg-teal/10 px-5 py-3 mb-6 max-w-2xl">
          <p className="text-sm font-medium text-fg">Plano trocado com sucesso.</p>
          <button
            type="button"
            onClick={() => setPlanoTrocado(false)}
            aria-label="Dispensar aviso"
            className="shrink-0 text-fg/50 hover:text-fg"
          >
            ✕
          </button>
        </div>
      )}
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
              rotulo="Tokens do WhatsApp este mês"
              usado={statusPlano.mensagens_usadas}
              limite={statusPlano.mensagens_limite}
              className="mt-4"
            />

            {ativo && (
              <>
                <button
                  type="button"
                  onClick={abrirPortal}
                  disabled={abrindoPortal}
                  className="mt-5 flex items-center gap-2 rounded-lg bg-paper/10 px-4 py-2.5 text-sm font-medium text-fg hover:bg-paper/15 disabled:opacity-60"
                >
                  {abrindoPortal ? (
                    <>
                      <LocufySpin size={14} /> Abrindo...
                    </>
                  ) : (
                    "Gerenciar pagamento"
                  )}
                </button>
                {erroPortal && <p className="text-sm text-rust-text mt-2">{erroPortal}</p>}
              </>
            )}
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
              <Feature
                texto={`${plano.agentes} ${plano.agentes === 1 ? "locutor de IA incluso" : "locutores de IA inclusos"}`}
              />
              <Feature texto={`${plano.mensagens.toLocaleString("pt-BR")} mensagens/mês no WhatsApp`} />
              <Feature texto="Respostas automáticas com IA" />
              {permiteClonagemVoz(plano.id) && (
                <Feature texto={plano.id === "professional" ? "Clonagem de voz inclusa" : "Opção de clonagem de voz"} />
              )}
              {plano.radialistasPorPrograma > 1 && (
                <Feature texto={`Até ${plano.radialistasPorPrograma} locutores por programa (diálogo)`} />
              )}
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
                    <LocufySpin size={14} /> Trocando...
                  </>
                ) : ativo ? (
                  "Trocar pra esse plano"
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
              onClick={() => setCheckoutAgenteExtraAberto(true)}
              className="flex items-center gap-2 shrink-0 rounded-lg bg-paper/10 px-4 py-2.5 text-sm font-medium text-fg hover:bg-paper/15"
            >
              + Agente extra
            </button>
          )}
        </div>

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
          onClick={() => setModalExcedenteAberto(false)}
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
              className="w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:ring-2 focus:ring-amber/40"
            />
            <p className="text-sm text-fg/65 mt-2">
              Total: <span className="font-semibold text-fg">R$ {formatarReais(blocosExcedente * PRECO_EXCEDENTE_1000_MSG)}</span>
            </p>
            <div className="flex justify-end gap-3 mt-5">
              <button
                type="button"
                onClick={() => setModalExcedenteAberto(false)}
                className="rounded-lg px-4 py-2.5 text-sm font-medium text-fg/60 hover:text-fg"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={comprarExcedente}
                className="flex items-center gap-2 rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-ink hover:bg-brand-600"
              >
                Comprar
              </button>
            </div>
          </div>
        </div>
      )}

      {checkoutPlanoId && (
        <CheckoutModal
          open
          endpoint="/billing/checkout"
          body={{ plano_id: checkoutPlanoId }}
          onClose={() => setCheckoutPlanoId(null)}
          onSuccess={() => {
            setCheckoutPlanoId(null);
            repollStatus();
            confirmarAssinatura();
          }}
        />
      )}

      {checkoutAgenteExtraAberto && (
        <CheckoutModal
          open
          endpoint="/billing/agentes-extras/checkout"
          onClose={() => setCheckoutAgenteExtraAberto(false)}
          onSuccess={() => {
            setCheckoutAgenteExtraAberto(false);
            repollStatus();
            setCompraConfirmada("Agente extra ativado.");
          }}
        />
      )}

      {checkoutExcedenteBlocos !== null && (
        <CheckoutModal
          open
          endpoint="/billing/excedente-mensagens/checkout"
          body={{ blocos: checkoutExcedenteBlocos }}
          onClose={() => setCheckoutExcedenteBlocos(null)}
          onSuccess={() => {
            setCheckoutExcedenteBlocos(null);
            repollStatus();
            setCompraConfirmada("Excedente de mensagens creditado.");
          }}
        />
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
