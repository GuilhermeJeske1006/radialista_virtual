"use client";

import { useState } from "react";
import Modal from "../Modal";
import ConfirmDialog from "../ConfirmDialog";
import { apiFetch, apiFetchForm, apiFetchBlob, ApiError } from "../../lib/api";
import { BibliotecaAudioItem, agruparPorCategoria, formatarDuracao } from "../../lib/bibliotecaAudio";
import { CategoriaVinheta } from "../../lib/types";
import { LocufySpin } from "../LocufyLogo";

const inputClass =
  "w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg placeholder:text-fg/65 focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20";
const labelClass = "block text-sm font-medium text-fg/80 mb-1.5";

type FormState = {
  id: number | null;
  nome: string;
  categoria_id: number | null;
  cor: string;
  ordem: number;
  ativo: boolean;
  arquivo: File | null;
};

const FORM_VAZIO: FormState = {
  id: null,
  nome: "",
  categoria_id: null,
  cor: "",
  ordem: 0,
  ativo: true,
  arquivo: null,
};

type Props = {
  itens: BibliotecaAudioItem[];
  categorias: CategoriaVinheta[];
  carregando: boolean;
  onRecarregar: () => void;
  programaAtivo: boolean;
  onInserirNaTransmissao: (item: BibliotecaAudioItem) => void;
};

