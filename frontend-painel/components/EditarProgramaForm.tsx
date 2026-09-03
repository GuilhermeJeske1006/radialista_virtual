"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import ConfirmDialog from "./ConfirmDialog";
import TagInput from "./TagInput";
import RoteiroBlocosEditor from "./RoteiroBlocosEditor";
import RadialistasProgramaSection from "./RadialistasProgramaSection";
import { apiFetch, ApiError } from "../lib/api";
import {
  CategoriaVinheta,
  DIAS_SEMANA_LABEL,
  normalizarPrograma,
  Patrocinador,
  Programa,
  PROGRAMA_VAZIO,
  RadioPerfil,
  rotuloBloco,
  TipoRadio,
} from "../lib/types";
import { janelaSegundos } from "../lib/duracaoBloco";
import { BibliotecaAudioItem } from "../lib/bibliotecaAudio";
import { CORES_BLOCO, kindDoBloco } from "../lib/blocoVisual";
import { LocufySpin } from "./LocufyLogo";

const inputClass =
  "w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg placeholder:text-fg/65 focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20";
const labelClass = "block text-sm font-medium text-fg/80 mb-1.5";

function semCamposSistema(p: Programa) {
  const { id, radio_config_id, ...dados } = p;
  return dados;
}

function alternarDia(dias: number[], dia: number): number[] {
  return dias.includes(dia) ? dias.filter((d) => d !== dia) : [...dias, dia].sort();
}

type EditarProgramaFormProps = {
  /** null = formulario de criacao -- so faz POST quando o usuario clica em Salvar. */
  programaId: number | null;
  /** obrigatorio quando programaId e' null: radialista dono do programa novo. */
  radioConfigId?: number;
  /** so' usado no formulario de criacao (programaId === null), pra pre-preencher campos
   * (ex.: dia/horario escolhidos ao clicar num slot vazio da grade semanal). */
  valoresIniciais?: Partial<Programa>;
  onSalvo?: (programa: Programa) => void;
  onExcluido?: () => void;
};

