"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import ConfirmDialog from "./ConfirmDialog";
import VoiceSelect from "./VoiceSelect";
import { apiFetch, ApiError } from "../lib/api";
import { setRadialistaAtualId } from "../lib/radialistas";
import { invalidarConfiguracaoInicial } from "../lib/useConfiguracaoInicial";
import { DIAS_SEMANA_LABEL, RADIALISTA_VAZIO, Programa, Radialista } from "../lib/types";
import { LocufySpin } from "./LocufyLogo";
import { PRECO_AGENTE_ADICIONAL, formatarReais } from "../lib/planos";

const inputClass =
  "w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg placeholder:text-fg/65 focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20";
const labelClass = "block text-sm font-medium text-fg/80 mb-1.5";

function semCamposSistema(r: Radialista) {
  const { id, ativo, ...dados } = r;
  return dados;
}

function formatarDias(dias: number[], dataEspecifica?: string | null): string {
  if (dataEspecifica) return `Avulso em ${dataEspecifica.split("-").reverse().join("/")}`;
  if (dias.length === 0) return "Todos os dias";
  return dias.map((d) => DIAS_SEMANA_LABEL[d]).join(", ");
}

type EditarRadialistaFormProps = {
  /** null = formulario de criacao -- so faz POST quando o usuario clica em Salvar. */
  radialistaId: number | null;
  onSalvo?: (radialista: Radialista) => void;
  onExcluido?: () => void;
  /** quando definido, "Editar"/nome do programa e "+ Novo programa" chamam isso em vez de navegar.
   * programaId null significa "abrir formulario de criacao de programa". */
  onAbrirPrograma?: (programaId: number | null) => void;
};

