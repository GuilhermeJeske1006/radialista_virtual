"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "../../components/AppShell";
import Modal from "../../components/Modal";
import ConfirmDialog from "../../components/ConfirmDialog";
import VoiceSelect from "../../components/VoiceSelect";
import { apiFetch, apiFetchForm, apiFetchBlob, ApiError } from "../../lib/api";
import { BibliotecaAudioItem, formatarDuracao } from "../../lib/bibliotecaAudio";
import { CategoriaVinheta, Patrocinador, Radialista } from "../../lib/types";
import { LocufySpin } from "../../components/LocufyLogo";

const inputClass =
  "w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg placeholder:text-fg/65 focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20";
const labelClass = "block text-sm font-medium text-fg/80 mb-1.5";

type FormCategoria = { id: number | null; nome: string; tipo: "biblioteca" | "propaganda" };

// Uma "inserção" e' uma vinheta (audio pro cartwall) ou uma propaganda (texto lido pelo
// locutor ou audio pronto de patrocinador) -- pro operador e' so' um item dentro da
// categoria; a distincao de tipo so aparece dentro do formulario.
type FormInsercao = {
  tipo: "biblioteca" | "propaganda";
  id: number | null;
  nome: string;
  categoria_id: number | null;
  ativo: boolean;
  arquivo: File | null;
  cor: string;
  ordem: number;
  tipo_conteudo: "texto" | "audio";
  texto: string;
  voz_id: string | null;
};

function novaInsercaoVazia(tipo: "biblioteca" | "propaganda", categoriaId: number | null): FormInsercao {
  return {
    tipo,
    id: null,
    nome: "",
    categoria_id: categoriaId,
    ativo: true,
    arquivo: null,
    cor: "",
    ordem: 0,
    tipo_conteudo: "texto",
    texto: "",
    voz_id: null,
  };
}

function SeletorCategoria({
  categorias,
  tipo,
  value,
  onChange,
}: {
  categorias: CategoriaVinheta[];
  tipo: "biblioteca" | "propaganda";
  value: number | null;
  onChange: (categoriaId: number | null) => void;
}) {
  const opcoes = categorias.filter((c) => c.tipo === tipo);
  return (
    <select
      aria-label="Categoria"
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
      className={inputClass}
    >
      <option value="">Sem categoria</option>
      {opcoes.map((categoria) => (
        <option key={categoria.id} value={categoria.id}>
          {categoria.nome}
        </option>
      ))}
    </select>
  );
}

