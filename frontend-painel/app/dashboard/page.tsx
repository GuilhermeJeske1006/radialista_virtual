"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "../../components/AppShell";
import { apiFetch, ApiError } from "../../lib/api";
import { Conta, Patrocinador, Programa, Radialista, RadioConta } from "../../lib/types";
import { LocufyLed, LocufySpin } from "../../components/LocufyLogo";
import { GraficoBarras, PontoSerie } from "../../components/GraficoBarras";
import { UpsellBanner } from "../../components/UpsellBanner";
import { useAppConfigurado } from "../../lib/instalarApp";
import { useNoAr } from "../../lib/useNoAr";
import { PASSOS_TOUR } from "../../lib/tour";
import { rotuloStatusAssinatura } from "../../lib/rotulosConsumo";
import { reais } from "../../lib/combinacoes";

const ATALHOS = [
  {
    href: "/live",
    label: "Ao Vivo",
    descricao: "Acompanhar programas no ar",
  },
  {
    href: "/vinhetagem",
    label: "Vinhetagem",
    descricao: "Gerenciar vinhetas, categorias e propagandas",
  },
  {
    href: "/metrics",
    label: "Métricas",
    descricao: "Acompanhar interações dos ouvintes",
  },
  {
    href: "/conversas",
    label: "Conversas",
    descricao: "Ver histórico de mensagens do WhatsApp",
  },
  {
    href: "/billing",
    label: "Assinatura",
    descricao: "Consumo, limite e faturas",
  },
  {
    href: "/perfil",
    label: "Perfil",
    descricao: "Dados da conta",
  },
];

type ConsumoCiclo = { consumo_brl: number; orcamento_brl: number; previsao_brl: number };

