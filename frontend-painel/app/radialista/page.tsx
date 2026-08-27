"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "../../components/AppShell";
import { apiFetch, ApiError } from "../../lib/api";
import { ConfiguracaoIA, DIAS_SEMANA_LABEL, Programa, Radialista } from "../../lib/types";
import { setRadialistaAtualId } from "../../lib/radialistas";
import { LocufySpin } from "../../components/LocufyLogo";
import { PRECO_AGENTE_ADICIONAL, formatarReais } from "../../lib/planos";

function formatarDias(dias: number[], dataEspecifica?: string | null): string {
  if (dataEspecifica) return `Avulso em ${dataEspecifica.split("-").reverse().join("/")}`;
  if (dias.length === 0) return "Todos os dias";
  return dias.map((d) => DIAS_SEMANA_LABEL[d]).join(", ");
}

export default function DashboardPage() {
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
    if (!descricaoIA.trim()) return;
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
      <div className="flex items-center justify-between mb-5">
        <p className="text-sm text-fg/65">Seus radialistas e a programação cadastrada de cada um.</p>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => {
              setErroIA("");
              setDescricaoIA("");
              setModalIAAberto(true);
            }}
            className="rounded-lg border border-amber/40 px-4 py-2.5 text-sm font-medium text-amber-text hover:bg-amber/10"
          >
            ✨ Gerar com IA
          </button>
          <Link
            href="/radialista/novo"
            className="rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-ink hover:bg-brand-600"
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
            return (
              <Link
                key={r.id}
                href={`/radialista/${r.id}`}
                onClick={() => setRadialistaAtualId(r.id)}
                className="block bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-5 hover:border-amber/40 transition-colors"
              >
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div>
                    <h2 className="font-display text-base font-bold text-fg">{r.nome_locutor || `Radialista #${r.id}`}</h2>
                    <p className="text-xs text-fg/65 mt-1">Atende pelo WhatsApp da rádio</p>
                  </div>
                  <span className="text-xs font-medium text-amber-text shrink-0">Editar →</span>
                </div>

                {programas.length === 0 ? (
                  <p className="text-sm text-fg/65">Nenhum programa cadastrado.</p>
                ) : (
                  <ul className="space-y-1.5">
                    {programas.map((p) => (
                      <li key={p.id} className="flex flex-wrap items-center gap-2 text-sm">
                        <span className={`font-medium ${p.ativo ? "text-fg" : "text-fg/65"}`}>{p.nome}</span>
                        <span className="text-xs text-fg/65 font-mono">
                          {formatarDias(p.dias_semana, p.data_especifica)} · {p.horario_inicio.slice(0, 5)} às{" "}
                          {p.horario_fim.slice(0, 5)}
                        </span>
                        {!p.ativo && (
                          <span className="rounded-full bg-paper/5 px-2 py-0.5 text-xs font-medium text-fg/65">
                            Pausado
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
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
            <textarea
              value={descricaoIA}
              onChange={(e) => setDescricaoIA(e.target.value)}
              disabled={gerandoIA}
              rows={4}
              placeholder="Ex: sertanejo, tom alegre e animado, programa de manhã pro público do interior"
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
                disabled={gerandoIA || !descricaoIA.trim()}
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
