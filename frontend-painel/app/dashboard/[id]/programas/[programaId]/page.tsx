"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import AppShell from "../../../../../components/AppShell";
import TagInput from "../../../../../components/TagInput";
import { apiFetch, ApiError } from "../../../../../lib/api";
import { DIAS_SEMANA_LABEL, normalizarPrograma, Programa } from "../../../../../lib/types";

const inputClass =
  "w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:border-brand-300 focus:ring-2 focus:ring-brand-500/20";
const labelClass = "block text-sm font-medium text-gray-700 mb-1.5";

function semCamposSistema(p: Programa) {
  const { id, radio_config_id, ...dados } = p;
  return dados;
}

function alternarDia(dias: number[], dia: number): number[] {
  return dias.includes(dia) ? dias.filter((d) => d !== dia) : [...dias, dia].sort();
}

export default function EditarProgramaPage() {
  const params = useParams<{ id: string; programaId: string }>();
  const router = useRouter();
  const radialistaId = Number(params.id);
  const programaId = Number(params.programaId);

  const [programa, setPrograma] = useState<Programa | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [mensagem, setMensagem] = useState("");
  const [erro, setErro] = useState("");

  useEffect(() => {
    apiFetch<Programa>(`/config/programas/${programaId}`)
      .then((dados) => setPrograma(normalizarPrograma(dados)))
      .catch((err) => setErro(err instanceof ApiError ? err.message : "Erro ao carregar programa"))
      .finally(() => setCarregando(false));
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
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao salvar");
    } finally {
      setSalvando(false);
    }
  }

  async function excluirPrograma() {
    if (!programa) return;
    if (!confirm(`Excluir o programa "${programa.nome}"? Essa ação não pode ser desfeita.`)) return;
    try {
      await apiFetch(`/config/programas/${programaId}`, { method: "DELETE" });
      router.push(`/dashboard/${radialistaId}`);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao excluir programa");
    }
  }

  if (carregando) {
    return (
      <AppShell title="Programa">
        <p className="text-sm text-gray-500">Carregando...</p>
      </AppShell>
    );
  }

  if (!programa) {
    return (
      <AppShell title="Programa">
        <p className="text-sm text-red-600">{erro || "Programa não encontrado."}</p>
        <Link href={`/dashboard/${radialistaId}`} className="text-sm text-brand-600 hover:underline mt-2 inline-block">
          Voltar para o radialista
        </Link>
      </AppShell>
    );
  }

  return (
    <AppShell title={programa.nome || "Programa"} maxWidthClassName="max-w-4xl">
      <Link href={`/dashboard/${radialistaId}`} className="text-sm text-brand-600 hover:underline mb-4 inline-block">
        ← Voltar para o radialista
      </Link>

      <div className="bg-white rounded-2xl border border-gray-200 shadow-theme-xs p-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-semibold text-gray-900">Editar programa</h2>
          <button
            type="button"
            onClick={excluirPrograma}
            className="text-xs font-medium text-red-600 hover:text-red-700"
          >
            Excluir programa
          </button>
        </div>

        {erro && <p className="text-sm text-red-600 mb-4">{erro}</p>}
        {mensagem && <p className="text-sm text-emerald-600 mb-4">{mensagem}</p>}

        <form onSubmit={salvar} className="space-y-4">
          <h3 className="text-sm font-semibold text-gray-900">No ar</h3>
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
            <label className={labelClass}>Dias da semana</label>
            <div className="flex flex-wrap gap-1.5 mb-1">
              {DIAS_SEMANA_LABEL.map((label, dia) => (
                <button
                  key={label}
                  type="button"
                  onClick={() => setPrograma({ ...programa, dias_semana: alternarDia(programa.dias_semana, dia) })}
                  className={`rounded-full px-3 py-1 text-xs font-medium border ${
                    programa.dias_semana.includes(dia)
                      ? "bg-brand-500 text-white border-brand-500"
                      : "bg-white text-gray-600 border-gray-300"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            <p className="text-xs text-gray-400">Nenhum dia marcado = programa vai ao ar todos os dias.</p>
          </div>
          <label className="inline-flex items-center gap-2 text-sm font-medium text-gray-700">
            <input
              type="checkbox"
              checked={programa.ativo}
              onChange={(e) => setPrograma({ ...programa, ativo: e.target.checked })}
              className="h-4 w-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500"
            />
            Programa ativo
          </label>

          <hr className="border-gray-100" />
          <h3 className="text-sm font-semibold text-gray-900">Persona e conteúdo</h3>
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

          <hr className="border-gray-100" />
          <h3 className="text-sm font-semibold text-gray-900">Músicas</h3>
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

          <hr className="border-gray-100" />
          <h3 className="text-sm font-semibold text-gray-900">Assuntos e notícias</h3>
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

          <hr className="border-gray-100" />
          <div className="flex items-center justify-between gap-4">
            <h3 className="text-sm font-semibold text-gray-900">Pesquisa externa</h3>
            <label className="inline-flex items-center gap-2 text-sm font-medium text-gray-700">
              <input
                type="checkbox"
                checked={programa.pode_pesquisar}
                onChange={(e) => setPrograma({ ...programa, pode_pesquisar: e.target.checked })}
                className="h-4 w-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500"
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
              className="rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {salvando ? "Salvando..." : "Salvar"}
            </button>
          </div>
        </form>
      </div>
    </AppShell>
  );
}