export default function BibliotecaAudioPanel({
  itens,
  categorias,
  carregando,
  onRecarregar,
  programaAtivo,
  onInserirNaTransmissao,
}: Props) {
  const [erro, setErro] = useState("");
  const [form, setForm] = useState<FormState | null>(null);
  const [salvando, setSalvando] = useState(false);
  const [paraExcluir, setParaExcluir] = useState<BibliotecaAudioItem | null>(null);
  const [tocandoId, setTocandoId] = useState<number | null>(null);

  function abrirNovo() {
    setErro("");
    setForm({ ...FORM_VAZIO });
  }

  function abrirEdicao(item: BibliotecaAudioItem) {
    setErro("");
    setForm({
      id: item.id,
      nome: item.nome,
      categoria_id: item.categoria_id,
      cor: item.cor ?? "",
      ordem: item.ordem,
      ativo: item.ativo,
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
    if (form.categoria_id !== null) dados.set("categoria_id", String(form.categoria_id));
    if (form.cor) dados.set("cor", form.cor);
    dados.set("ordem", String(form.ordem));
    dados.set("ativo", String(form.ativo));
    if (form.arquivo) dados.set("arquivo", form.arquivo);

    try {
      if (form.id === null) {
        if (!form.arquivo) throw new ApiError(400, "Selecione um arquivo de audio");
        await apiFetchForm<BibliotecaAudioItem>("/biblioteca-audio", dados, "POST");
      } else {
        await apiFetchForm<BibliotecaAudioItem>(`/biblioteca-audio/${form.id}`, dados, "PUT");
      }
      setForm(null);
      onRecarregar();
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao salvar item da biblioteca");
    } finally {
      setSalvando(false);
    }
  }

  async function excluir(item: BibliotecaAudioItem) {
    try {
      await apiFetch(`/biblioteca-audio/${item.id}`, { method: "DELETE" });
      onRecarregar();
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao excluir item");
    } finally {
      setParaExcluir(null);
    }
  }

  async function tocar(item: BibliotecaAudioItem) {
    // com a transmissao no ar, o clique vai direto pro ao vivo -- corta a fala/musica
    // atual e poe esse audio no ar, em vez do preview isolado abaixo.
    if (programaAtivo) {
      onInserirNaTransmissao(item);
      return;
    }
    try {
      setTocandoId(item.id);
      const blob = await apiFetchBlob(`/biblioteca-audio/${item.id}/audio`);
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.onended = () => {
        setTocandoId((atual) => (atual === item.id ? null : atual));
        URL.revokeObjectURL(url);
      };
      audio.play();
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao tocar audio");
      setTocandoId(null);
    }
  }

  return (
    <section className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-5">
      <div className="flex items-center justify-between mb-1">
        <h2 className="font-display text-base font-bold text-fg">Biblioteca</h2>
        <button
          type="button"
          onClick={abrirNovo}
          className="rounded-lg bg-brand-500 px-3 py-1.5 text-xs font-medium text-ink hover:bg-brand-600"
        >
          + Áudio
        </button>
      </div>
      <p className="text-xs text-fg/65 mb-3">Cadastro de vinhetas e efeitos -- toque em Cartwall pra disparar.</p>

      {erro && <p className="text-xs text-rust-text mb-3">{erro}</p>}

      {carregando ? (
        <p className="flex items-center gap-2 text-sm text-fg/65">
          <LocufySpin size={16} /> Carregando...
        </p>
      ) : itens.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border-strong p-5 text-center">
          <p className="text-sm text-fg/65">Nenhum áudio cadastrado.</p>
          <p className="text-xs text-fg/65 mt-1">Suba vinhetas, efeitos ou jingles próprios pra começar.</p>
        </div>
      ) : (
        <div className="space-y-4 max-h-96 overflow-y-auto pr-1 -mr-1">
          {agruparPorCategoria(itens, categorias).map(([categoria, itensDaCategoria]) => (
            <div key={categoria.id ?? "sem-categoria"}>
              <p className="text-xs font-mono font-medium text-fg/65 uppercase tracking-wide mb-1.5">
                {categoria.nome}
              </p>
              <div className="space-y-1.5">
                {itensDaCategoria.map((item) => (
                  <div
                    key={item.id}
                    className="flex items-center gap-2 rounded-lg border border-border px-2.5 py-1.5 text-sm"
                  >
                    <button
                      type="button"
                      onClick={() => tocar(item)}
                      className="shrink-0 text-amber-text hover:text-amber-dim"
                      title="Tocar"
                    >
                      {tocandoId === item.id ? <LocufySpin size={14} /> : "▶"}
                    </button>
                    <div className="min-w-0 flex-1">
                      <p className={`truncate ${item.ativo ? "text-fg" : "text-fg/65"}`}>{item.nome}</p>
                    </div>
                    <span className="shrink-0 font-mono text-xs text-fg/65">
                      {formatarDuracao(item.duracao_segundos)}
                    </span>
                    <button
                      type="button"
                      onClick={() => abrirEdicao(item)}
                      title="Editar"
                      className="shrink-0 flex h-6 w-6 items-center justify-center rounded-md text-amber-text hover:bg-amber/10"
                    >
                      ✎
                    </button>
                    <button
                      type="button"
                      onClick={() => setParaExcluir(item)}
                      title="Excluir"
                      className="shrink-0 flex h-6 w-6 items-center justify-center rounded-md text-rust-text hover:bg-rust/10"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal open={form !== null} onClose={() => setForm(null)} title={form?.id === null ? "Novo áudio" : "Editar áudio"}>
        {form && (
          <form onSubmit={salvar} className="space-y-4">
            <div>
              <label className={labelClass}>Nome</label>
              <input
                type="text"
                required
                value={form.nome}
                onChange={(e) => setForm({ ...form, nome: e.target.value })}
                className={inputClass}
                placeholder="Ex.: Vinheta de abertura"
              />
            </div>
            <div>
              <label className={labelClass}>Categoria</label>
              <select
                aria-label="Categoria"
                value={form.categoria_id ?? ""}
                onChange={(e) => setForm({ ...form, categoria_id: e.target.value ? Number(e.target.value) : null })}
                className={inputClass}
              >
                <option value="">Sem categoria</option>
                {categorias
                  .filter((categoria) => categoria.tipo === "biblioteca")
                  .map((categoria) => (
                    <option key={categoria.id} value={categoria.id}>
                      {categoria.nome}
                    </option>
                  ))}
              </select>
              <p className="text-xs text-fg/65 mt-1.5">
                Categorias são cadastradas na tela de Vinhetagem.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={labelClass}>Cor do card (opcional)</label>
                <input
                  type="color"
                  value={form.cor || "#e8a33d"}
                  onChange={(e) => setForm({ ...form, cor: e.target.value })}
                  className="h-10 w-full rounded-lg border border-border-strong bg-bg"
                />
              </div>
              <div>
                <label className={labelClass}>Ordem no cartwall</label>
                <input
                  type="number"
                  value={form.ordem}
                  onChange={(e) => setForm({ ...form, ordem: Number(e.target.value) })}
                  className={inputClass}
                />
              </div>
            </div>
            <div>
              <label className={labelClass}>Arquivo de áudio (mp3, m4a, wav ou ogg, até 15MB)</label>
              <input
                type="file"
                accept="audio/*,.mp3,.m4a,.wav,.ogg"
                onChange={(e) => setForm({ ...form, arquivo: e.target.files?.[0] ?? null })}
                className={inputClass}
              />
              <p className="text-xs text-fg/65 mt-1.5">
                {form.id !== null ? "Deixe em branco pra manter o áudio atual." : "Obrigatório."}
              </p>
            </div>
            {form.id !== null && (
              <label className="flex items-center gap-1.5 text-sm text-fg/80">
                <input
                  type="checkbox"
                  checked={form.ativo}
                  onChange={(e) => setForm({ ...form, ativo: e.target.checked })}
                />
                Ativo (aparece no cartwall)
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
        title="Excluir áudio"
        mensagem={`Excluir "${paraExcluir?.nome}"? Ele some do cartwall imediatamente. Essa ação não pode ser desfeita.`}
        onConfirmar={() => paraExcluir && excluir(paraExcluir)}
        onCancelar={() => setParaExcluir(null)}
      />
    </section>
  );
}
