"use client";

import { useEffect, useState } from "react";
import AppShell from "../../components/AppShell";
import Modal from "../../components/Modal";
import ConfirmDialog from "../../components/ConfirmDialog";
import VoiceSelect from "../../components/VoiceSelect";
import { apiFetch, apiFetchForm, ApiError } from "../../lib/api";
import { Patrocinador, Radialista } from "../../lib/types";
import { OndaSpin } from "../../components/OndaLogo";

const inputClass =
  "w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg placeholder:text-fg/35 focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20";
const labelClass = "block text-sm font-medium text-fg/80 mb-1.5";

type FormState = {
  id: number | null;
  nome: string;
  tipo_conteudo: "texto" | "audio";
  texto: string;
  voz_id: string | null;
  ativo: boolean;
  arquivo: File | null;
};

const FORM_VAZIO: FormState = {
  id: null,
  nome: "",
  tipo_conteudo: "texto",
  texto: "",
  voz_id: null,
  ativo: true,
  arquivo: null,
};

export default function PatrocinadoresPage() {
  const [patrocinadores, setPatrocinadores] = useState<Patrocinador[]>([]);
  const [radialistas, setRadialistas] = useState<Radialista[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");
  const [form, setForm] = useState<FormState | null>(null);
  const [salvando, setSalvando] = useState(false);
  const [paraExcluir, setParaExcluir] = useState<Patrocinador | null>(null);

  function carregar() {
    setCarregando(true);
    setErro("");
    apiFetch<Patrocinador[]>("/patrocinadores")
      .then(setPatrocinadores)
      .catch((err) => setErro(err instanceof ApiError ? err.message : "Erro ao carregar patrocinadores"))
      .finally(() => setCarregando(false));
    apiFetch<Radialista[]>("/config/radialistas")
      .then(setRadialistas)
      .catch(() => setRadialistas([]));
  }

  useEffect(() => {
    carregar();
  }, []);

  function abrirNovo() {
    setErro("");
    setForm({ ...FORM_VAZIO });
  }

  function abrirEdicao(p: Patrocinador) {
    setErro("");
    setForm({
      id: p.id,
      nome: p.nome,
      tipo_conteudo: p.tipo_conteudo,
      texto: p.texto ?? "",
      voz_id: p.voz_id ?? null,
      ativo: p.ativo,
      arquivo: null,
    });
  }

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    if (!form) return;
    setSalvando(true);
    setErro("");

    const dados = new FormData();
    dados.set("nome", form.nome);
    dados.set("tipo_conteudo", form.tipo_conteudo);
    if (form.tipo_conteudo === "texto") {
      dados.set("texto", form.texto);
      if (form.voz_id) dados.set("voz_id", form.voz_id);
    } else if (form.arquivo) {
      dados.set("arquivo", form.arquivo);
    }
    if (form.id !== null) {
      dados.set("ativo", String(form.ativo));
    }

    try {
      if (form.id === null) {
        await apiFetchForm<Patrocinador>("/patrocinadores", dados, "POST");
      } else {
        await apiFetchForm<Patrocinador>(`/patrocinadores/${form.id}`, dados, "PUT");
      }
      setForm(null);
      carregar();
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao salvar patrocinador");
    } finally {
      setSalvando(false);
    }
  }

  async function excluir(p: Patrocinador) {
    try {
      await apiFetch(`/patrocinadores/${p.id}`, { method: "DELETE" });
      carregar();
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao excluir patrocinador");
    } finally {
      setParaExcluir(null);
    }
  }

  return (
    <AppShell title="Patrocinadores" maxWidthClassName="max-w-4xl">
      <div className="flex items-center justify-between mb-5">
        <p className="text-sm text-fg/55">
          Cadastre os patrocinadores (texto lido pelo locutor ou áudio pronto) e organize onde eles entram na
          sequência de blocos de cada programa.
        </p>
        <button
          type="button"
          onClick={abrirNovo}
          className="rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-ink hover:bg-brand-600 shrink-0"
        >
          + Novo patrocinador
        </button>
      </div>

      {erro && <p className="text-sm text-rust mb-4">{erro}</p>}

      {carregando ? (
        <p className="flex items-center gap-2 text-sm text-fg/55">
          <OndaSpin size={16} /> Carregando...
        </p>
      ) : patrocinadores.length === 0 ? (
        <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6">
          <p className="text-sm text-fg/55">Nenhum patrocinador cadastrado ainda.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {patrocinadores.map((p) => (
            <div
              key={p.id}
              className="flex flex-wrap items-center justify-between gap-2 bg-surface rounded-2xl border border-border-strong shadow-theme-xs px-4 py-3"
            >
              <div className="min-w-0">
                <p className={`text-sm font-medium ${p.ativo ? "text-fg" : "text-fg/35"}`}>
                  {p.nome}
                  {!p.ativo && <span className="ml-2 text-xs font-medium text-fg/45">(inativo)</span>}
                </p>
                <p className="text-xs text-fg/45 font-mono">
                  {p.tipo_conteudo === "texto" ? "Texto (TTS)" : `Áudio${p.audio_nome_original ? ` · ${p.audio_nome_original}` : ""}`}
                </p>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <button
                  type="button"
                  onClick={() => abrirEdicao(p)}
                  className="text-xs font-medium text-amber hover:text-amber-dim"
                >
                  Editar
                </button>
                <button
                  type="button"
                  onClick={() => setParaExcluir(p)}
                  className="text-xs font-medium text-rust hover:text-rust/80"
                >
                  Excluir
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal open={form !== null} onClose={() => setForm(null)} title={form?.id === null ? "Novo patrocinador" : "Editar patrocinador"}>
        {form && (
          <form onSubmit={salvar} className="space-y-4">
            <div>
              <label className={labelClass}>Nome do patrocinador</label>
              <input
                type="text"
                required
                value={form.nome}
                onChange={(e) => setForm({ ...form, nome: e.target.value })}
                className={inputClass}
                placeholder="Ex.: Mercado Bom Preço"
              />
            </div>

            <div>
              <label className={labelClass}>Tipo de conteúdo</label>
              <div className="flex gap-4 text-sm text-fg/80">
                <label className="flex items-center gap-1.5">
                  <input
                    type="radio"
                    checked={form.tipo_conteudo === "texto"}
                    onChange={() => setForm({ ...form, tipo_conteudo: "texto" })}
                  />
                  Texto (locutor lê ao vivo)
                </label>
                <label className="flex items-center gap-1.5">
                  <input
                    type="radio"
                    checked={form.tipo_conteudo === "audio"}
                    onChange={() => setForm({ ...form, tipo_conteudo: "audio" })}
                  />
                  Áudio pronto (upload)
                </label>
              </div>
            </div>

            {form.tipo_conteudo === "texto" ? (
              <div className="space-y-4">
                <div>
                  <label className={labelClass}>Texto do anúncio</label>
                  <textarea
                    required
                    rows={4}
                    value={form.texto}
                    onChange={(e) => setForm({ ...form, texto: e.target.value })}
                    className={inputClass}
                    placeholder="Texto exato que o locutor vai ler, sem parafrasear."
                  />
                </div>
                {radialistas.length > 1 && (
                  <div>
                    <label className={labelClass}>Voz que lê este patrocinador</label>
                    <VoiceSelect value={form.voz_id} onChange={(vozId) => setForm({ ...form, voz_id: vozId })} />
                    <p className="text-xs text-fg/45 mt-1.5">
                      Sem escolha aqui, o patrocinador é lido com a voz do radialista que estiver no ar.
                    </p>
                  </div>
                )}
              </div>
            ) : (
              <div>
                <label className={labelClass}>Arquivo de áudio (mp3, m4a, wav ou ogg, até 15MB)</label>
                <input
                  type="file"
                  accept="audio/*,.mp3,.m4a,.wav,.ogg"
                  onChange={(e) => setForm({ ...form, arquivo: e.target.files?.[0] ?? null })}
                  className={inputClass}
                />
                <p className="text-xs text-fg/45 mt-1.5">
                  {form.id !== null ? "Deixe em branco pra manter o áudio atual." : "Obrigatório pra patrocinador em áudio."}
                </p>
              </div>
            )}

            {form.id !== null && (
              <label className="flex items-center gap-1.5 text-sm text-fg/80">
                <input
                  type="checkbox"
                  checked={form.ativo}
                  onChange={(e) => setForm({ ...form, ativo: e.target.checked })}
                />
                Ativo (aparece pra ser inserido nos blocos do programa)
              </label>
            )}

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setForm(null)}
                className="rounded-lg px-4 py-2.5 text-sm font-medium text-fg/60 hover:text-fg"
              >
                Cancelar
              </button>
              <button
                type="submit"
                disabled={salvando}
                className="rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-ink hover:bg-brand-600 disabled:opacity-60"
              >
                {salvando ? "Salvando..." : "Salvar"}
              </button>
            </div>
          </form>
        )}
      </Modal>

      <ConfirmDialog
        open={paraExcluir !== null}
        title="Excluir patrocinador"
        mensagem={`Excluir "${paraExcluir?.nome}"? Ele será removido de qualquer sequência de blocos que o use. Essa ação não pode ser desfeita.`}
        onConfirmar={() => paraExcluir && excluir(paraExcluir)}
        onCancelar={() => setParaExcluir(null)}
      />
    </AppShell>
  );
}