export default function EditarProgramaForm({
  programaId,
  radioConfigId,
  valoresIniciais,
  onSalvo,
  onExcluido,
}: EditarProgramaFormProps) {
  const [programa, setPrograma] = useState<Programa | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [mensagem, setMensagem] = useState("");
  const [erro, setErro] = useState("");
  const [confirmandoExclusao, setConfirmandoExclusao] = useState(false);
  const [patrocinadores, setPatrocinadores] = useState<Patrocinador[]>([]);
  const [vinhetas, setVinhetas] = useState<BibliotecaAudioItem[]>([]);
  const [categorias, setCategorias] = useState<CategoriaVinheta[]>([]);
  const [iaAberto, setIaAberto] = useState(false);
  const [descricaoIA, setDescricaoIA] = useState("");
  const [gerandoIA, setGerandoIA] = useState(false);
  const [erroIA, setErroIA] = useState("");
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

  // Depois que o POST de criacao roda (dentro de salvar()), guarda o id criado aqui --
  // programaId (prop) continua null enquanto o pai (pagina/modal) nao navegar/atualizar,
  // entao o formulario passa a se comportar como edicao sem depender disso.
  const [idCriado, setIdCriado] = useState<number | null>(null);
  const idEfetivo = programaId ?? idCriado;
  const criando = idEfetivo === null;

  useEffect(() => {
    if (idEfetivo === null) {
      setPrograma(
        normalizarPrograma({ id: 0, radio_config_id: radioConfigId ?? 0, ...PROGRAMA_VAZIO, ...valoresIniciais })
      );
      setCarregando(false);
    } else {
      setCarregando(true);
      apiFetch<Programa>(`/config/programas/${idEfetivo}`)
        .then((dados) => setPrograma(normalizarPrograma(dados)))
        .catch((err) => setErro(err instanceof ApiError ? err.message : "Erro ao carregar programa"))
        .finally(() => setCarregando(false));
    }
    apiFetch<Patrocinador[]>("/patrocinadores")
      .then(setPatrocinadores)
      .catch(() => setPatrocinadores([]));
    apiFetch<BibliotecaAudioItem[]>("/biblioteca-audio")
      .then(setVinhetas)
      .catch(() => setVinhetas([]));
    apiFetch<CategoriaVinheta[]>("/categorias-vinheta")
      .then(setCategorias)
      .catch(() => setCategorias([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idEfetivo]);

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    if (!programa) return;
    if (criando && !radioConfigId) {
      setErro("Radialista nao identificado -- volte e tente de novo.");
      return;
    }
    setSalvando(true);
    setErro("");
    setMensagem("");
    try {
      const atualizado = criando
        ? await apiFetch<Programa>(`/config/radialistas/${radioConfigId}/programas`, {
            method: "POST",
            body: JSON.stringify(semCamposSistema(programa)),
          })
        : await apiFetch<Programa>(`/config/programas/${idEfetivo}`, {
            method: "PUT",
            body: JSON.stringify(semCamposSistema(programa)),
          });
      if (criando) setIdCriado(atualizado.id);
      setPrograma(normalizarPrograma(atualizado));
      setMensagem(criando ? "Programa criado." : "Programa salvo.");
      onSalvo?.(atualizado);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao salvar");
    } finally {
      setSalvando(false);
    }
  }

  async function gerarComIA() {
    if ((!descricaoIA.trim() && !tipoRadioConta) || !radioConfigId) return;
    setGerandoIA(true);
    setErroIA("");
    try {
      const criado = await apiFetch<Programa>(`/config/radialistas/${radioConfigId}/programas/gerar-ia`, {
        method: "POST",
        body: JSON.stringify({ descricao: descricaoIA.trim() }),
      });
      setIdCriado(criado.id);
      setPrograma(normalizarPrograma(criado));
      setIaAberto(false);
      setMensagem("Programa gerado com IA -- revise e ajuste o que quiser antes de salvar.");
      onSalvo?.(criado);
    } catch (err) {
      setErroIA(err instanceof ApiError ? err.message : "Erro ao gerar programa com IA");
    } finally {
      setGerandoIA(false);
    }
  }

  async function excluirPrograma() {
    if (!programa || idEfetivo === null) return;
    try {
      await apiFetch(`/config/programas/${idEfetivo}`, { method: "DELETE" });
      onExcluido?.();
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao excluir programa");
    } finally {
      setConfirmandoExclusao(false);
    }
  }

  if (carregando) {
    return (
      <p className="flex items-center gap-2 text-sm text-fg/65">
        <LocufySpin size={16} /> Carregando...
      </p>
    );
  }

  if (!programa) {
    return <p className="text-sm text-rust-text">{erro || "Programa não encontrado."}</p>;
  }

  return (
    <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6">
      <div className="flex items-center justify-between mb-5">
        <h2 className="font-display text-base font-bold text-fg">{criando ? "Novo programa" : "Editar programa"}</h2>
        {!criando && (
          <button
            type="button"
            onClick={() => setConfirmandoExclusao(true)}
            className="text-xs font-medium text-rust-text hover:text-rust/80"
          >
            Excluir programa
          </button>
        )}
      </div>

      {criando && radioConfigId && (
        <div className="mb-4 rounded-xl border border-amber/30 bg-amber/5 p-4">
          {!iaAberto ? (
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm text-fg/70">Prefere começar com um rascunho pronto?</p>
              <button
                type="button"
                onClick={() => {
                  setErroIA("");
                  setDescricaoIA("");
                  setIaAberto(true);
                }}
                className="shrink-0 text-sm font-medium text-amber-text hover:text-amber-dim"
              >
                ✨ Gerar com IA
              </button>
            </div>
          ) : (
            <div>
              <p className="text-sm text-fg/70 mb-3">
                Descreva o gênero, o tom e o horário do programa. A IA preenche tópicos, estrutura de blocos,
                músicas e todo o resto -- depois é só revisar e ajustar.
              </p>
              {tipoRadioConta ? (
                <p className="text-xs font-medium text-amber-text bg-amber/10 rounded-lg px-3 py-2 mb-3">
                  Baseado no perfil: {labelTipoRadioConta ?? tipoRadioConta}
                </p>
              ) : (
                <p className="text-xs text-fg/65 bg-paper/5 rounded-lg px-3 py-2 mb-3">
                  Nenhum tipo de rádio configurado -- a IA vai depender só da descrição.{" "}
                  <Link href="/configuracoes" className="font-medium text-amber-text hover:underline">
                    Configurar tipo de rádio →
                  </Link>
                </p>
              )}
              <textarea
                value={descricaoIA}
                onChange={(e) => setDescricaoIA(e.target.value)}
                disabled={gerandoIA}
                rows={3}
                placeholder="Descrição (opcional). Ex: programa noturno, mais calmo e romântico, foco em modão"
                className={inputClass}
              />
              {erroIA && <p className="text-sm text-rust-text mt-2">{erroIA}</p>}
              <div className="flex justify-end gap-3 mt-3">
                <button
                  type="button"
                  onClick={() => setIaAberto(false)}
                  disabled={gerandoIA}
                  className="rounded-lg px-4 py-2 text-sm font-medium text-fg/60 hover:text-fg disabled:opacity-60"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={gerarComIA}
                  disabled={gerandoIA || (!descricaoIA.trim() && !tipoRadioConta)}
                  className="rounded-lg bg-amber px-4 py-2 text-sm font-medium text-ink hover:bg-amber/90 disabled:opacity-60"
                >
                  {gerandoIA ? "Gerando..." : "Gerar"}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {erro && (
        <div className="mb-4">
          <p className="text-sm text-rust-text">{erro}</p>
          {erro.toLowerCase().includes("conflita") && (
            <p className="text-sm text-fg/65 mt-1">
              Ajuste o horário do programa mencionado acima (ou o dele mesmo) pra abrir espaço, ou escolha outro
              horário pra este aqui.
            </p>
          )}
        </div>
      )}
      {mensagem && <p className="text-sm text-teal-text mb-4">{mensagem}</p>}

      <form onSubmit={salvar} className="space-y-4">
        <h3 className="font-mono text-xs uppercase tracking-wide text-amber-text">No ar</h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label className={labelClass}>Nome do programa</label>
            <input
              className={inputClass}
              value={programa.nome}
              onChange={(e) => setPrograma({ ...programa, nome: e.target.value })}
            />
          </div>
          <div>
            <label className={labelClass}>Horário de início</label>
            <input
              type="time"
              className={inputClass}
              value={programa.horario_inicio.slice(0, 5)}
              onChange={(e) => setPrograma({ ...programa, horario_inicio: `${e.target.value}:00` })}
            />
          </div>
          <div>
            <label className={labelClass}>Horário de fim</label>
            <input
              type="time"
              className={inputClass}
              value={programa.horario_fim.slice(0, 5)}
              onChange={(e) => setPrograma({ ...programa, horario_fim: `${e.target.value}:00` })}
            />
          </div>
        </div>
        <div>
          <label className={labelClass}>Sobre o programa</label>
          <textarea
            rows={3}
            className={inputClass}
            value={programa.descricao}
            onChange={(e) => setPrograma({ ...programa, descricao: e.target.value })}
            placeholder="Do que se trata esse programa: formato, proposta, publico -- da mais contexto pro agente alem do tom e dos topicos permitidos."
          />
        </div>
        <div>
          <label className={labelClass}>Recorrência</label>
          <div className="flex gap-1.5 mb-3">
            <button
              type="button"
              onClick={() => setPrograma({ ...programa, data_especifica: null })}
              className={`rounded-full px-3 py-1 text-xs font-medium border ${
                !programa.data_especifica
                  ? "bg-brand-500 text-ink border-brand-500"
                  : "bg-transparent text-fg/65 border-border-strong"
              }`}
            >
              Recorrente
            </button>
            <button
              type="button"
              onClick={() =>
                setPrograma({
                  ...programa,
                  data_especifica: programa.data_especifica ?? new Date().toISOString().slice(0, 10),
                })
              }
              className={`rounded-full px-3 py-1 text-xs font-medium border ${
                programa.data_especifica
                  ? "bg-brand-500 text-ink border-brand-500"
                  : "bg-transparent text-fg/65 border-border-strong"
              }`}
            >
              Avulso (um dia só)
            </button>
          </div>

          {programa.data_especifica ? (
            <div>
              <label className={labelClass}>Data</label>
              <input
                type="date"
                className={inputClass}
                value={programa.data_especifica}
                onChange={(e) => setPrograma({ ...programa, data_especifica: e.target.value })}
              />
              <p className="text-xs text-fg/65 mt-1">Programa avulso: vai ao ar só nessa data.</p>
            </div>
          ) : (
            <div>
              <div className="flex flex-wrap gap-1.5 mb-1">
                {DIAS_SEMANA_LABEL.map((label, dia) => (
                  <button
                    key={label}
                    type="button"
                    onClick={() => setPrograma({ ...programa, dias_semana: alternarDia(programa.dias_semana, dia) })}
                    className={`rounded-full px-3 py-1 text-xs font-medium border ${
                      programa.dias_semana.includes(dia)
                        ? "bg-brand-500 text-ink border-brand-500"
                        : "bg-transparent text-fg/65 border-border-strong"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <p className="text-xs text-fg/65">Nenhum dia marcado = programa vai ao ar todos os dias.</p>
            </div>
          )}
        </div>
        <label className="inline-flex items-center gap-2 text-sm font-medium text-fg/80">
          <input
            type="checkbox"
            checked={programa.ativo}
            onChange={(e) => setPrograma({ ...programa, ativo: e.target.checked })}
            className="h-4 w-4 rounded border-border-strong bg-bg text-amber-text focus:ring-amber/40"
          />
          Programa ativo
        </label>

        {!criando && idEfetivo !== null && (
          <>
            <hr className="border-border" />
            <h3 className="font-mono text-xs uppercase tracking-wide text-amber-text">Radialistas</h3>
            <RadialistasProgramaSection programaId={idEfetivo} />
          </>
        )}

        <hr className="border-border" />
        <div className="flex items-center justify-between gap-2">
          <h3 className="font-mono text-xs uppercase tracking-wide text-amber-text">Roteiro do programa</h3>
          <Link
            href="/vinhetagem"
            target="_blank"
            className="text-xs font-medium text-amber-text hover:text-amber-dim"
          >
            Gerenciar vinhetagem ↗
          </Link>
        </div>

        {criando ? (
          <RoteiroBlocosEditor
            blocos={programa.estrutura_blocos}
            onChange={(blocos) => setPrograma({ ...programa, estrutura_blocos: blocos })}
            patrocinadores={patrocinadores}
            vinhetas={vinhetas}
            categorias={categorias}
            janelaSegundos={janelaSegundos(programa.horario_inicio, programa.horario_fim)}
          />
        ) : (
          <div className="rounded-xl border border-border-strong bg-bg/40 p-4">
            {programa.estrutura_blocos.length > 0 ? (
              <ol className="flex flex-wrap items-center gap-1.5 mb-3">
                {programa.estrutura_blocos.map((bloco, i) => {
                  const cor = CORES_BLOCO[kindDoBloco(bloco)];
                  return (
                    <li key={`${bloco}-${i}`} className="flex items-center gap-1.5">
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-amber/10 text-amber-text border border-amber/25 px-2.5 py-0.5 text-sm">
                        <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${cor.dot}`} />
                        {rotuloBloco(bloco, Object.fromEntries(patrocinadores.map((p) => [p.id, p.nome])))}
                      </span>
                      {i < programa.estrutura_blocos.length - 1 && <span className="text-fg/25 text-xs">→</span>}
                    </li>
                  );
                })}
              </ol>
            ) : (
              <p className="text-sm text-fg/65 mb-3">Nenhum bloco montado ainda -- o programa não tem roteiro definido.</p>
            )}
            <Link
              href={`/radialista/${programa.radio_config_id}/programas/${idEfetivo}/grade`}
              className="inline-flex items-center gap-1 text-sm font-medium text-amber-text hover:text-amber-dim"
            >
              {programa.estrutura_blocos.length > 0 ? "Editar sequência do programa" : "Montar sequência do programa"} ↗
            </Link>
          </div>
        )}

        <label className="inline-flex items-center gap-2 text-sm font-medium text-fg/80">
          <input
            type="checkbox"
            checked={programa.ia_pode_adicionar_blocos}
            onChange={(e) => setPrograma({ ...programa, ia_pode_adicionar_blocos: e.target.checked })}
            className="h-4 w-4 rounded border-border-strong bg-bg text-amber-text focus:ring-amber/40"
          />
          IA pode inserir blocos extras entre os da sequência
        </label>

        <hr className="border-border" />
        <h3 className="font-mono text-xs uppercase tracking-wide text-amber-text">Persona e conteúdo</h3>
        <div>
          <label className={labelClass}>Tom de voz</label>
          <textarea
            className={inputClass}
            rows={3}
            value={programa.tom}
            onChange={(e) => setPrograma({ ...programa, tom: e.target.value })}
          />
        </div>
        <TagInput
          label="Tópicos permitidos"
          tags={programa.topicos_permitidos}
          onChange={(tags) => setPrograma({ ...programa, topicos_permitidos: tags })}
        />
        <TagInput
          label="Tópicos proibidos"
          tags={programa.topicos_proibidos}
          onChange={(tags) => setPrograma({ ...programa, topicos_proibidos: tags })}
        />
        <div>
          <label className={labelClass}>Mensagem de saudação</label>
          <input
            className={inputClass}
            value={programa.mensagem_saudacao}
            onChange={(e) => setPrograma({ ...programa, mensagem_saudacao: e.target.value })}
          />
        </div>
        <div>
          <label className={labelClass}>Mensagem de recusa</label>
          <input
            className={inputClass}
            value={programa.mensagem_recusa}
            onChange={(e) => setPrograma({ ...programa, mensagem_recusa: e.target.value })}
          />
        </div>
        <div>
          <label className={labelClass}>Limite de mensagens por hora</label>
          <input
            type="number"
            min={1}
            className={inputClass}
            value={programa.limite_mensagens_hora}
            onChange={(e) => setPrograma({ ...programa, limite_mensagens_hora: Number(e.target.value) })}
          />
        </div>

        <hr className="border-border" />
        <details className="group">
          <summary className="flex items-center justify-between cursor-pointer list-none py-1 [&::-webkit-details-marker]:hidden">
            <span className="font-mono text-xs uppercase tracking-wide text-amber-text">
              Músicas <span className="text-fg/40 normal-case font-sans">-- opcional, ajusta o que a IA toca</span>
            </span>
            <span className="text-fg/40 transition-transform group-open:rotate-90">›</span>
          </summary>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 mt-3">
            <TagInput
              label="Gêneros permitidos"
              tags={programa.generos_musicais}
              onChange={(tags) => setPrograma({ ...programa, generos_musicais: tags })}
            />
            <TagInput
              label="Músicas ou artistas preferidos"
              tags={programa.musicas_permitidas}
              onChange={(tags) => setPrograma({ ...programa, musicas_permitidas: tags })}
            />
            <TagInput
              label="Músicas ou artistas bloqueados"
              tags={programa.musicas_bloqueadas}
              onChange={(tags) => setPrograma({ ...programa, musicas_bloqueadas: tags })}
            />
            <div>
              <label className={labelClass}>Busca de músicas</label>
              <textarea
                className={inputClass}
                rows={5}
                placeholder="Ex.: sertanejo raiz e universitário dos anos 2000 até hoje, evitar remixes eletrônicos"
                value={programa.criterios_busca_musicas}
                onChange={(e) => setPrograma({ ...programa, criterios_busca_musicas: e.target.value })}
              />
            </div>
            <div>
              <label className={labelClass}>Música de fundo (enquanto o locutor fala)</label>
              <input
                type="text"
                className={inputClass}
                placeholder="Ex.: Lofi Chill Beats - Instrumental. Vazio = sorteia pelo gênero"
                value={programa.musica_fundo_escolhida}
                onChange={(e) => setPrograma({ ...programa, musica_fundo_escolhida: e.target.value })}
              />
            </div>
          </div>
        </details>

        <hr className="border-border" />
        <details className="group">
          <summary className="flex items-center justify-between cursor-pointer list-none py-1 [&::-webkit-details-marker]:hidden">
            <span className="font-mono text-xs uppercase tracking-wide text-amber-text">
              Assuntos e notícias <span className="text-fg/40 normal-case font-sans">-- opcional</span>
            </span>
            <span className="text-fg/40 transition-transform group-open:rotate-90">›</span>
          </summary>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 mt-3">
            <TagInput
              label="Assuntos do ao vivo"
              tags={programa.assuntos_ao_vivo}
              onChange={(tags) => setPrograma({ ...programa, assuntos_ao_vivo: tags })}
            />
            <TagInput
              label="Tipos de notícias"
              tags={programa.tipos_noticias}
              onChange={(tags) => setPrograma({ ...programa, tipos_noticias: tags })}
            />
            <TagInput
              label="Fontes de notícias"
              tags={programa.fontes_noticias}
              onChange={(tags) => setPrograma({ ...programa, fontes_noticias: tags })}
            />
          </div>
        </details>

        <hr className="border-border" />
        <details className="group">
          <summary className="flex items-center justify-between cursor-pointer list-none py-1 [&::-webkit-details-marker]:hidden">
            <span className="font-mono text-xs uppercase tracking-wide text-amber-text">
              Pesquisa externa <span className="text-fg/40 normal-case font-sans">-- opcional</span>
            </span>
            <span className="text-fg/40 transition-transform group-open:rotate-90">›</span>
          </summary>
          <label className="inline-flex items-center gap-2 text-sm font-medium text-fg/80 mt-3 mb-1">
            <input
              type="checkbox"
              checked={programa.pode_pesquisar}
              onChange={(e) => setPrograma({ ...programa, pode_pesquisar: e.target.checked })}
              className="h-4 w-4 rounded border-border-strong bg-bg text-amber-text focus:ring-amber/40"
            />
            Pode pesquisar
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4">
            <TagInput
              label="Onde pode pesquisar"
              tags={programa.fontes_pesquisa}
              onChange={(tags) => setPrograma({ ...programa, fontes_pesquisa: tags })}
            />
            <div>
              <label className={labelClass}>Regras de pesquisa</label>
              <textarea
                className={inputClass}
                rows={5}
                placeholder="Ex.: buscar só em fontes de notícia locais, resumir em até 2 frases, sem opinião"
                value={programa.instrucoes_pesquisa}
                onChange={(e) => setPrograma({ ...programa, instrucoes_pesquisa: e.target.value })}
              />
            </div>
          </div>
        </details>

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

      <ConfirmDialog
        open={confirmandoExclusao}
        title="Excluir programa"
        mensagem={`Excluir o programa "${programa.nome}"? Essa ação não pode ser desfeita.`}
        onConfirmar={excluirPrograma}
        onCancelar={() => setConfirmandoExclusao(false)}
      />
    </div>
  );
}