export default function DashboardPage() {
  const [conta, setConta] = useState<Conta | null>(null);
  const [radialistas, setRadialistas] = useState<Radialista[]>([]);
  const [radioConta, setRadioConta] = useState<RadioConta | null>(null);
  const [programas, setProgramas] = useState<Programa[]>([]);
  const [patrocinadores, setPatrocinadores] = useState<Patrocinador[]>([]);
  const { estado: noAr, noAr: realmenteNoAr } = useNoAr();
  const [consumo, setConsumo] = useState<ConsumoCiclo | null>(null);
  const [mensagens7Dias, setMensagens7Dias] = useState<number | null>(null);
  const [mensagensPorDia, setMensagensPorDia] = useState<PontoSerie[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");
  const [onboardingIncompleto, setOnboardingIncompleto] = useState(false);
  // do aparelho, nao da conta (ver lib/instalarApp.ts) -- conta como pendente em cada computador
  const appPronto = useAppConfigurado();
  // aba do navegador que cedeu o ao vivo pro app recem-instalado (ver app/live/page.tsx)
  const [aoVivoNoApp, setAoVivoNoApp] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("app") === "instalado") {
      setAoVivoNoApp(true);
      params.delete("app");
      const resto = params.toString();
      window.history.replaceState(null, "", resto ? `/dashboard?${resto}` : "/dashboard");
    }
    if (params.get("onboarding") === "incompleto") {
      setOnboardingIncompleto(true);
      params.delete("onboarding");
      const resto = params.toString();
      window.history.replaceState(null, "", resto ? `/dashboard?${resto}` : "/dashboard");
    }
  }, []);

  useEffect(() => {
    Promise.all([
      apiFetch<Conta>("/auth/me"),
      apiFetch<Radialista[]>("/config/radialistas"),
      apiFetch<RadioConta>("/config/radio"),
      apiFetch<Patrocinador[]>("/patrocinadores").catch(() => [] as Patrocinador[]),
    ])
      .then(async ([c, r, radio, patro]) => {
        setConta(c);
        setRadialistas(r);
        setRadioConta(radio);
        setPatrocinadores(patro);

        const listasDeProgramas = await Promise.all(
          r.map((rad) =>
            apiFetch<Programa[]>(`/config/radialistas/${rad.id}/programas`).catch(() => [] as Programa[])
          )
        );
        setProgramas(listasDeProgramas.flat());

        const resumos = await Promise.all(
          r.map((rad) =>
            apiFetch<{ ultimos_7_dias: number; mensagens_por_dia: PontoSerie[] }>(
              `/metrics/summary?radialista_id=${rad.id}`
            ).catch(() => null)
          )
        );
        setMensagens7Dias(resumos.reduce((soma, res) => soma + (res?.ultimos_7_dias ?? 0), 0));

        const totaisPorData = new Map<string, number>();
        resumos.forEach((res) => {
          res?.mensagens_por_dia.forEach((ponto) => {
            totaisPorData.set(ponto.data, (totaisPorData.get(ponto.data) ?? 0) + ponto.total);
          });
        });
        setMensagensPorDia(
          [...totaisPorData.entries()]
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([data, total]) => ({ data, total }))
        );
      })
      .catch((err) => setErro(err instanceof ApiError ? err.message : "Erro ao carregar painel"))
      .finally(() => setCarregando(false));
  }, []);

  useEffect(() => {
    apiFetch<ConsumoCiclo>("/billing/consumo-ia")
      .then((c) => {
        if (c && typeof c.consumo_brl === "number") setConsumo(c);
      })
      .catch(() => {});
  }, []);

  const whatsappConectado = Boolean(radioConta?.wuzapi_token);
  const perfilPreenchido = Boolean(radioConta?.nome_radio && radioConta?.frequencia);
  const radialistasProntos = radialistas.filter((r) => r.ativo && r.voz_id).length;
  const temRadialistaPronto = radialistasProntos > 0;
  const programasAtivos = programas.filter((p) => p.ativo).length;
  const temProgramaAtivo = programasAtivos > 0;
  const patrocinadoresAtivos = patrocinadores.filter((p) => p.ativo).length;
  const temPatrocinador = patrocinadoresAtivos > 0;
  // Os quatro passos obrigatórios são os mesmos do tour e da barra lateral (lib/tour.ts).
  const estadoSetup = {
    radialistaPronto: temRadialistaPronto,
    programaAtivo: temProgramaAtivo,
    whatsappConectado,
    completa: temRadialistaPronto && temProgramaAtivo && whatsappConectado,
    appPronto,
  };
  const TAREFAS_AO_VIVO = [
    ...PASSOS_TOUR.map((p) => ({ feita: p.feito(estadoSetup), label: `${p.numero}. ${p.titulo}`, descricao: p.texto, href: p.href, opcional: false })),
    {
      feita: perfilPreenchido,
      label: "Completar dados da rádio",
      descricao: "Opcional — nome e frequência ajudam o radialista a se apresentar",
      href: "/configuracoes",
      opcional: true,
    },
    {
      feita: temPatrocinador,
      label: "Cadastrar vinhetagem",
      descricao: "Opcional — para inserir chamadas comerciais no ar",
      href: "/vinhetagem",
      opcional: true,
    },
  ];
  const pendentes = TAREFAS_AO_VIVO.filter((t) => !t.feita && !t.opcional).length;
  const feitos = PASSOS_TOUR.length - pendentes;

  const checklist = (
    <div className="bg-surface rounded-3xl border border-border-strong shadow-theme-xs p-5 mb-6">
      <div className="flex items-center justify-between gap-3 mb-3">
        <h2 className="font-display text-sm font-bold text-fg">
          {pendentes === 0 ? "Pronto para o ao vivo" : "Configuração inicial"}
        </h2>
        <span className="text-xs font-medium text-fg/65 tabular-nums">
          {pendentes === 0 ? "Tudo certo" : `${feitos} de ${PASSOS_TOUR.length} concluídos`}
        </span>
      </div>
      <ul className="flex flex-col gap-2.5">
        {TAREFAS_AO_VIVO.map((t) => (
          <li key={t.label}>
            <Link href={t.href} className="flex items-start gap-3 group rounded-xl -mx-2 px-2 py-1.5 hover:bg-fg/5">
              <span
                className={`mt-0.5 shrink-0 w-5 h-5 rounded-full border flex items-center justify-center ${
                  t.feita ? "bg-ciano border-ciano text-on-brand" : "border-border-strong text-transparent"
                }`}
                aria-hidden="true"
              >
                <svg viewBox="0 0 16 16" width="11" height="11" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M3 8l3 3 7-7" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </span>
              <span className="flex-1">
                <span
                  className={`text-sm font-medium group-hover:text-acento-claro transition-colors ${
                    t.feita ? "text-fg/65 line-through" : "text-fg"
                  }`}
                >
                  {t.label}
                  <span className="sr-only">{t.feita ? " (concluído)" : " (pendente)"}</span>
                </span>
                <span className="block text-xs text-fg/65">{t.descricao}</span>
              </span>
              {!t.feita && <span className="text-acento-claro shrink-0 text-sm" aria-hidden="true">→</span>}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );

  return (
    <AppShell title="Visão geral" maxWidthClassName="max-w-4xl">
      {erro && <p className="text-sm text-laranja mb-4">{erro}</p>}

      <UpsellBanner />

      {aoVivoNoApp && (
        <div role="status" className="rounded-3xl border border-ciano bg-ciano/10 px-5 py-4 mb-6">
          <p className="text-sm font-medium text-ciano">
            O ao vivo está rodando no app Locufy (janela própria, som liberado), então esta aba saiu do ar para a rádio não tocar em dobro.
          </p>
          <p className="text-sm text-fg/65 mt-0.5">Pode fechar esta aba do navegador.</p>
        </div>
      )}

      {onboardingIncompleto && (
        <div className="flex items-start justify-between gap-4 rounded-3xl border border-acento-claro/40 bg-acento/10 px-5 py-4 mb-6">
          <div>
            <p className="text-sm font-medium text-fg">Sua conta foi criada, mas alguns dados podem não ter sido salvos.</p>
            <p className="text-sm text-fg/65 mt-0.5">
              Confira{" "}
              <Link href="/configuracoes" className="text-acento-claro hover:text-acento-dim font-medium underline">
                Configurações
              </Link>
              {" "}e{" "}
              <Link href="/radialista" className="text-acento-claro hover:text-acento-dim font-medium underline">
                Radialistas
              </Link>
              .
            </p>
          </div>
          <button
            type="button"
            onClick={() => setOnboardingIncompleto(false)}
            aria-label="Dispensar aviso"
            className="-m-2 flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-fg/65 hover:bg-fg/5 hover:text-fg"
          >
            ✕
          </button>
        </div>
      )}

      {carregando ? (
        <p className="flex items-center gap-2 text-sm text-fg/65">
          <LocufySpin size={16} /> Carregando…
        </p>
      ) : (
        <>
          {/* No topo só enquanto falta passo da conta; o do app é por computador e não deve
              empurrar o resto do painel de uma rádio que já opera pelo navegador. */}
          {!estadoSetup.completa && checklist}

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <div className="bg-surface rounded-3xl border border-border-strong shadow-theme-xs p-5">
              <p className="text-xs font-medium uppercase tracking-wide text-fg/65 mb-1">Radialistas</p>
              <p className="font-display text-2xl font-bold text-fg">{radialistas.length}</p>
              <p className="text-xs text-fg/65 mt-0.5">
                {radialistasProntos} pronto{radialistasProntos === 1 ? "" : "s"} com voz definida
              </p>
            </div>
            <div className="bg-surface rounded-3xl border border-border-strong shadow-theme-xs p-5">
              <p className="text-xs font-medium uppercase tracking-wide text-fg/65 mb-1">WhatsApp da rádio</p>
              <p className="flex items-center gap-2 font-display text-2xl font-bold text-fg">
                <LocufyLed color={whatsappConectado ? "ciano" : "laranja"} pulse={false} />
                {whatsappConectado ? "Conectado" : "Não conectado"}
              </p>
            </div>
            <div className="bg-surface rounded-3xl border border-border-strong shadow-theme-xs p-5">
              <p className="text-xs font-medium uppercase tracking-wide text-fg/65 mb-1">No ar agora</p>
              {realmenteNoAr ? (
                <>
                  <p className="flex items-center gap-2 font-display text-2xl font-bold text-fg truncate">
                    <LocufyLed color="laranja" pulse /> {noAr!.radialista_nome}
                  </p>
                  <p className="text-xs text-fg/65 mt-0.5 truncate">{noAr!.programa_nome}</p>
                </>
              ) : (
                <p className="flex items-center gap-2 font-display text-2xl font-bold text-fg/65">
                  <LocufyLed color="acento" pulse={false} /> Ninguém
                </p>
              )}
            </div>
            <Link
              href="/billing"
              className="bg-surface rounded-3xl border border-border-strong shadow-theme-xs p-5 hover:border-acento-claro/40 transition-colors"
            >
              <p className="text-xs font-medium uppercase tracking-wide text-fg/65 mb-1">Uso de IA no ciclo</p>
              <p className="font-display text-2xl font-bold text-fg tabular-nums">{consumo ? reais(consumo.consumo_brl) : "—"}</p>
              <p className="text-xs text-fg/65 mt-0.5">
                {consumo && consumo.orcamento_brl > 0
                  ? `de ${reais(consumo.orcamento_brl)} de limite · ${rotuloStatusAssinatura(conta?.plano_status ?? "")}`
                  : `Locufy Flex · ${rotuloStatusAssinatura(conta?.plano_status ?? "")}`}
              </p>
              {consumo && consumo.orcamento_brl > 0 && (
                <span className="mt-2 block h-1.5 overflow-hidden rounded-full bg-fg/10" aria-hidden="true">
                  <span
                    className={`block h-full rounded-full ${consumo.consumo_brl / consumo.orcamento_brl >= 0.8 ? "bg-laranja" : "bg-ciano"}`}
                    style={{ width: `${Math.min(100, (consumo.consumo_brl / consumo.orcamento_brl) * 100)}%` }}
                  />
                </span>
              )}
            </Link>
            <div className="bg-surface rounded-3xl border border-border-strong shadow-theme-xs p-5">
              <p className="text-xs font-medium uppercase tracking-wide text-fg/65 mb-1">Programas</p>
              <p className="font-display text-2xl font-bold text-fg">{programas.length}</p>
              <p className="text-xs text-fg/65 mt-0.5">
                {programasAtivos} ativo{programasAtivos === 1 ? "" : "s"} na grade
              </p>
            </div>
            <div className="bg-surface rounded-3xl border border-border-strong shadow-theme-xs p-5">
              <p className="text-xs font-medium uppercase tracking-wide text-fg/65 mb-1">Vinhetagem</p>
              <p className="font-display text-2xl font-bold text-fg">{patrocinadores.length}</p>
              <p className="text-xs text-fg/65 mt-0.5">
                {patrocinadoresAtivos} patrocinador{patrocinadoresAtivos === 1 ? "" : "es"} ativo{patrocinadoresAtivos === 1 ? "" : "s"}
              </p>
            </div>
            <Link
              href="/metrics"
              className="bg-surface rounded-3xl border border-border-strong shadow-theme-xs p-5 hover:border-acento-claro/40 transition-colors"
            >
              <p className="text-xs font-medium uppercase tracking-wide text-fg/65 mb-1">Mensagens (7 dias)</p>
              <p className="font-display text-2xl font-bold text-fg">{mensagens7Dias ?? "-"}</p>
              <p className="text-xs text-fg/65 mt-0.5">Interações com ouvintes</p>
            </Link>
          </div>

          {mensagensPorDia.some((ponto) => ponto.total > 0) && (
            <div className="bg-surface rounded-3xl border border-border-strong shadow-theme-xs p-5 mb-6">
              <div className="flex items-center justify-between mb-3">
                <p className="font-display text-sm font-bold text-fg">Mensagens por dia (últimos 30 dias)</p>
                <Link href="/metrics" className="text-xs font-medium text-acento-claro hover:text-acento-dim">
                  Ver detalhes
                </Link>
              </div>
              <GraficoBarras serie={mensagensPorDia} />
            </div>
          )}

          {estadoSetup.completa && checklist}

          {/* So' em telas pequenas: no desktop a sidebar (sempre visivel) ja' cobre os
              mesmos destinos, sem precisar rolar a pagina pra achar um atalho redundante. */}
          <div className="md:hidden">
            <p className="text-sm font-medium text-fg/65 mb-3">Acesso rápido</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {ATALHOS.map((a) => (
                <Link
                  key={a.href}
                  href={a.href}
                  className="flex items-center justify-between gap-3 bg-surface rounded-3xl border border-border-strong shadow-theme-xs p-5 hover:border-acento-claro/40 transition-colors"
                >
                  <div>
                    <p className="font-display text-sm font-bold text-fg">{a.label}</p>
                    <p className="text-sm text-fg/65 mt-0.5">{a.descricao}</p>
                  </div>
                  <span className="text-acento-claro shrink-0">→</span>
                </Link>
              ))}
            </div>
          </div>
        </>
      )}
    </AppShell>
  );
}
