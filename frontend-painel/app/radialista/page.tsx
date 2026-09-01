"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "../../components/AppShell";
import { apiFetch, ApiError } from "../../lib/api";
import { ConfiguracaoIA, Programa, Radialista, RadioPerfil, TipoRadio } from "../../lib/types";
import { setRadialistaAtualId } from "../../lib/radialistas";
import { LocufySpin } from "../../components/LocufyLogo";
import { PRECO_AGENTE_ADICIONAL, formatarReais } from "../../lib/planos";

export default function RadialistasPage() {
  const [radialistas, setRadialistas] = useState<Radialista[]>([]);
  const [programasPorRadialista, setProgramasPorRadialista] = useState<Record<number, Programa[]>>({});
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");
  const [mensagemUpgrade, setMensagemUpgrade] = useState("");
  const [modalIAAberto, setModalIAAberto] = useState(false);
  const [descricaoIA, setDescricaoIA] = useState("");
  const [gerandoIA, setGerandoIA] = useState(false);
  const [erroIA, setErroIA] = useState("");
  const [comprandoAgenteExtra, setComprandoAgenteExtra] = useState(false);
  const [erroCompraAgenteExtra, setErroCompraAgenteExtra] = useState("");
  const [tipoRadioConta, setTipoRadioConta] = useState("");
  const [tiposRadio, setTiposRadio] = useState<TipoRadio[]>([]);

  useEffect(() => {
    apiFetch<RadioPerfil>("/config/radio")
      .then((radio) => setTipoRadioConta(radio.tipo_radio))
      .catch(() => {});
    apiFetch<TipoRadio[]>("/config/tipos-radio")
      .then(setTiposRadio)
      .catch(() => {});
  }, []);

  const labelTipoRadioConta = tiposRadio.find((t) => t.value === tipoRadioConta)?.label;

  function carregar() {
    setCarregando(true);
    apiFetch<Radialista[]>("/config/radialistas")
      .then(async (lista) => {
        setRadialistas(lista);
        const entradas = await Promise.all(
          lista.map(async (r) => {
            try {
              const programas = await apiFetch<Programa[]>(`/config/radialistas/${r.id}/programas`);
              return [r.id, programas] as const;
            } catch {
              return [r.id, []] as const;
            }
          })
        );
        setProgramasPorRadialista(Object.fromEntries(entradas));
      })
      .catch((err) => setErro(err instanceof ApiError ? err.message : "Erro ao carregar radialistas"))
      .finally(() => setCarregando(false));
  }

  useEffect(() => {
    carregar();
  }, []);

  async function gerarRadialistaComIA() {
    if (!descricaoIA.trim() && !tipoRadioConta) return;
    setGerandoIA(true);
    setErroIA("");
    try {
      const criado = await apiFetch<ConfiguracaoIA>("/config/radialistas/gerar-ia", {
        method: "POST",
        body: JSON.stringify({ descricao: descricaoIA.trim() }),
      });
      setRadialistaAtualId(criado.radialista.id);
      window.location.href = `/radialista/${criado.radialista.id}`;
    } catch (err) {
      if (err instanceof ApiError && err.status === 402) {
        setModalIAAberto(false);
        setMensagemUpgrade(err.message);
      } else {
        setErroIA(err instanceof ApiError ? err.message : "Erro ao gerar configuração com IA");
      }
      setGerandoIA(false);
    }
  }

  async function comprarAgenteExtra() {
    setComprandoAgenteExtra(true);
    setErroCompraAgenteExtra("");
    try {
      const { url } = await apiFetch<{ url: string }>("/billing/agentes-extras/checkout", { method: "POST" });
      window.location.href = url;
    } catch (err) {
      setErroCompraAgenteExtra(err instanceof ApiError ? err.message : "Erro ao iniciar compra");
      setComprandoAgenteExtra(false);
    }
  }

  return (
    <AppShell title="Radialistas" maxWidthClassName="max-w-4xl">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-5">
        <p className="text-sm text-fg/65">
          Seus locutores de IA. Clique num deles pra editar a persona, a voz e os programas.
        </p>
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={() => {
              setErroIA("");
              setDescricaoIA("");
              setModalIAAberto(true);
            }}
            className="rounded-lg border border-amber/40 px-4 py-2.5 text-sm font-medium text-amber-text hover:bg-amber/10 whitespace-nowrap"
          >
            ✨ Gerar com IA
          </button>
          <Link
            href="/radialista/novo"
            className="rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-ink hover:bg-brand-600 whitespace-nowrap"
          >
            + Novo radialista
          </Link>
        </div>
      </div>

      {erro && <p className="text-sm text-rust-text mb-4">{erro}</p>}

      {carregando ? (
        <p className="flex items-center gap-2 text-sm text-fg/65">
          <LocufySpin size={16} /> Carregando...
        </p>
      ) : radialistas.length === 0 ? (
        <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6">
          <p className="text-sm text-fg/65">Nenhum radialista ainda. Crie o primeiro para começar.</p>
          <p className="text-sm text-fg/65 mt-1">Depois, você cria os programas dele e conecta o WhatsApp.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {radialistas.map((r) => {
            const programas = programasPorRadialista[r.id] ?? [];
            const ativos = programas.filter((p) => p.ativo).length;
            return (
              <Link
                key={r.id}
                href={`/radialista/${r.id}`}
                onClick={() => setRadialistaAtualId(r.id)}
                className="flex items-center justify-between gap-3 bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-5 hover:border-amber/40 transition-colors"
              >
                <div>
                  <h2 className="font-display text-base font-bold text-fg">{r.nome_locutor || `Radialista #${r.id}`}</h2>
                  <p className="text-xs text-fg/65 mt-1">
                    Atende pelo WhatsApp da rádio ·{" "}
                    {programas.length === 0
                      ? "nenhum programa cadastrado"
                      : `${ativos} programa${ativos === 1 ? "" : "s"} ativo${ativos === 1 ? "" : "s"}${
                          programas.length > ativos ? ` (${programas.length - ativos} pausado${programas.length - ativos === 1 ? "" : "s"})` : ""
                        }`}
                  </p>
                </div>
                <span className="text-xs font-medium text-amber-text shrink-0">Editar →</span>
              </Link>
            );
          })}
        </div>
      )}

      {modalIAAberto && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/50 px-4"
          onClick={() => !gerandoIA && setModalIAAberto(false)}
        >
          <div
            className="w-full max-w-lg rounded-2xl border border-border-strong bg-surface p-6 shadow-theme-xs"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="font-display text-base font-bold text-fg mb-2">Gerar radialista com IA</h2>
            <p className="text-sm text-fg/70 mb-4">
              Descreva o gênero musical, o tom e o público do programa. A IA preenche a persona do
              locutor, os tópicos, a estrutura de blocos e todo o resto — depois é só revisar e ajustar.
            </p>
            {tipoRadioConta ? (
              <p className="text-xs font-medium text-amber-text bg-amber/10 rounded-lg px-3 py-2 mb-3">
                Baseado no perfil: {labelTipoRadioConta ?? tipoRadioConta}
              </p>
            ) : (
              <p className="text-xs text-fg/65 bg-paper/5 rounded-lg px-3 py-2 mb-3">
                Nenhum tipo de rádio configurado — a IA vai depender só da descrição.{" "}
                <Link href="/configuracoes" className="font-medium text-amber-text hover:underline">
                  Configurar tipo de rádio →
                </Link>
              </p>
            )}
            <textarea
              value={descricaoIA}
              onChange={(e) => setDescricaoIA(e.target.value)}
              disabled={gerandoIA}
              rows={4}
              placeholder="Descrição (opcional). Ex: programa de manhã, mais animado, com bloco de recado"
              className="w-full rounded-lg border border-border-strong bg-bg px-3 py-2.5 text-sm text-fg placeholder:text-fg/65 focus:outline-none focus:ring-2 focus:ring-amber/40 disabled:opacity-60"
            />
            {erroIA && <p className="text-sm text-rust-text mt-2">{erroIA}</p>}
            <div className="flex justify-end gap-3 mt-5">
              <button
                type="button"
                onClick={() => setModalIAAberto(false)}
                disabled={gerandoIA}
                className="rounded-lg px-4 py-2.5 text-sm font-medium text-fg/60 hover:text-fg disabled:opacity-60"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={gerarRadialistaComIA}
                disabled={gerandoIA || (!descricaoIA.trim() && !tipoRadioConta)}
                className="rounded-lg bg-amber px-4 py-2.5 text-sm font-medium text-ink hover:bg-amber/90 disabled:opacity-60"
              >
                {gerandoIA ? "Gerando..." : "Gerar"}
              </button>
            </div>
          </div>
        </div>
      )}

      {mensagemUpgrade && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/50 px-4"
          onClick={() => setMensagemUpgrade("")}
        >
          <div
            className="w-full max-w-sm rounded-2xl border border-border-strong bg-surface p-6 shadow-theme-xs"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="font-display text-base font-bold text-fg mb-2">Limite de agentes atingido</h2>
            <p className="text-sm text-fg/70 mb-5">{mensagemUpgrade}</p>
            <p className="text-sm text-fg/70 mb-5">
              Adicione este agente agora por{" "}
              <span className="font-semibold text-fg">R$ {formatarReais(PRECO_AGENTE_ADICIONAL)}/mês</span>, sem
              trocar de plano — ele entra no ar assim que o pagamento confirmar.
            </p>
            {erroCompraAgenteExtra && <p className="text-sm text-rust-text mb-3">{erroCompraAgenteExtra}</p>}
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setMensagemUpgrade("")}
                disabled={comprandoAgenteExtra}
                className="rounded-lg px-4 py-2.5 text-sm font-medium text-fg/60 hover:text-fg disabled:opacity-60"
              >
                Fechar
              </button>
              <Link
                href="/billing"
                className="rounded-lg border border-border-strong px-4 py-2.5 text-sm font-medium text-fg hover:bg-paper/10"
              >
                Ver planos
              </Link>
              <button
                type="button"
                onClick={comprarAgenteExtra}
                disabled={comprandoAgenteExtra}
                className="flex items-center gap-2 rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-ink hover:bg-brand-600 disabled:opacity-60"
              >
                {comprandoAgenteExtra ? (
                  <>
                    <LocufySpin size={14} /> Redirecionando...
                  </>
                ) : (
                  "Adicionar agente extra"
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
