"use client";

import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "../lib/api";
import { FONTE_NOTICIA_VAZIA, FonteNoticia } from "../lib/types";
import { LocufySpin } from "./LocufyLogo";

const inputClass =
  "w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg placeholder:text-fg/65 focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20";

const TIPO_LABEL: Record<FonteNoticia["tipo"], string> = {
  oficial: "Órgão oficial",
  imprensa: "Imprensa",
  assessoria: "Assessoria",
};

// Fontes de notícia são da conta (não do programa) -- alimentam o worker de apuração que roda
// fora do ao vivo (ver backend app/news/worker.py) e viram pauta real pra qualquer programa que
// tenha bloco de notícia/escalada/giro/serviço/plantão, via CRUD em /config/fontes-noticia.
export default function FontesNoticiaSection() {
  const [fontes, setFontes] = useState<FonteNoticia[] | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");
  const [novaFonte, setNovaFonte] = useState<Omit<FonteNoticia, "id">>(FONTE_NOTICIA_VAZIA);
  const [salvandoId, setSalvandoId] = useState<number | "nova" | null>(null);
  const [gerandoSeeds, setGerandoSeeds] = useState(false);

  function carregar() {
    setCarregando(true);
    apiFetch<FonteNoticia[]>("/config/fontes-noticia")
      .then((dados) => setFontes(Array.isArray(dados) ? dados : []))
      .catch((err) => setErro(err instanceof ApiError ? err.message : "Erro ao carregar fontes de notícia"))
      .finally(() => setCarregando(false));
  }

  useEffect(carregar, []);

  async function adicionar() {
    if (!novaFonte.nome.trim()) return;
    setSalvandoId("nova");
    setErro("");
    try {
      const criada = await apiFetch<FonteNoticia>("/config/fontes-noticia", {
        method: "POST",
        body: JSON.stringify(novaFonte),
      });
      setFontes((atual) => [...(atual ?? []), criada]);
      setNovaFonte(FONTE_NOTICIA_VAZIA);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao adicionar fonte");
    } finally {
      setSalvandoId(null);
    }
  }

  async function salvar(fonte: FonteNoticia) {
    setSalvandoId(fonte.id);
    setErro("");
    try {
      const atualizada = await apiFetch<FonteNoticia>(`/config/fontes-noticia/${fonte.id}`, {
        method: "PUT",
        body: JSON.stringify(fonte),
      });
      setFontes((atual) => atual?.map((f) => (f.id === atualizada.id ? atualizada : f)) ?? atual);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao salvar fonte");
    } finally {
      setSalvandoId(null);
    }
  }

  function atualizarLocal(id: number, campo: keyof FonteNoticia, valor: string | boolean | number) {
    setFontes((atual) => atual?.map((f) => (f.id === id ? { ...f, [campo]: valor } : f)) ?? atual);
  }

  async function remover(id: number) {
    setSalvandoId(id);
    setErro("");
    try {
      await apiFetch(`/config/fontes-noticia/${id}`, { method: "DELETE" });
      setFontes((atual) => atual?.filter((f) => f.id !== id) ?? atual);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao remover fonte");
    } finally {
      setSalvandoId(null);
    }
  }

  async function gerarSugestoes() {
    setGerandoSeeds(true);
    setErro("");
    try {
      const criadas = await apiFetch<FonteNoticia[]>("/config/fontes-noticia/seeds", { method: "POST" });
      setFontes((atual) => [...(atual ?? []), ...criadas]);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao gerar sugestões de fonte");
    } finally {
      setGerandoSeeds(false);
    }
  }

  if (carregando) {
    return (
      <p className="flex items-center gap-2 text-sm text-fg/65">
        <LocufySpin size={16} /> Carregando fontes de notícia...
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-fg/65">
        Feed RSS de cada fonte é coletado periodicamente e vira pauta real pros blocos de notícia
        (ver worker de apuração). Sem URL de feed preenchida, a fonte fica cadastrada mas fora da
        coleta.
      </p>

      {erro && <p className="text-sm text-rust-text">{erro}</p>}

      <div className="space-y-2">
        {(fontes ?? []).map((fonte) => (
          <div key={fonte.id} className="rounded-lg border border-border-strong p-3 space-y-2">
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium text-fg">{fonte.nome}</span>
              <div className="flex items-center gap-3">
                <label className="inline-flex items-center gap-1.5 text-xs text-fg/70">
                  <input
                    type="checkbox"
                    checked={fonte.ativa}
                    onChange={(e) => {
                      atualizarLocal(fonte.id, "ativa", e.target.checked);
                      salvar({ ...fonte, ativa: e.target.checked });
                    }}
                    className="h-3.5 w-3.5 rounded border-border-strong bg-bg text-amber-text focus:ring-amber/40"
                  />
                  Ativa
                </label>
                <button
                  type="button"
                  onClick={() => remover(fonte.id)}
                  disabled={salvandoId === fonte.id}
                  className="text-xs font-medium text-rust-text hover:text-rust/80 disabled:opacity-60"
                >
                  Remover
                </button>
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-[1fr_auto] gap-2">
              <input
                className={inputClass}
                placeholder="URL do feed RSS/Atom (ex.: https://prefeitura.exemplo.gov.br/feed)"
                value={fonte.url_feed}
                onChange={(e) => atualizarLocal(fonte.id, "url_feed", e.target.value)}
              />
              <select
                className={inputClass}
                value={fonte.tipo}
                onChange={(e) => atualizarLocal(fonte.id, "tipo", e.target.value)}
              >
                {Object.entries(TIPO_LABEL).map(([valor, label]) => (
                  <option key={valor} value={valor}>{label}</option>
                ))}
              </select>
            </div>
            <div>
              <button
                type="button"
                onClick={() => salvar(fonte)}
                disabled={salvandoId === fonte.id}
                className="rounded-lg border border-border-strong px-3 py-1.5 text-xs font-medium text-fg/80 hover:bg-paper/5 disabled:opacity-60"
              >
                {salvandoId === fonte.id ? "Salvando..." : "Salvar"}
              </button>
            </div>
          </div>
        ))}
        {(fontes ?? []).length === 0 && (
          <p className="text-sm text-fg/65">Nenhuma fonte de notícia cadastrada ainda.</p>
        )}
      </div>

      <div className="rounded-lg border border-dashed border-border-strong p-3 space-y-2">
        <p className="text-xs font-medium text-fg/70">Nova fonte</p>
        <div className="grid grid-cols-1 sm:grid-cols-[1fr_1fr_auto] gap-2">
          <input
            className={inputClass}
            placeholder="Nome (ex.: Defesa Civil de Blumenau)"
            value={novaFonte.nome}
            onChange={(e) => setNovaFonte({ ...novaFonte, nome: e.target.value })}
          />
          <input
            className={inputClass}
            placeholder="URL do feed (opcional por enquanto)"
            value={novaFonte.url_feed}
            onChange={(e) => setNovaFonte({ ...novaFonte, url_feed: e.target.value })}
          />
          <select
            className={inputClass}
            value={novaFonte.tipo}
            onChange={(e) => setNovaFonte({ ...novaFonte, tipo: e.target.value as FonteNoticia["tipo"] })}
          >
            {Object.entries(TIPO_LABEL).map(([valor, label]) => (
              <option key={valor} value={valor}>{label}</option>
            ))}
          </select>
        </div>
        <button
          type="button"
          onClick={adicionar}
          disabled={salvandoId === "nova" || !novaFonte.nome.trim()}
          className="rounded-lg border border-border-strong px-3 py-1.5 text-xs font-medium text-fg/80 hover:bg-paper/5 disabled:opacity-60"
        >
          {salvandoId === "nova" ? "Adicionando..." : "+ Adicionar fonte"}
        </button>
      </div>

      <button
        type="button"
        onClick={gerarSugestoes}
        disabled={gerandoSeeds}
        className="text-xs font-medium text-amber-text hover:text-amber-dim disabled:opacity-60"
      >
        {gerandoSeeds ? "Gerando..." : "Sugerir fontes oficiais pela cidade da rádio"}
      </button>
    </div>
  );
}
