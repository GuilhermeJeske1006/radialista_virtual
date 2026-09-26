"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "../../../components/AppShell";
import { apiFetch, ApiError } from "../../../lib/api";
import { setRadialistaAtualId } from "../../../lib/radialistas";
import { invalidarConfiguracaoInicial } from "../../../lib/useConfiguracaoInicial";
import { ConfiguracaoIA, DIAS_SEMANA_LABEL, Radialista, RadioPerfil, TipoRadio, Voz } from "../../../lib/types";
import { LocufySpin } from "../../../components/LocufyLogo";
import CombinacaoSelect from "../../../components/CombinacaoSelect";
import { AvisoPagamento, useExigirAssinatura } from "../../../components/AssinaturaGate";
import { Combinacao, consumoMensalEstimado, nomeModelo, reais, reaisPreciso } from "../../../lib/combinacoes";

function formatarDias(dias: number[], dataEspecifica: string | null): string {
  if (dataEspecifica) return `Avulso em ${dataEspecifica.split("-").reverse().join("/")}`;
  if (dias.length === 0) return "Todos os dias";
  return dias.map((d) => DIAS_SEMANA_LABEL[d]).join(", ");
}

export default function LocutorOnboardingPage() {
  const [tipoRadioConta, setTipoRadioConta] = useState("");
  const [tiposRadio, setTiposRadio] = useState<TipoRadio[]>([]);
  const [vozes, setVozes] = useState<Voz[]>([]);
  const [descricao, setDescricao] = useState("");
  const [gerando, setGerando] = useState(false);
  const [erro, setErro] = useState("");
  const [precisaUpgrade, setPrecisaUpgrade] = useState("");
  const [combinacao, setCombinacao] = useState<Combinacao | null>(null);
  const [criado, setCriado] = useState<ConfiguracaoIA | null>(null);
  const [verificandoSetup, setVerificandoSetup] = useState(true);
  const [jaConfigurado, setJaConfigurado] = useState(false);
  const { exigir, modal: modalAssinatura } = useExigirAssinatura();

  useEffect(() => {
    apiFetch<RadioPerfil>("/config/radio")
      .then((radio) => setTipoRadioConta(radio.tipo_radio))
      .catch(() => {});
    apiFetch<TipoRadio[]>("/config/tipos-radio")
      .then(setTiposRadio)
      .catch(() => {});
    apiFetch<Voz[]>("/tts/voices")
      .then(setVozes)
      .catch(() => {});
    // se a rádio ja' tem um radialista com voz definida, esse wizard ja' foi concluido antes --
    // mostrar de novo o CTA de gerar so' levaria a um 402 (limite de agentes atingido) sem
    // explicar por que, entao pula direto pro proximo passo do onboarding.
    apiFetch<Radialista[]>("/config/radialistas")
      .then((radialistas) => {
        if (radialistas.some((r) => r.voz_id)) setJaConfigurado(true);
      })
      .catch(() => {})
      .finally(() => setVerificandoSetup(false));
  }, []);

  const labelTipoRadioConta = tiposRadio.find((t) => t.value === tipoRadioConta)?.label;
  const vozGerada = criado ? vozes.find((v) => v.voz_id === criado.radialista.voz_id) : undefined;

  async function gerar() {
    setGerando(true);
    setErro("");
    setPrecisaUpgrade("");
    try {
      const resultado = await apiFetch<ConfiguracaoIA>("/config/radialistas/gerar-ia", {
        method: "POST",
        body: JSON.stringify({ descricao: descricao.trim(), combinacao_id: combinacao?.id ?? null }),
      });
      setRadialistaAtualId(resultado.radialista.id);
      setCriado(resultado);
      invalidarConfiguracaoInicial();
    } catch (err) {
      if (err instanceof ApiError && err.status === 402) {
        setPrecisaUpgrade(err.message || "Não foi possível autorizar esta geração.");
      } else {
        setErro(err instanceof ApiError ? err.message : "Erro ao gerar radialista com IA");
      }
    } finally {
      setGerando(false);
    }
  }

  if (verificandoSetup) {
    return (
      <AppShell title="Seu primeiro radialista" maxWidthClassName="max-w-lg">
        <p className="flex items-center gap-2 text-sm text-fg/65">
          <LocufySpin size={16} /> Carregando…
        </p>
      </AppShell>
    );
  }

  if (jaConfigurado && !criado) {
    return (
      <AppShell title="Seu primeiro radialista" maxWidthClassName="max-w-lg">
        <div className="bg-surface rounded-3xl border border-border-strong shadow-theme-xs p-6">
          <h2 className="font-display text-base font-bold text-fg mb-1">Seu radialista já está pronto</h2>
          <p className="text-sm text-fg/65 mb-5">
            Você já configurou um radialista com voz definida. Continue para o próximo passo ou ajuste a
            personalidade dele quando quiser em Radialistas.
          </p>
          <div className="flex flex-col sm:flex-row gap-3">
            <Link
              href="/onboarding"
              className="flex-1 text-center rounded-xl bg-brand-500 px-4 py-2.5 text-sm font-medium text-on-brand hover:bg-brand-600"
            >
              Continuar →
            </Link>
            <Link
              href="/radialista"
              className="flex-1 text-center rounded-xl border border-border-strong px-4 py-2.5 text-sm font-medium text-fg hover:bg-fg/5"
            >
              Ver radialistas
            </Link>
          </div>
        </div>
      </AppShell>
    );
  }

  if (criado) {
    return (
      <AppShell title="Radialista criado" maxWidthClassName="max-w-lg">
        <div className="bg-surface rounded-3xl border border-border-strong shadow-theme-xs p-6">
          <div className="flex items-center gap-2 mb-4">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-ciano text-on-brand">
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={3} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
              </svg>
            </span>
            <h2 className="font-display text-base font-bold text-fg">Pronto! Veja o que preparamos:</h2>
          </div>

          <dl className="space-y-3 mb-6">
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-fg/65">Radialista</dt>
              <dd className="text-sm font-medium text-fg">{criado.radialista.nome_locutor}</dd>
            </div>
            {vozGerada && (
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-fg/65">Voz</dt>
                <dd className="flex items-center gap-2 text-sm text-fg">
                  {vozGerada.nome} — {vozGerada.genero}
                  {vozGerada.preview_url && (
                    <audio controls preload="none" src={vozGerada.preview_url} className="h-8 w-40 shrink-0" />
                  )}
                </dd>
              </div>
            )}
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-fg/65">Programa</dt>
              <dd className="text-sm text-fg">
                {criado.programa.nome} · {formatarDias(criado.programa.dias_semana, criado.programa.data_especifica)} ·{" "}
                {criado.programa.horario_inicio.slice(0, 5)} às {criado.programa.horario_fim.slice(0, 5)}
              </dd>
            </div>
            {criado.combinacao && (
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-fg/65">Combinação</dt>
                <dd className="text-sm text-fg">
                  {criado.combinacao.nome} · Texto {nomeModelo(criado.combinacao.modelo_texto)} · Voz{" "}
                  {nomeModelo(criado.combinacao.modelo_voz)}
                </dd>
                <dd className="text-sm text-fg">
                  Uso estimado deste programa: ≈ {reais(consumoMensalEstimado(criado.combinacao, criado.programa))}/mês
                  ({reais(criado.combinacao.preco_hora_brl)} por hora de programa), além da mensalidade.
                </dd>
              </div>
            )}
            {criado.custo_geracao_brl != null && (
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-fg/65">Valor desta geração</dt>
                <dd className="text-sm text-fg">
                  {reaisPreciso(criado.custo_geracao_brl)} (radialista, programa e textos das vinhetas). O áudio das
                  vinhetas aparece no extrato quando ficar pronto.
                </dd>
              </div>
            )}
            {criado.programa.generos_musicais.length > 0 && (
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-fg/65">Toca</dt>
                <dd className="text-sm text-fg">{criado.programa.generos_musicais.join(", ")}</dd>
              </div>
            )}
          </dl>

          <p className="text-sm text-ciano mb-2">
            Criamos 3 vinhetas com trilha para este programa e colocamos na programação.
          </p>
          <p className="text-xs text-fg/65 mb-4">
            Dá pra ajustar tudo isso depois — tom de voz, tópicos, músicas e o roteiro do programa.
          </p>

          <div className="flex flex-col sm:flex-row gap-3">
            <Link
              href="/onboarding"
              className="flex-1 text-center rounded-xl bg-brand-500 px-4 py-2.5 text-sm font-medium text-on-brand hover:bg-brand-600"
            >
              Está bom, continuar →
            </Link>
            <Link
              href={`/radialista/${criado.radialista.id}`}
              className="flex-1 text-center rounded-xl border border-border-strong px-4 py-2.5 text-sm font-medium text-fg hover:bg-fg/5"
            >
              Personalizar tudo
            </Link>
          </div>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell title="Seu primeiro radialista" maxWidthClassName="max-w-3xl">
      <div className="bg-surface rounded-3xl border border-border-strong shadow-theme-xs p-6">
        <h2 className="font-display text-lg font-bold text-fg mb-1">Vamos criar seu primeiro radialista</h2>
        <p className="text-sm text-fg/65 mb-5">
          {tipoRadioConta
            ? `Baseado no perfil "${labelTipoRadioConta ?? tipoRadioConta}" que você escolheu, já preparamos um ponto de partida.`
            : "Descreva sua rádio (ou pule direto) e a IA já prepara um radialista e um programa prontos."}
        </p>

        <div className="rounded-xl border border-acento-claro/30 bg-acento/5 p-4 mb-4">
          <p className="text-sm font-medium text-fg mb-1">✨ Gerar automaticamente</p>
          <p className="text-xs text-fg/65 mb-3">Nome, voz e programa prontos em segundos. Você revisa e ajusta o que quiser depois.</p>
          <label htmlFor="onboarding-descricao" className="mb-1.5 block text-xs font-medium text-fg/80">
            Descreva sua rádio ou programa (opcional)
          </label>
          <textarea
            id="onboarding-descricao"
            value={descricao}
            onChange={(e) => setDescricao(e.target.value)}
            disabled={gerando}
            rows={3}
            placeholder="Ex.: programa de manhã, animado, com bloco de recado ao ouvinte…"
            className="w-full rounded-xl border border-border-strong bg-bg px-3 py-2.5 text-sm text-fg placeholder:text-fg/65 focus:outline-none focus:ring-2 focus:ring-acento-claro/40 disabled:opacity-60 mb-3"
          />
          <div className="mb-3">
            <CombinacaoSelect value={combinacao?.id ?? null} onChange={setCombinacao} disabled={gerando} compacto />
          </div>
          {combinacao && (
            <p role="status" className="rounded-lg bg-fg/5 px-3 py-2 text-xs text-fg/80 mb-3">
              Seu radialista vai usar <strong className="text-fg">{combinacao.nome}</strong>: texto{" "}
              <span translate="no">{nomeModelo(combinacao.modelo_texto)}</span> e voz{" "}
              <span translate="no">{nomeModelo(combinacao.modelo_voz)}</span> · ≈ {reais(combinacao.preco_hora_brl)} por
              hora de programa.
            </p>
          )}
          {erro && <p className="text-sm text-laranja mb-3">{erro}</p>}
          {precisaUpgrade && (
            <AvisoPagamento mensagem={precisaUpgrade} onClose={() => setPrecisaUpgrade("")} onAssinado={() => void gerar()} />
          )}
          <button
            type="button"
            onClick={() => exigir(() => void gerar())}
            disabled={gerando}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-acento px-4 py-2.5 text-sm font-medium text-on-brand hover:bg-acento/90 disabled:opacity-60"
          >
            {gerando ? (
              <>
                <LocufySpin size={14} /> Gerando…
              </>
            ) : combinacao ? (
              `Gerar agora com ${combinacao.nome} →`
            ) : (
              "Gerar agora →"
            )}
          </button>
        </div>

        <div className="text-center">
          <Link href="/radialista/novo" className="text-sm font-medium text-fg/65 hover:text-fg">
            ou prefiro configurar cada campo manualmente →
          </Link>
        </div>
      </div>
      {modalAssinatura}
    </AppShell>
  );
}
