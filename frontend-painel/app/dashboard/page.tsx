"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "../../components/AppShell";
import { apiFetch, ApiError } from "../../lib/api";
import { Conta, Patrocinador, Programa, Radialista, RadioConta } from "../../lib/types";
import { LocufyLed, LocufySpin } from "../../components/LocufyLogo";
import { GraficoBarras, PontoSerie } from "../../components/GraficoBarras";
import { UpsellBanner } from "../../components/UpsellBanner";

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
    descricao: "Plano e cobrança",
  },
  {
    href: "/perfil",
    label: "Perfil",
    descricao: "Dados da conta",
  },
];

type NoArResponse = {
  no_ar: boolean;
  radialista_id: number | null;
  radialista_nome: string | null;
  programa_id: number | null;
  programa_nome: string | null;
};

const INTERVALO_NO_AR_MS = 30_000;

export default function DashboardPage() {
  const [conta, setConta] = useState<Conta | null>(null);
  const [radialistas, setRadialistas] = useState<Radialista[]>([]);
  const [radioConta, setRadioConta] = useState<RadioConta | null>(null);
  const [programas, setProgramas] = useState<Programa[]>([]);
  const [patrocinadores, setPatrocinadores] = useState<Patrocinador[]>([]);
  const [noAr, setNoAr] = useState<NoArResponse | null>(null);
  const [mensagens7Dias, setMensagens7Dias] = useState<number | null>(null);
  const [mensagensPorDia, setMensagensPorDia] = useState<PontoSerie[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");
  const [onboardingIncompleto, setOnboardingIncompleto] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
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
    function buscarNoAr() {
      apiFetch<NoArResponse>("/live/no-ar")
        .then(setNoAr)
        .catch(() => {
          // ignora falha isolada, mantem o ultimo estado conhecido
        });
    }

    buscarNoAr();
    const intervalo = setInterval(buscarNoAr, INTERVALO_NO_AR_MS);
    return () => clearInterval(intervalo);
  }, []);

  const whatsappConectado = Boolean(radioConta?.wuzapi_token);
  const perfilPreenchido = Boolean(radioConta?.nome_radio && radioConta?.frequencia);
  const radialistasProntos = radialistas.filter((r) => r.ativo && r.voz_id).length;
  const temRadialistaPronto = radialistasProntos > 0;
  const programasAtivos = programas.filter((p) => p.ativo).length;
  const temProgramaAtivo = programasAtivos > 0;
  const patrocinadoresAtivos = patrocinadores.filter((p) => p.ativo).length;
  const temPatrocinador = patrocinadoresAtivos > 0;
  // "no ar" pela janela de horario do programa nao basta -- sem WhatsApp conectado nao tem
  // ouvinte de verdade podendo falar com o radialista, entao nao e' "ao vivo" de fato ainda.
  const realmenteNoAr = Boolean(noAr?.no_ar) && whatsappConectado;

  const TAREFAS_AO_VIVO = [
    {
      feita: perfilPreenchido,
      label: "Preencher dados da rádio",
      descricao: "Nome e frequência da rádio configurados",
      href: "/configuracoes",
    },
    {
      feita: temRadialistaPronto,
      label: "Cadastrar radialista",
      descricao: "Locutor ativo com voz definida",
      href: "/radialista",
    },
    {
      feita: temProgramaAtivo,
      label: "Cadastrar programa",
      descricao: "Ao menos um programa ativo na grade",
      href: "/programas",
    },
    {
      feita: whatsappConectado,
      label: "Conectar WhatsApp",
      descricao: "Número da rádio conectado para receber pedidos",
      href: "/conversas",
    },
    {
      feita: temPatrocinador,
      label: "Cadastrar Vinhetagem",
      descricao: "Opcional — para inserir chamadas comerciais no ar",
      href: "/vinhetagem",
      opcional: true,
    },
  ];
  const pendentes = TAREFAS_AO_VIVO.filter((t) => !t.feita && !t.opcional).length;

  return (
    <AppShell title="Dashboard" maxWidthClassName="max-w-4xl">
      {erro && <p className="text-sm text-rust-text mb-4">{erro}</p>}

      <UpsellBanner />

      {onboardingIncompleto && (
        <div className="flex items-start justify-between gap-4 rounded-2xl border border-amber/40 bg-amber/10 px-5 py-4 mb-6">
          <div>
            <p className="text-sm font-medium text-fg">Sua conta foi criada, mas a assinatura ainda não foi confirmada.</p>
            <p className="text-sm text-fg/65 mt-0.5">
              Alguns dados podem não ter sido salvos.{" "}
              <Link href="/billing" className="text-amber-text hover:text-amber-dim font-medium">
                Finalizar assinatura
              </Link>
              {" "}· revise também{" "}
              <Link href="/configuracoes" className="text-amber-text hover:text-amber-dim font-medium">
                Configurações
              </Link>
              {" "}e{" "}
              <Link href="/radialista" className="text-amber-text hover:text-amber-dim font-medium">
                Radialistas
              </Link>
              .
            </p>
          </div>
          <button
            type="button"
            onClick={() => setOnboardingIncompleto(false)}
            aria-label="Dispensar aviso"
            className="shrink-0 text-fg/50 hover:text-fg"
          >
            ✕
          </button>
        </div>
      )}

      {carregando ? (
        <p className="flex items-center gap-2 text-sm text-fg/65">
          <LocufySpin size={16} /> Carregando...
        </p>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-5">
              <p className="text-xs font-medium uppercase tracking-wide text-fg/65 mb-1">Radialistas</p>
              <p className="font-display text-2xl font-bold text-fg">{radialistas.length}</p>
              <p className="text-xs text-fg/65 mt-0.5">
                {radialistasProntos} pronto{radialistasProntos === 1 ? "" : "s"} com voz definida
              </p>
            </div>
            <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-5">
              <p className="text-xs font-medium uppercase tracking-wide text-fg/65 mb-1">WhatsApp da rádio</p>
              <p className="flex items-center gap-2 font-display text-2xl font-bold text-fg">
                <LocufyLed color={whatsappConectado ? "teal" : "amber"} pulse={false} />
                {whatsappConectado ? "Conectado" : "Não conectado"}
              </p>
            </div>
            <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-5">
              <p className="text-xs font-medium uppercase tracking-wide text-fg/65 mb-1">No ar agora</p>
              {realmenteNoAr ? (
                <>
                  <p className="flex items-center gap-2 font-display text-2xl font-bold text-fg truncate">
                    <LocufyLed color="rust" pulse /> {noAr!.radialista_nome}
                  </p>
                  <p className="text-xs text-fg/65 mt-0.5 truncate">{noAr!.programa_nome}</p>
                </>
              ) : (
                <p className="flex items-center gap-2 font-display text-2xl font-bold text-fg/65">
                  <LocufyLed color="amber" pulse={false} /> Ninguém
                </p>
              )}
            </div>
            <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-5">
              <p className="text-xs font-medium uppercase tracking-wide text-fg/65 mb-1">Plano</p>
              <p className="font-display text-2xl font-bold text-fg capitalize">{conta?.plano ?? "-"}</p>
              <p className="text-xs text-fg/65 mt-0.5 capitalize">{conta?.plano_status ?? ""}</p>
            </div>
            <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-5">
              <p className="text-xs font-medium uppercase tracking-wide text-fg/65 mb-1">Programas</p>
              <p className="font-display text-2xl font-bold text-fg">{programas.length}</p>
              <p className="text-xs text-fg/65 mt-0.5">
                {programasAtivos} ativo{programasAtivos === 1 ? "" : "s"} na grade
              </p>
            </div>
            <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-5">
              <p className="text-xs font-medium uppercase tracking-wide text-fg/65 mb-1">Vinhetagem</p>
              <p className="font-display text-2xl font-bold text-fg">{patrocinadores.length}</p>
              <p className="text-xs text-fg/65 mt-0.5">
                {patrocinadoresAtivos} patrocinador{patrocinadoresAtivos === 1 ? "" : "es"} ativo{patrocinadoresAtivos === 1 ? "" : "s"}
              </p>
            </div>
            <Link
              href="/metrics"
              className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-5 hover:border-amber/40 transition-colors"
            >
              <p className="text-xs font-medium uppercase tracking-wide text-fg/65 mb-1">Mensagens (7 dias)</p>
              <p className="font-display text-2xl font-bold text-fg">{mensagens7Dias ?? "-"}</p>
              <p className="text-xs text-fg/65 mt-0.5">Interações com ouvintes</p>
            </Link>
          </div>

          {mensagensPorDia.some((ponto) => ponto.total > 0) && (
            <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-5 mb-6">
              <div className="flex items-center justify-between mb-3">
                <p className="font-display text-sm font-bold text-fg">Mensagens por dia (últimos 30 dias)</p>
                <Link href="/metrics" className="text-xs font-medium text-amber-text hover:text-amber-dim">
                  Ver detalhes
                </Link>
              </div>
              <GraficoBarras serie={mensagensPorDia} />
            </div>
          )}

          <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-5 mb-6">
            <div className="flex items-center justify-between mb-3">
              <p className="font-display text-sm font-bold text-fg">Pronto para o ao vivo</p>
              <span className="text-xs font-medium text-fg/65">
                {pendentes === 0 ? "Tudo certo" : `${pendentes} pendente${pendentes > 1 ? "s" : ""}`}
              </span>
            </div>
            <ul className="flex flex-col gap-2.5">
              {TAREFAS_AO_VIVO.map((t) => (
                <li key={t.label}>
                  <Link href={t.href} className="flex items-start gap-3 group">
                    <span
                      className={`mt-0.5 shrink-0 w-4 h-4 rounded-full border flex items-center justify-center ${
                        t.feita ? "bg-teal border-teal text-ink" : "border-border-strong text-transparent"
                      }`}
                    >
                      <svg viewBox="0 0 16 16" width="10" height="10" fill="none" stroke="currentColor" strokeWidth="2.5">
                        <path d="M3 8l3 3 7-7" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    </span>
                    <span className="flex-1">
                      <span
                        className={`text-sm font-medium group-hover:text-amber-text transition-colors ${
                          t.feita ? "text-fg/65 line-through" : "text-fg"
                        }`}
                      >
                        {t.label}
                      </span>
                      <span className="block text-xs text-fg/65">{t.descricao}</span>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* So' em telas pequenas: no desktop a sidebar (sempre visivel) ja' cobre os
              mesmos destinos, sem precisar rolar a pagina pra achar um atalho redundante. */}
          <div className="md:hidden">
            <p className="text-sm font-medium text-fg/65 mb-3">Acesso rápido</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {ATALHOS.map((a) => (
                <Link
                  key={a.href}
                  href={a.href}
                  className="flex items-center justify-between gap-3 bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-5 hover:border-amber/40 transition-colors"
                >
                  <div>
                    <p className="font-display text-sm font-bold text-fg">{a.label}</p>
                    <p className="text-sm text-fg/65 mt-0.5">{a.descricao}</p>
                  </div>
                  <span className="text-amber-text shrink-0">→</span>
                </Link>
              ))}
            </div>
          </div>
        </>
      )}
    </AppShell>
  );
}