export default function EditarRadialistaForm({
  radialistaId,
  onSalvo,
  onExcluido,
  onAbrirPrograma,
}: EditarRadialistaFormProps) {
  const [config, setConfig] = useState<Radialista | null>(null);
  const [programas, setProgramas] = useState<Programa[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [mensagem, setMensagem] = useState("");
  const [erro, setErro] = useState("");
  const [confirmandoExclusaoRadialista, setConfirmandoExclusaoRadialista] = useState(false);
  const [programaParaExcluir, setProgramaParaExcluir] = useState<Programa | null>(null);
  const [mensagemLimiteAgentes, setMensagemLimiteAgentes] = useState("");
  const [comprandoAgenteExtra, setComprandoAgenteExtra] = useState(false);
  const [erroCompraAgenteExtra, setErroCompraAgenteExtra] = useState("");

  // Depois que o POST de criacao roda (dentro de salvar()), guarda o id criado aqui --
  // radialistaId (prop) continua null enquanto o pai (pagina/modal) nao navegar/atualizar,
  // entao o formulario passa a se comportar como edicao sem depender disso.
  const [idCriado, setIdCriado] = useState<number | null>(null);
  const idEfetivo = radialistaId ?? idCriado;
  const criando = idEfetivo === null;

  function carregarProgramas() {
    if (idEfetivo === null) return;
    apiFetch<Programa[]>(`/config/radialistas/${idEfetivo}/programas`)
      .then(setProgramas)
      .catch(() => setProgramas([]));
  }

  useEffect(() => {
    if (idEfetivo === null) {
      setConfig({ id: 0, ativo: true, ...RADIALISTA_VAZIO });
      setProgramas([]);
      setCarregando(false);
      return;
    }
    setRadialistaAtualId(idEfetivo);
    setCarregando(true);
    apiFetch<Radialista>(`/config/radialistas/${idEfetivo}`)
      .then(setConfig)
      .catch((err) => setErro(err instanceof ApiError ? err.message : "Erro ao carregar radialista"))
      .finally(() => setCarregando(false));
    carregarProgramas();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idEfetivo]);

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    if (!config) return;
    setSalvando(true);
    setErro("");
    setMensagem("");
    try {
      const atualizado = criando
        ? await apiFetch<Radialista>("/config/radialistas", {
            method: "POST",
            body: JSON.stringify(semCamposSistema(config)),
          })
        : await apiFetch<Radialista>(`/config/radialistas/${idEfetivo}`, {
            method: "PUT",
            body: JSON.stringify(semCamposSistema(config)),
          });
      if (criando) {
        setIdCriado(atualizado.id);
        setRadialistaAtualId(atualizado.id);
      }
      setConfig(atualizado);
      setMensagem(criando ? "Radialista criado." : "Configuração salva.");
      invalidarConfiguracaoInicial();
      onSalvo?.(atualizado);
    } catch (err) {
      if (criando && err instanceof ApiError && err.status === 402) {
        setMensagemLimiteAgentes(err.message);
      } else {
        setErro(err instanceof ApiError ? err.message : "Erro ao salvar");
      }
    } finally {
      setSalvando(false);
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

  async function excluirRadialista() {
    if (!config || idEfetivo === null) return;
    try {
      await apiFetch(`/config/radialistas/${idEfetivo}`, { method: "DELETE" });
      invalidarConfiguracaoInicial();
      onExcluido?.();
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao excluir radialista");
    } finally {
      setConfirmandoExclusaoRadialista(false);
    }
  }

  function abrirNovoPrograma() {
    if (idEfetivo === null) return;
    if (onAbrirPrograma) {
      onAbrirPrograma(null);
    } else {
      window.location.href = `/radialista/${idEfetivo}/programas/novo`;
    }
  }

  async function excluirPrograma(programa: Programa) {
    try {
      await apiFetch(`/config/programas/${programa.id}`, { method: "DELETE" });
      invalidarConfiguracaoInicial();
      carregarProgramas();
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao excluir programa");
    } finally {
      setProgramaParaExcluir(null);
    }
  }

  if (carregando) {
    return (
      <p className="flex items-center gap-2 text-sm text-fg/65">
        <LocufySpin size={16} /> Carregando...
      </p>
    );
  }

  if (!config) {
    return <p className="text-sm text-rust-text">{erro || "Radialista não encontrado."}</p>;
  }

  return (
    <div className="space-y-5">
      {erro && <p className="text-sm text-rust-text">{erro}</p>}
      {mensagem && <p className="text-sm text-teal-text">{mensagem}</p>}

      <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6">
        <div className="flex flex-col gap-1 mb-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="font-display text-base font-bold text-fg">
              {criando ? "Novo radialista" : "Identidade do locutor"}
            </h2>
            <p className="text-sm text-fg/65">
              Atende pelo WhatsApp da rádio.{" "}
              <Link href="/conversas" className="text-amber-text hover:underline">
                Gerenciar conexão
              </Link>
            </p>
          </div>
          {!criando && (
            <button
              type="button"
              onClick={() => setConfirmandoExclusaoRadialista(true)}
              className="text-xs font-medium text-rust-text hover:text-rust/80 self-start sm:self-auto"
            >
              Excluir radialista
            </button>
          )}
        </div>

        <form onSubmit={salvar} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className={labelClass}>Nome do locutor</label>
              <input
                className={inputClass}
                value={config.nome_locutor}
                onChange={(e) => setConfig({ ...config, nome_locutor: e.target.value })}
              />
            </div>
            <div>
              <label className={labelClass}>Voz</label>
              <VoiceSelect value={config.voz_id} onChange={(vozId) => setConfig({ ...config, voz_id: vozId })} />
            </div>
          </div>
          <div>
            <label className={labelClass}>Personalidade</label>
            <textarea
              className={inputClass}
              rows={4}
              placeholder="Descreva como o locutor deve se comportar: personalidade, características, jeito de falar, humor, etc."
              value={config.personalidade}
              onChange={(e) => setConfig({ ...config, personalidade: e.target.value })}
            />
          </div>
          <label className="inline-flex items-center gap-2 text-sm font-medium text-fg/80">
            <input
              type="checkbox"
              checked={config.resposta_automatica_whatsapp}
              onChange={(e) => setConfig({ ...config, resposta_automatica_whatsapp: e.target.checked })}
              className="h-4 w-4 rounded border-border-strong bg-bg text-amber-text focus:ring-amber/40"
            />
            Responder automaticamente no WhatsApp
          </label>
          <div className="pt-2">
            <button
              type="submit"
              disabled={salvando}
              className="rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-ink hover:bg-brand-600 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {salvando ? "Salvando..." : "Salvar"}
            </button>
          </div>
        </form>
      </div>

      {criando ? (
        <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6">
          <h2 className="font-display text-base font-bold text-fg mb-1">Programação</h2>
          <p className="text-sm text-fg/65">Salve o radialista pra poder cadastrar os programas dele.</p>
        </div>
      ) : (
        <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6">
          <div className="flex items-center justify-between mb-1">
            <h2 className="font-display text-base font-bold text-fg">Programação</h2>
            <button
              type="button"
              onClick={abrirNovoPrograma}
              className="text-sm font-medium text-amber-text hover:text-amber-dim"
            >
              + Novo programa
            </button>
          </div>
          <p className="text-sm text-fg/65 mb-5">
            Cada programa tem seu próprio tom, tópicos, músicas, notícias e regras de pesquisa, além do horário em que
            vai ao ar.
          </p>

          {programas.length === 0 ? (
            <p className="text-sm text-fg/65">Nenhum programa cadastrado ainda.</p>
          ) : (
            <div className="space-y-2">
              {programas.map((p) => (
                <div
                  key={p.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border-strong px-3 py-2.5"
                >
                  {onAbrirPrograma ? (
                    <button type="button" onClick={() => onAbrirPrograma(p.id)} className="min-w-0 text-left">
                      <p className="text-sm font-medium text-fg hover:text-amber-text">{p.nome}</p>
                      <p className="text-xs text-fg/65 font-mono">
                        {formatarDias(p.dias_semana, p.data_especifica)} · {p.horario_inicio.slice(0, 5)} às{" "}
                        {p.horario_fim.slice(0, 5)}
                        {!p.ativo && " · pausado"}
                      </p>
                    </button>
                  ) : (
                    <Link href={`/radialista/${idEfetivo}/programas/${p.id}`} className="min-w-0">
                      <p className="text-sm font-medium text-fg hover:text-amber-text">{p.nome}</p>
                      <p className="text-xs text-fg/65 font-mono">
                        {formatarDias(p.dias_semana, p.data_especifica)} · {p.horario_inicio.slice(0, 5)} às{" "}
                        {p.horario_fim.slice(0, 5)}
                        {!p.ativo && " · pausado"}
                      </p>
                    </Link>
                  )}
                  <div className="flex items-center gap-3 shrink-0">
                    {onAbrirPrograma ? (
                      <button
                        type="button"
                        onClick={() => onAbrirPrograma(p.id)}
                        className="text-xs font-medium text-amber-text hover:text-amber-dim"
                      >
                        Editar
                      </button>
                    ) : (
                      <Link
                        href={`/radialista/${idEfetivo}/programas/${p.id}`}
                        className="text-xs font-medium text-amber-text hover:text-amber-dim"
                      >
                        Editar
                      </Link>
                    )}
                    <button
                      type="button"
                      onClick={() => setProgramaParaExcluir(p)}
                      className="text-xs font-medium text-rust-text hover:text-rust/80"
                    >
                      Excluir
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {mensagemLimiteAgentes && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/50 px-4"
          onClick={() => !comprandoAgenteExtra && setMensagemLimiteAgentes("")}
        >
          <div
            className="w-full max-w-sm rounded-2xl border border-border-strong bg-surface p-6 shadow-theme-xs"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="font-display text-base font-bold text-fg mb-2">Limite de agentes atingido</h2>
            <p className="text-sm text-fg/70 mb-5">{mensagemLimiteAgentes}</p>
            <p className="text-sm text-fg/70 mb-5">
              Adicione este agente agora por{" "}
              <span className="font-semibold text-fg">R$ {formatarReais(PRECO_AGENTE_ADICIONAL)}/mês</span>, sem
              trocar de plano — ele entra no ar assim que o pagamento confirmar.
            </p>
            {erroCompraAgenteExtra && <p className="text-sm text-rust-text mb-3">{erroCompraAgenteExtra}</p>}
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setMensagemLimiteAgentes("")}
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

      <ConfirmDialog
        open={confirmandoExclusaoRadialista}
        title="Excluir radialista"
        mensagem={`Excluir o radialista "${config.nome_locutor}"? Essa ação não pode ser desfeita.`}
        onConfirmar={excluirRadialista}
        onCancelar={() => setConfirmandoExclusaoRadialista(false)}
      />
      <ConfirmDialog
        open={programaParaExcluir !== null}
        title="Excluir programa"
        mensagem={`Excluir o programa "${programaParaExcluir?.nome}"?`}
        onConfirmar={() => programaParaExcluir && excluirPrograma(programaParaExcluir)}
        onCancelar={() => setProgramaParaExcluir(null)}
      />
    </div>
  );
}