export default function VinhetagemPage() {
  const [categorias, setCategorias] = useState<CategoriaVinheta[]>([]);
  const [vinhetas, setVinhetas] = useState<BibliotecaAudioItem[]>([]);
  const [propagandas, setPropagandas] = useState<Patrocinador[]>([]);
  const [radialistas, setRadialistas] = useState<Radialista[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");
  const [salvando, setSalvando] = useState(false);
  const [tocandoId, setTocandoId] = useState<number | null>(null);

  const [formCategoria, setFormCategoria] = useState<FormCategoria | null>(null);
  const [paraExcluirCategoria, setParaExcluirCategoria] = useState<CategoriaVinheta | null>(null);
  const [formInsercao, setFormInsercao] = useState<FormInsercao | null>(null);
  const [paraExcluirInsercao, setParaExcluirInsercao] = useState<
    { tipo: "biblioteca"; item: BibliotecaAudioItem } | { tipo: "propaganda"; item: Patrocinador } | null
  >(null);

  function carregar() {
    setCarregando(true);
    setErro("");
    Promise.all([
      apiFetch<CategoriaVinheta[]>("/categorias-vinheta"),
      apiFetch<BibliotecaAudioItem[]>("/biblioteca-audio"),
      apiFetch<Patrocinador[]>("/patrocinadores"),
    ])
      .then(([c, v, p]) => {
        setCategorias(c);
        setVinhetas(v);
        setPropagandas(p);
      })
      .catch((err) => setErro(err instanceof ApiError ? err.message : "Erro ao carregar vinhetagem"))
      .finally(() => setCarregando(false));
    apiFetch<Radialista[]>("/config/radialistas")
      .then(setRadialistas)
      .catch(() => setRadialistas([]));
  }

  useEffect(() => {
    carregar();
  }, []);

  // --- Categorias ---

  async function salvarCategoria(e: React.FormEvent) {
    e.preventDefault();
    if (!formCategoria) return;
    setSalvando(true);
    setErro("");
    try {
      if (formCategoria.id === null) {
        await apiFetch<CategoriaVinheta>("/categorias-vinheta", {
          method: "POST",
          body: JSON.stringify({ nome: formCategoria.nome, tipo: formCategoria.tipo }),
        });
      } else {
        await apiFetch<CategoriaVinheta>(`/categorias-vinheta/${formCategoria.id}`, {
          method: "PUT",
          body: JSON.stringify({ nome: formCategoria.nome, tipo: formCategoria.tipo }),
        });
      }
      setFormCategoria(null);
      carregar();
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao salvar categoria");
    } finally {
      setSalvando(false);
    }
  }

  async function excluirCategoria(categoria: CategoriaVinheta) {
    try {
      await apiFetch(`/categorias-vinheta/${categoria.id}`, { method: "DELETE" });
      carregar();
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao excluir categoria");
    } finally {
      setParaExcluirCategoria(null);
    }
  }

  // --- Inserções (vinheta ou propaganda) ---

  async function tocarVinheta(item: BibliotecaAudioItem) {
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
      setErro(err instanceof ApiError ? err.message : "Erro ao tocar áudio");
      setTocandoId(null);
    }
  }

  function editarVinheta(item: BibliotecaAudioItem) {
    setFormInsercao({
      tipo: "biblioteca",
      id: item.id,
      nome: item.nome,
      categoria_id: item.categoria_id,
      ativo: item.ativo,
      arquivo: null,
      cor: item.cor ?? "",
      ordem: item.ordem,
      tipo_conteudo: "texto",
      texto: "",
      voz_id: null,
    });
  }

  function editarPropaganda(p: Patrocinador) {
    setFormInsercao({
      tipo: "propaganda",
      id: p.id,
      nome: p.nome,
      categoria_id: p.categoria_id,
      ativo: p.ativo,
      arquivo: null,
      cor: "",
      ordem: 0,
      tipo_conteudo: p.tipo_conteudo,
      texto: p.texto ?? "",
      voz_id: p.voz_id ?? null,
    });
  }

  async function salvarInsercao(e: React.FormEvent) {
    e.preventDefault();
    if (!formInsercao) return;
    setSalvando(true);
    setErro("");

    const dados = new FormData();
    dados.set("nome", formInsercao.nome);
    if (formInsercao.categoria_id !== null) dados.set("categoria_id", String(formInsercao.categoria_id));

    try {
      if (formInsercao.tipo === "biblioteca") {
        if (formInsercao.cor) dados.set("cor", formInsercao.cor);
        dados.set("ordem", String(formInsercao.ordem));
        dados.set("ativo", String(formInsercao.ativo));
        if (formInsercao.arquivo) dados.set("arquivo", formInsercao.arquivo);

        if (formInsercao.id === null) {
          if (!formInsercao.arquivo) throw new ApiError(400, "Selecione um arquivo de áudio");
          await apiFetchForm<BibliotecaAudioItem>("/biblioteca-audio", dados, "POST");
        } else {
          await apiFetchForm<BibliotecaAudioItem>(`/biblioteca-audio/${formInsercao.id}`, dados, "PUT");
        }
      } else {
        dados.set("tipo_conteudo", formInsercao.tipo_conteudo);
        if (formInsercao.tipo_conteudo === "texto") {
          dados.set("texto", formInsercao.texto);
          if (formInsercao.voz_id) dados.set("voz_id", formInsercao.voz_id);
        } else if (formInsercao.arquivo) {
          dados.set("arquivo", formInsercao.arquivo);
        }
        if (formInsercao.id !== null) dados.set("ativo", String(formInsercao.ativo));

        if (formInsercao.id === null) {
          await apiFetchForm<Patrocinador>("/patrocinadores", dados, "POST");
        } else {
          await apiFetchForm<Patrocinador>(`/patrocinadores/${formInsercao.id}`, dados, "PUT");
        }
      }
      setFormInsercao(null);
      carregar();
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao salvar inserção");
    } finally {
      setSalvando(false);
    }
  }

  async function excluirInsercao() {
    if (!paraExcluirInsercao) return;
    try {
      if (paraExcluirInsercao.tipo === "biblioteca") {
        await apiFetch(`/biblioteca-audio/${paraExcluirInsercao.item.id}`, { method: "DELETE" });
      } else {
        await apiFetch(`/patrocinadores/${paraExcluirInsercao.item.id}`, { method: "DELETE" });
      }
      carregar();
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao excluir inserção");
    } finally {
      setParaExcluirInsercao(null);
    }
  }

  // Sempre mostra todas as categorias cadastradas (mesmo vazias) + "Sem categoria" se houver algo lá.
  const semCategoriaTemItens =
    vinhetas.some((v) => v.categoria_id === null) || propagandas.some((p) => p.categoria_id === null);
  const gruposExibidos: { id: number | null; nome: string; tipo: "biblioteca" | "propaganda" | null }[] = [
    ...categorias.map((c) => ({ id: c.id as number | null, nome: c.nome, tipo: c.tipo })),
    ...(semCategoriaTemItens ? [{ id: null, nome: "Sem categoria", tipo: null }] : []),
  ];

  return (
    <AppShell title="Vinhetagem" maxWidthClassName="max-w-6xl">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-5">
        <p className="text-sm text-fg/65 max-w-2xl">
          Crie categorias (cada uma já marcada como biblioteca ou propaganda) e adicione as inserções dentro de cada
          uma -- o tipo é sempre o da categoria escolhida. Vinhetas de biblioteca aparecem como botões no cartwall do{" "}
          <Link href="/live" className="text-amber-text underline hover:text-amber-dim">
            Ao Vivo
          </Link>
          ; propagandas entram nos blocos &quot;Chamada ao ouvinte&quot; da programação de cada radialista.
        </p>
        <div className="flex flex-wrap gap-2 shrink-0">
          <button
            type="button"
            onClick={() => setFormCategoria({ id: null, nome: "", tipo: "biblioteca" })}
            className="rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-ink hover:bg-brand-600"
          >
            + Categoria
          </button>
        </div>
      </div>

      {erro && <p className="text-sm text-rust-text mb-4">{erro}</p>}

      {carregando ? (
        <p className="flex items-center gap-2 text-sm text-fg/65">
          <LocufySpin size={16} /> Carregando...
        </p>
      ) : categorias.length === 0 && vinhetas.length === 0 && propagandas.length === 0 ? (
        <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6">
          <p className="text-sm text-fg/65">
            Nada cadastrado ainda. Comece criando uma categoria (ex.: &quot;Vinhetas&quot;, &quot;Comerciais&quot;) e
            depois adicione inserções dentro dela.
          </p>
        </div>
      ) : (
        <div className="space-y-5">
          {gruposExibidos.map((categoria) => {
            const categoriaId = categoria.id;
            const itensDaCategoria: (
              | { tipo: "biblioteca"; item: BibliotecaAudioItem }
              | { tipo: "propaganda"; item: Patrocinador }
            )[] = [
              ...vinhetas.filter((v) => v.categoria_id === categoriaId).map((item) => ({ tipo: "biblioteca" as const, item })),
              ...propagandas
                .filter((p) => p.categoria_id === categoriaId)
                .map((item) => ({ tipo: "propaganda" as const, item })),
            ].sort((a, b) => a.item.nome.localeCompare(b.item.nome));

            return (
              <section
                key={categoriaId ?? "sem-categoria"}
                className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-5"
              >
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <h2 className="font-display text-base font-bold text-fg">{categoria.nome}</h2>
                    {categoria.tipo && (
                      <span className="rounded-full bg-fg/5 px-2 py-0.5 text-[10px] font-mono uppercase tracking-wide text-fg/65">
                        {categoria.tipo === "biblioteca" ? "Biblioteca" : "Propaganda"}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3">
                    {categoriaId !== null && categoria.tipo && (
                      <>
                        <button
                          type="button"
                          onClick={() => setFormCategoria({ id: categoriaId, nome: categoria.nome, tipo: categoria.tipo! })}
                          className="text-xs font-medium text-amber-text hover:text-amber-dim"
                        >
                          Renomear
                        </button>
                        <button
                          type="button"
                          onClick={() => setParaExcluirCategoria({ id: categoriaId, nome: categoria.nome, tipo: categoria.tipo! })}
                          className="text-xs font-medium text-rust-text hover:text-rust/80"
                        >
                          Excluir categoria
                        </button>
                        <button
                          type="button"
                          onClick={() => setFormInsercao(novaInsercaoVazia(categoria.tipo!, categoriaId))}
                          className="text-xs font-medium text-amber-text hover:text-amber-dim"
                        >
                          + Inserção
                        </button>
                      </>
                    )}
                  </div>
                </div>

                {itensDaCategoria.length === 0 ? (
                  <p className="text-sm text-fg/65">Nada cadastrado nessa categoria.</p>
                ) : (
                  <div className="space-y-1.5">
                    {itensDaCategoria.map((entrada) =>
                      entrada.tipo === "biblioteca" ? (
                        <div
                          key={`vinheta-${entrada.item.id}`}
                          className="flex items-center gap-2 rounded-lg border border-border px-2.5 py-1.5 text-sm"
                        >
                          <button
                            type="button"
                            onClick={() => tocarVinheta(entrada.item)}
                            className="shrink-0 text-amber-text hover:text-amber-dim"
                            title="Tocar"
                          >
                            {tocandoId === entrada.item.id ? <LocufySpin size={14} /> : "▶"}
                          </button>
                          <div className="min-w-0 flex-1">
                            <p className={`truncate ${entrada.item.ativo ? "text-fg" : "text-fg/65"}`}>
                              {entrada.item.nome}
                            </p>
                          </div>
                          <span className="shrink-0 font-mono text-xs text-fg/65">
                            {formatarDuracao(entrada.item.duracao_segundos)}
                          </span>
                          <button
                            type="button"
                            onClick={() => editarVinheta(entrada.item)}
                            className="shrink-0 text-xs font-medium text-amber-text hover:text-amber-dim"
                          >
                            Editar
                          </button>
                          <button
                            type="button"
                            onClick={() => setParaExcluirInsercao({ tipo: "biblioteca", item: entrada.item })}
                            className="shrink-0 text-xs font-medium text-rust-text hover:text-rust/80"
                          >
                            Excluir
                          </button>
                        </div>
                      ) : (
                        <div
                          key={`propaganda-${entrada.item.id}`}
                          className="flex items-center gap-2 rounded-lg border border-border px-2.5 py-1.5 text-sm"
                        >
                          <div className="min-w-0 flex-1">
                            <p className={`truncate ${entrada.item.ativo ? "text-fg" : "text-fg/65"}`}>
                              {entrada.item.nome}
                              {!entrada.item.ativo && (
                                <span className="ml-2 text-xs font-medium text-fg/65">(inativo)</span>
                              )}
                            </p>
                            <p className="text-xs text-fg/65 font-mono">
                              {entrada.item.tipo_conteudo === "texto"
                                ? "Texto (TTS)"
                                : `Áudio${entrada.item.audio_nome_original ? ` · ${entrada.item.audio_nome_original}` : ""}`}
                            </p>
                          </div>
                          <button
                            type="button"
                            onClick={() => editarPropaganda(entrada.item)}
                            className="shrink-0 text-xs font-medium text-amber-text hover:text-amber-dim"
                          >
                            Editar
                          </button>
                          <button
                            type="button"
                            onClick={() => setParaExcluirInsercao({ tipo: "propaganda", item: entrada.item })}
                            className="shrink-0 text-xs font-medium text-rust-text hover:text-rust/80"
                          >
                            Excluir
                          </button>
                        </div>
                      )
                    )}
                  </div>
                )}
              </section>
            );
          })}
        </div>
      )}

      <Modal
        open={formCategoria !== null}
        onClose={() => setFormCategoria(null)}
        title={formCategoria?.id === null ? "Nova categoria" : "Renomear categoria"}
      >
        {formCategoria && (
          <form onSubmit={salvarCategoria} className="space-y-4">
            <div>
              <label className={labelClass}>Nome da categoria</label>
              <input
                type="text"
                required
                value={formCategoria.nome}
                onChange={(e) => setFormCategoria({ ...formCategoria, nome: e.target.value })}
                className={inputClass}
                placeholder="Ex.: Vinhetas, Comerciais, Efeitos"
              />
            </div>
            <div>
              <label className={labelClass}>Tipo</label>
              <div className="flex gap-4 text-sm text-fg/80">
                <label className="flex items-center gap-1.5">
                  <input
                    type="radio"
                    checked={formCategoria.tipo === "biblioteca"}
                    onChange={() => setFormCategoria({ ...formCategoria, tipo: "biblioteca" })}
                  />
                  Biblioteca (áudio pro cartwall)
                </label>
                <label className="flex items-center gap-1.5">
                  <input
                    type="radio"
                    checked={formCategoria.tipo === "propaganda"}
                    onChange={() => setFormCategoria({ ...formCategoria, tipo: "propaganda" })}
                  />
                  Propaganda (patrocinador)
                </label>
              </div>
              <p className="text-xs text-fg/65 mt-1.5">
                Define o que pode ser adicionado dentro dessa categoria.
              </p>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setFormCategoria(null)}
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

      <Modal
        open={formInsercao !== null}
        onClose={() => setFormInsercao(null)}
        title={formInsercao?.id === null ? "Nova inserção" : "Editar inserção"}
      >
        {formInsercao && (
          <form onSubmit={salvarInsercao} className="space-y-4">
            <div>
              <label className={labelClass}>Nome</label>
              <input
                type="text"
                required
                value={formInsercao.nome}
                onChange={(e) => setFormInsercao({ ...formInsercao, nome: e.target.value })}
                className={inputClass}
                placeholder={formInsercao.tipo === "biblioteca" ? "Ex.: Vinheta de abertura" : "Ex.: Mercado Bom Preço"}
              />
            </div>

            <div>
              <label className={labelClass}>Categoria</label>
              <SeletorCategoria
                categorias={categorias}
                tipo={formInsercao.tipo}
                value={formInsercao.categoria_id}
                onChange={(categoria_id) => setFormInsercao({ ...formInsercao, categoria_id })}
              />
              <p className="text-xs text-fg/65 mt-1.5">
                {formInsercao.tipo === "biblioteca" ? "Categorias de biblioteca" : "Categorias de propaganda"} apenas.
              </p>
            </div>

            {formInsercao.tipo === "biblioteca" ? (
              <>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className={labelClass}>Cor do card (opcional)</label>
                    <input
                      type="color"
                      value={formInsercao.cor || "#e8a33d"}
                      onChange={(e) => setFormInsercao({ ...formInsercao, cor: e.target.value })}
                      className="h-10 w-full rounded-lg border border-border-strong bg-bg"
                    />
                  </div>
                  <div>
                    <label className={labelClass}>Ordem no cartwall</label>
                    <input
                      type="number"
                      value={formInsercao.ordem}
                      onChange={(e) => setFormInsercao({ ...formInsercao, ordem: Number(e.target.value) })}
                      className={inputClass}
                    />
                  </div>
                </div>
                <div>
                  <label className={labelClass}>Arquivo de áudio (mp3, m4a, wav ou ogg, até 15MB)</label>
                  <input
                    type="file"
                    accept="audio/*,.mp3,.m4a,.wav,.ogg"
                    onChange={(e) => setFormInsercao({ ...formInsercao, arquivo: e.target.files?.[0] ?? null })}
                    className={inputClass}
                  />
                  <p className="text-xs text-fg/65 mt-1.5">
                    {formInsercao.id !== null ? "Deixe em branco pra manter o áudio atual." : "Obrigatório."}
                  </p>
                </div>
                {formInsercao.id !== null && (
                  <label className="flex items-center gap-1.5 text-sm text-fg/80">
                    <input
                      type="checkbox"
                      checked={formInsercao.ativo}
                      onChange={(e) => setFormInsercao({ ...formInsercao, ativo: e.target.checked })}
                    />
                    Ativo (aparece no cartwall do Ao Vivo)
                  </label>
                )}
              </>
            ) : (
              <>
                <div>
                  <label className={labelClass}>Tipo de conteúdo</label>
                  <div className="flex gap-4 text-sm text-fg/80">
                    <label className="flex items-center gap-1.5">
                      <input
                        type="radio"
                        checked={formInsercao.tipo_conteudo === "texto"}
                        onChange={() => setFormInsercao({ ...formInsercao, tipo_conteudo: "texto" })}
                      />
                      Texto (locutor lê ao vivo)
                    </label>
                    <label className="flex items-center gap-1.5">
                      <input
                        type="radio"
                        checked={formInsercao.tipo_conteudo === "audio"}
                        onChange={() => setFormInsercao({ ...formInsercao, tipo_conteudo: "audio" })}
                      />
                      Áudio pronto (upload)
                    </label>
                  </div>
                </div>

                {formInsercao.tipo_conteudo === "texto" ? (
                  <div className="space-y-4">
                    <div>
                      <label className={labelClass}>Texto do anúncio</label>
                      <textarea
                        required
                        rows={4}
                        value={formInsercao.texto}
                        onChange={(e) => setFormInsercao({ ...formInsercao, texto: e.target.value })}
                        className={inputClass}
                        placeholder="Texto exato que o locutor vai ler, sem parafrasear."
                      />
                    </div>
                    {radialistas.length > 1 && (
                      <div>
                        <label className={labelClass}>Voz que lê este patrocinador</label>
                        <VoiceSelect
                          value={formInsercao.voz_id}
                          onChange={(vozId) => setFormInsercao({ ...formInsercao, voz_id: vozId })}
                        />
                        <p className="text-xs text-fg/65 mt-1.5">
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
                      onChange={(e) => setFormInsercao({ ...formInsercao, arquivo: e.target.files?.[0] ?? null })}
                      className={inputClass}
                    />
                    <p className="text-xs text-fg/65 mt-1.5">
                      {formInsercao.id !== null
                        ? "Deixe em branco pra manter o áudio atual."
                        : "Obrigatório pra propaganda em áudio."}
                    </p>
                  </div>
                )}

                {formInsercao.id !== null && (
                  <label className="flex items-center gap-1.5 text-sm text-fg/80">
                    <input
                      type="checkbox"
                      checked={formInsercao.ativo}
                      onChange={(e) => setFormInsercao({ ...formInsercao, ativo: e.target.checked })}
                    />
                    Ativo (aparece pra ser inserido nos blocos do programa)
                  </label>
                )}
              </>
            )}

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setFormInsercao(null)}
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
        open={paraExcluirCategoria !== null}
        title="Excluir categoria"
        mensagem={`Excluir "${paraExcluirCategoria?.nome}"? As inserções dessa categoria passam pra "Sem categoria". Essa ação não pode ser desfeita.`}
        onConfirmar={() => paraExcluirCategoria && excluirCategoria(paraExcluirCategoria)}
        onCancelar={() => setParaExcluirCategoria(null)}
      />

      <ConfirmDialog
        open={paraExcluirInsercao !== null}
        title="Excluir inserção"
        mensagem={`Excluir "${paraExcluirInsercao?.item.nome}"? Essa ação não pode ser desfeita.`}
        onConfirmar={excluirInsercao}
        onCancelar={() => setParaExcluirInsercao(null)}
      />
    </AppShell>
  );
}
