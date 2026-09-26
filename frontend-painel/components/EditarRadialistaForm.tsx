"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import ConfirmDialog from "./ConfirmDialog";
import { AvisoPagamento } from "./AssinaturaGate";
import VoiceSelect from "./VoiceSelect";
import TagInput from "./TagInput";
import { apiFetch, ApiError } from "../lib/api";
import { setRadialistaAtualId } from "../lib/radialistas";
import { invalidarConfiguracaoInicial } from "../lib/useConfiguracaoInicial";
import { DIAS_SEMANA_LABEL, RADIALISTA_VAZIO, Programa, Radialista } from "../lib/types";
import { LocufySpin } from "./LocufyLogo";
import { useAvisoAlteracoes } from "../lib/useAvisoAlteracoes";

const inputClass =
  "w-full rounded-xl border border-border-strong bg-bg px-3 py-2 text-sm text-fg placeholder:text-fg/65 focus:outline-none focus:border-acento-claro/50 focus:ring-2 focus:ring-acento-claro/20";
const labelClass = "block text-sm font-medium text-fg/80 mb-1.5";

// Fusos horários do Brasil pós-2019 (sem horário de verão) -- ver Radialista.timezone,
// usado por useLiveEngine pra decidir se o programa está no ar.
const TIMEZONES_BRASIL = [
  { value: "America/Noronha", label: "Fernando de Noronha (UTC-2)" },
  { value: "America/Sao_Paulo", label: "Brasília (UTC-3)" },
  { value: "America/Manaus", label: "Manaus/Cuiabá (UTC-4)" },
  { value: "America/Rio_Branco", label: "Acre (UTC-5)" },
];

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
  const [mensagemPagamento, setMensagemPagamento] = useState("");
  // Última versão salva/carregada -- diferença em relação a `config` = alteração pendente.
  const [original, setOriginal] = useState("");

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
      const vazio = { id: 0, ativo: true, ...RADIALISTA_VAZIO };
      setConfig(vazio);
      setOriginal(JSON.stringify(vazio));
      setProgramas([]);
      setCarregando(false);
      return;
    }
    setRadialistaAtualId(idEfetivo);
    setCarregando(true);
    apiFetch<Radialista>(`/config/radialistas/${idEfetivo}`)
      .then((r) => {
        setConfig(r);
        setOriginal(JSON.stringify(r));
      })
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
      setOriginal(JSON.stringify(atualizado));
      setMensagem(criando ? "Radialista criado." : "Configuração salva.");
      invalidarConfiguracaoInicial();
      onSalvo?.(atualizado);
    } catch (err) {
      if (err instanceof ApiError && err.status === 402) {
        setMensagemPagamento(err.message);
      } else {
        setErro(err instanceof ApiError ? err.message : "Erro ao salvar");
      }
    } finally {
      setSalvando(false);
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

  const alteracoesPendentes = config !== null && original !== "" && JSON.stringify(config) !== original;
  useAvisoAlteracoes(alteracoesPendentes);

  if (carregando) {
    return (
      <p className="flex items-center gap-2 text-sm text-fg/65">
        <LocufySpin size={16} /> Carregando…
      </p>
    );
  }

  if (!config) {
    return <p className="text-sm text-laranja">{erro || "Radialista não encontrado."}</p>;
  }

  return (
    <div className="space-y-5">
      {erro && <p role="alert" className="text-sm text-laranja">{erro}</p>}
      {mensagem && <p role="status" className="text-sm text-ciano">{mensagem}</p>}

      <div className="bg-surface rounded-3xl border border-border-strong shadow-theme-xs p-6">
        <div className="flex flex-col gap-1 mb-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="font-display text-base font-bold text-fg">
              {criando ? "Novo radialista" : "Identidade do radialista"}
            </h2>
            <p className="text-sm text-fg/65">
              Atende pelo WhatsApp da rádio.{" "}
              <Link href="/configuracoes#whatsapp" className="text-acento-claro underline hover:text-acento-dim">
                Gerenciar conexão
              </Link>
            </p>
          </div>
          {!criando && (
            <button
              type="button"
              onClick={() => setConfirmandoExclusaoRadialista(true)}
              className="text-xs font-medium text-laranja hover:text-laranja/80 self-start sm:self-auto"
            >
              Excluir radialista
            </button>
          )}
        </div>

        <form onSubmit={salvar} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label htmlFor="radialista-nome" className={labelClass}>Nome do radialista</label>
              <input
                id="radialista-nome"
                autoComplete="off"
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
            <label htmlFor="radialista-fuso" className={labelClass}>Fuso horário</label>
            <select
              id="radialista-fuso"
              className={inputClass}
              value={config.timezone}
              onChange={(e) => setConfig({ ...config, timezone: e.target.value })}
            >
              {TIMEZONES_BRASIL.map((tz) => (
                <option key={tz.value} value={tz.value}>
                  {tz.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="radialista-personalidade" className={labelClass}>Personalidade</label>
            <textarea
              id="radialista-personalidade"
              className={inputClass}
              rows={4}
              placeholder="Descreva como o radialista deve se comportar: personalidade, características, jeito de falar, humor…"
              value={config.personalidade}
              onChange={(e) => setConfig({ ...config, personalidade: e.target.value })}
            />
          </div>
          <div>
            <label htmlFor="radialista-biografia" className={labelClass}>Biografia</label>
            <textarea
              id="radialista-biografia"
              className={inputClass}
              rows={3}
              placeholder="Poucos fatos pessoais fixos: de onde é, há quanto tempo trabalha na rádio, time que torce, hobby. Não mudam entre programas…"
              value={config.biografia}
              onChange={(e) => setConfig({ ...config, biografia: e.target.value })}
            />
          </div>
          <TagInput
            label="Traços marcantes (1 ou 2 marcas registradas: implicância boba, piada interna)"
            tags={config.tracos_marcantes}
            onChange={(tags) => setConfig({ ...config, tracos_marcantes: tags })}
          />
          <TagInput
            label="Fatos do dia (um é sorteado a cada transmissão, ex.: “hoje eu vim de bicicleta”)"
            tags={config.fatos_do_dia}
            onChange={(tags) => setConfig({ ...config, fatos_do_dia: tags })}
          />
          <label className="inline-flex items-center gap-2 text-sm font-medium text-fg/80">
            <input
              type="checkbox"
              checked={config.resposta_automatica_whatsapp}
              onChange={(e) => setConfig({ ...config, resposta_automatica_whatsapp: e.target.checked })}
              className="h-4 w-4 rounded border-border-strong bg-bg text-acento-claro focus:ring-acento-claro/40"
            />
            Responder automaticamente no WhatsApp
          </label>
          <div className="sticky bottom-0 -mx-6 -mb-6 flex items-center gap-3 rounded-b-3xl border-t border-border bg-surface/95 px-6 py-3 backdrop-blur">
            <button
              type="submit"
              disabled={salvando}
              className="rounded-xl bg-brand-500 px-4 py-2.5 text-sm font-medium text-on-brand hover:bg-brand-600 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {salvando ? "Salvando…" : criando ? "Criar radialista" : "Salvar radialista"}
            </button>
            {alteracoesPendentes && <span className="text-xs text-laranja">Alterações não salvas</span>}
          </div>
        </form>
      </div>

      {criando ? (
        <div className="bg-surface rounded-3xl border border-border-strong shadow-theme-xs p-6">
          <h2 className="font-display text-base font-bold text-fg mb-1">Programação</h2>
          <p className="text-sm text-fg/65">Salve o radialista para cadastrar os programas dele.</p>
        </div>
      ) : (
        <div className="bg-surface rounded-3xl border border-border-strong shadow-theme-xs p-6">
          <div className="flex items-center justify-between mb-1">
            <h2 className="font-display text-base font-bold text-fg">Programação</h2>
            <button
              type="button"
              onClick={abrirNovoPrograma}
              className="text-sm font-medium text-acento-claro hover:text-acento-dim"
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
                  className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-border-strong px-3 py-2.5"
                >
                  {onAbrirPrograma ? (
                    <button type="button" onClick={() => onAbrirPrograma(p.id)} className="min-w-0 text-left">
                      <p className="text-sm font-medium text-fg hover:text-acento-claro">{p.nome}</p>
                      <p className="text-xs text-fg/65 font-mono">
                        {formatarDias(p.dias_semana, p.data_especifica)} · {p.horario_inicio.slice(0, 5)} às{" "}
                        {p.horario_fim.slice(0, 5)}
                        {!p.ativo && " · pausado"}
                      </p>
                    </button>
                  ) : (
                    <Link href={`/radialista/${idEfetivo}/programas/${p.id}`} className="min-w-0">
                      <p className="text-sm font-medium text-fg hover:text-acento-claro">{p.nome}</p>
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
                        className="text-xs font-medium text-acento-claro hover:text-acento-dim"
                      >
                        Editar
                      </button>
                    ) : (
                      <Link
                        href={`/radialista/${idEfetivo}/programas/${p.id}`}
                        className="text-xs font-medium text-acento-claro hover:text-acento-dim"
                      >
                        Editar
                      </Link>
                    )}
                    <button
                      type="button"
                      onClick={() => setProgramaParaExcluir(p)}
                      className="text-xs font-medium text-laranja hover:text-laranja/80"
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

      {mensagemPagamento && (
        <AvisoPagamento mensagem={mensagemPagamento} onClose={() => setMensagemPagamento("")} />
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
