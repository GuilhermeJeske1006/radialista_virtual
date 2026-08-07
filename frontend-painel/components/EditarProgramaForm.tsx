"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import ConfirmDialog from "./ConfirmDialog";
import TagInput from "./TagInput";
import EstruturaBlocosInput from "./EstruturaBlocosInput";
import { apiFetch, ApiError } from "../lib/api";
import { DIAS_SEMANA_LABEL, normalizarPrograma, Patrocinador, Programa } from "../lib/types";
import { OndaSpin } from "./OndaLogo";

const inputClass =
  "w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg placeholder:text-fg/35 focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20";
const labelClass = "block text-sm font-medium text-fg/80 mb-1.5";

function semCamposSistema(p: Programa) {
  const { id, radio_config_id, ...dados } = p;
  return dados;
}

function alternarDia(dias: number[], dia: number): number[] {
  return dias.includes(dia) ? dias.filter((d) => d !== dia) : [...dias, dia].sort();
}

type EditarProgramaFormProps = {
  programaId: number;
  onSalvo?: (programa: Programa) => void;
  onExcluido?: () => void;
};

export default function EditarProgramaForm({ programaId, onSalvo, onExcluido }: EditarProgramaFormProps) {
  const [programa, setPrograma] = useState<Programa | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [mensagem, setMensagem] = useState("");
  const [erro, setErro] = useState("");
  const [confirmandoExclusao, setConfirmandoExclusao] = useState(false);
  const [patrocinadores, setPatrocinadores] = useState<Patrocinador[]>([]);

  useEffect(() => {
    setCarregando(true);
    apiFetch<Programa>(`/config/programas/${programaId}`)
      .then((dados) => setPrograma(normalizarPrograma(dados)))
      .catch((err) => setErro(err instanceof ApiError ? err.message : "Erro ao carregar programa"))
      .finally(() => setCarregando(false));
    apiFetch<Patrocinador[]>("/patrocinadores")
      .then(setPatrocinadores)
      .catch(() => setPatrocinadores([]));
  }, [programaId]);

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    if (!programa) return;
    setSalvando(true);
    setErro("");
    setMensagem("");
    try {
      const atualizado = await apiFetch<Programa>(`/config/programas/${programaId}`, {
        method: "PUT",
        body: JSON.stringify(semCamposSistema(programa)),
      });
      setPrograma(normalizarPrograma(atualizado));
      setMensagem("Programa salvo.");
      onSalvo?.(atualizado);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao salvar");
    } finally {
      setSalvando(false);
    }
  }

  async function excluirPrograma() {
    if (!programa) return;
    try {
      await apiFetch(`/config/programas/${programaId}`, { method: "DELETE" });
      onExcluido?.();
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao excluir programa");
    } finally {
      setConfirmandoExclusao(false);
    }
  }

  if (carregando) {
    return (
      <p className="flex items-center gap-2 text-sm text-fg/55">
        <OndaSpin size={16} /> Carregando...
      </p>
    );
  }

  if (!programa) {
    return <p className="text-sm text-rust">{erro || "Programa não encontrado."}</p>;
  }

  return (
    <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6">
      <div className="flex items-center justify-between mb-5">
        <h2 className="font-display text-base font-bold text-fg">Editar programa</h2>
        <button
          type="button"
          onClick={() => setConfirmandoExclusao(true)}
          className="text-xs font-medium text-rust hover:text-rust/80"
        >
          Excluir programa
        </button>
      </div>

      {erro && <p className="text-sm text-rust mb-4">{erro}</p>}
      {mensagem && <p className="text-sm text-teal mb-4">{mensagem}</p>}

      <form onSubmit={salvar} className="space-y-4">
        <h3 className="font-mono text-xs uppercase tracking-wide text-amber">No ar</h3>
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
              <p className="text-xs text-fg/35 mt-1">Programa avulso: vai ao ar só nessa data.</p>
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
              <p className="text-xs text-fg/35">Nenhum dia marcado = programa vai ao ar todos os dias.</p>
            </div>
          )}
        </div>
        <label className="inline-flex items-center gap-2 text-sm font-medium text-fg/80">
          <input
            type="checkbox"
            checked={programa.ativo}
            onChange={(e) => setPrograma({ ...programa, ativo: e.target.checked })}
            className="h-4 w-4 rounded border-border-strong bg-bg text-amber focus:ring-amber/40"
          />
          Programa ativo
        </label>

        <hr className="border-border" />
        <div className="flex items-center justify-between gap-2">
          <h3 className="font-mono text-xs uppercase tracking-wide text-amber">Estrutura do programa</h3>
          <Link
            href="/patrocinadores"
            target="_blank"
            className="text-xs font-medium text-amber hover:text-amber-dim"
          >
            Gerenciar patrocinadores ↗
          </Link>
        </div>
        <EstruturaBlocosInput
          blocos={programa.estrutura_blocos}
          onChange={(blocos) => setPrograma({ ...programa, estrutura_blocos: blocos })}
          patrocinadores={patrocinadores}
        />
        <label className="inline-flex items-center gap-2 text-sm font-medium text-fg/80">
          <input
            type="checkbox"
            checked={programa.ia_pode_adicionar_blocos}
            onChange={(e) => setPrograma({ ...programa, ia_pode_adicionar_blocos: e.target.checked })}
            className="h-4 w-4 rounded border-border-strong bg-bg text-amber focus:ring-amber/40"
          />
          IA pode inserir blocos extras entre os da sequência
        </label>

        <hr className="border-border" />
        <h3 className="font-mono text-xs uppercase tracking-wide text-amber">Persona e conteúdo</h3>
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
        <h3 className="font-mono text-xs uppercase tracking-wide text-amber">Músicas</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4">
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
              value={programa.criterios_busca_musicas}
              onChange={(e) => setPrograma({ ...programa, criterios_busca_musicas: e.target.value })}
            />
          </div>
        </div>

        <hr className="border-border" />
        <h3 className="font-mono text-xs uppercase tracking-wide text-amber">Assuntos e notícias</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4">
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

        <hr className="border-border" />
        <div className="flex items-center justify-between gap-4">
          <h3 className="font-mono text-xs uppercase tracking-wide text-amber">Pesquisa externa</h3>
          <label className="inline-flex items-center gap-2 text-sm font-medium text-fg/80">
            <input
              type="checkbox"
              checked={programa.pode_pesquisar}
              onChange={(e) => setPrograma({ ...programa, pode_pesquisar: e.target.checked })}
              className="h-4 w-4 rounded border-border-strong bg-bg text-amber focus:ring-amber/40"
            />
            Pode pesquisar
          </label>
        </div>
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
              value={programa.instrucoes_pesquisa}
              onChange={(e) => setPrograma({ ...programa, instrucoes_pesquisa: e.target.value })}
            />
          </div>
        </div>

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
