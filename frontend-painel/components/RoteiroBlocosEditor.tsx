"use client";

import { useState } from "react";
import { apiFetchBlob, ApiError } from "../lib/api";
import { BLOCOS_PRESET, CategoriaVinheta, Patrocinador, rotuloBloco } from "../lib/types";
import { estimarDuracaoBloco, formatarDuracaoBloco } from "../lib/duracaoBloco";
import { agruparPorCategoria, BibliotecaAudioItem, formatarDuracao } from "../lib/bibliotecaAudio";
import { CORES_BLOCO, kindDoBloco, LEGENDA_BLOCO_KIND } from "../lib/blocoVisual";
import { LocufySpin } from "./LocufyLogo";

// Payload trocado via dataTransfer no drag-and-drop: "novo" = item vindo da paleta (ainda nao
// esta na sequencia), "sequencia" = reordenando um bloco que ja esta na sequencia (por indice,
// nao por valor -- a sequencia pode ter blocos repetidos, ex. duas "Musica").
type PayloadArraste = { origem: "novo"; valor: string } | { origem: "sequencia"; indice: number };

function lerPayloadArraste(e: React.DragEvent): PayloadArraste | null {
  try {
    return JSON.parse(e.dataTransfer.getData("text/plain"));
  } catch {
    return null;
  }
}

function iniciarArraste(e: React.DragEvent, payload: PayloadArraste, effect: "copy" | "move") {
  e.dataTransfer.effectAllowed = effect;
  e.dataTransfer.setData("text/plain", JSON.stringify(payload));
}

type Props = {
  blocos: string[];
  onChange: (blocos: string[]) => void;
  patrocinadores: Patrocinador[];
  vinhetas: BibliotecaAudioItem[];
  categorias: CategoriaVinheta[];
  janelaSegundos?: number;
};

export default function RoteiroBlocosEditor({
  blocos,
  onChange,
  patrocinadores,
  vinhetas,
  categorias,
  janelaSegundos,
}: Props) {
  const [texto, setTexto] = useState("");
  const [filtroPaleta, setFiltroPaleta] = useState("");
  const [indiceArrastandoSobre, setIndiceArrastandoSobre] = useState<number | null>(null);
  const [tocandoId, setTocandoId] = useState<number | null>(null);
  const [carregandoId, setCarregandoId] = useState<number | null>(null);
  const [erroAudio, setErroAudio] = useState("");

  function adicionar(bloco: string) {
    const valor = bloco.trim();
    if (!valor) return;
    onChange([...blocos, valor]);
    setTexto("");
  }

  function inserirEm(indiceAlvo: number, payload: PayloadArraste) {
    const copia = [...blocos];
    if (payload.origem === "novo") {
      copia.splice(indiceAlvo, 0, payload.valor);
    } else {
      if (payload.indice === indiceAlvo || payload.indice === indiceAlvo - 1) return; // ja esta ali
      const [item] = copia.splice(payload.indice, 1);
      const alvoAjustado = payload.indice < indiceAlvo ? indiceAlvo - 1 : indiceAlvo;
      copia.splice(alvoAjustado, 0, item);
    }
    onChange(copia);
  }

  function remover(indice: number) {
    onChange(blocos.filter((_, i) => i !== indice));
  }

  function mover(indice: number, direcao: -1 | 1) {
    const novo = indice + direcao;
    if (novo < 0 || novo >= blocos.length) return;
    const copia = [...blocos];
    [copia[indice], copia[novo]] = [copia[novo], copia[indice]];
    onChange(copia);
  }

  async function tocarPreview(item: BibliotecaAudioItem, e: React.MouseEvent) {
    e.stopPropagation();
    if (tocandoId === item.id) {
      setTocandoId(null);
      return;
    }
    setErroAudio("");
    setCarregandoId(item.id);
    try {
      const blob = await apiFetchBlob(`/biblioteca-audio/${item.id}/audio`);
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      setTocandoId(item.id);
      audio.onended = () => {
        URL.revokeObjectURL(url);
        setTocandoId((atual) => (atual === item.id ? null : atual));
      };
      await audio.play();
    } catch (err) {
      setErroAudio(err instanceof ApiError ? err.message : "Erro ao tocar áudio");
      setTocandoId(null);
    } finally {
      setCarregandoId(null);
    }
  }

  const nomesPatrocinadores = Object.fromEntries(patrocinadores.map((p) => [p.id, p.nome]));
  const nomesVinhetas = Object.fromEntries(vinhetas.map((v) => [v.id, v.nome]));
  const rotulo = (bloco: string) => rotuloBloco(bloco, nomesPatrocinadores, nomesVinhetas);
  const duracoes = blocos.map((bloco) => estimarDuracaoBloco(bloco, patrocinadores, vinhetas));
  const totalCicloSegundos = duracoes.reduce((soma, d) => soma + d.segundos, 0);
  const ciclosNaJanela =
    janelaSegundos && totalCicloSegundos > 0 ? janelaSegundos / totalCicloSegundos : null;

  const contagemPorTipo = blocos.reduce<Record<string, number>>((mapa, bloco) => {
    const r = rotulo(bloco);
    mapa[r] = (mapa[r] ?? 0) + 1;
    return mapa;
  }, {});

  function corDoBloco(tipo: string): { dot: string; borda: string; fundo: string } {
    return CORES_BLOCO[kindDoBloco(tipo)];
  }

  const filtro = filtroPaleta.trim().toLowerCase();
  const presetsFiltrados = filtro ? BLOCOS_PRESET.filter((p) => p.label.toLowerCase().includes(filtro)) : BLOCOS_PRESET;
  const vinhetasFiltradas = filtro ? vinhetas.filter((v) => v.nome.toLowerCase().includes(filtro)) : vinhetas;
  const patrocinadoresFiltrados = (filtro
    ? patrocinadores.filter((p) => p.nome.toLowerCase().includes(filtro))
    : patrocinadores
  ).filter((p) => p.ativo);

  const categoriasVinheta = categorias.filter((c) => c.tipo === "biblioteca");
  const categoriasPropaganda = categorias.filter((c) => c.tipo === "propaganda");

  function dropHandlers(indiceAlvo: number) {
    return {
      onDragOver: (e: React.DragEvent) => {
        e.preventDefault();
        setIndiceArrastandoSobre(indiceAlvo);
      },
      onDragLeave: () => setIndiceArrastandoSobre((atual) => (atual === indiceAlvo ? null : atual)),
      onDrop: (e: React.DragEvent) => {
        e.preventDefault();
        setIndiceArrastandoSobre(null);
        const payload = lerPayloadArraste(e);
        if (payload) inserirEm(indiceAlvo, payload);
      },
    };
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_320px] gap-6">
      <div>
        {blocos.length > 0 && (
          <div className="mb-3">
            <div className="flex h-2 w-full overflow-hidden rounded-full bg-bg border border-border-strong">
              {blocos.map((bloco, i) => {
                const cor = corDoBloco(bloco);
                const pct = totalCicloSegundos > 0 ? (duracoes[i].segundos / totalCicloSegundos) * 100 : 0;
                return (
                  <div
                    key={`${bloco}-${i}`}
                    style={{ flexBasis: `${pct}%` }}
                    className={`h-full shrink-0 ${cor.dot}`}
                    title={`${rotulo(bloco)} · ${formatarDuracaoBloco(duracoes[i].segundos)}`}
                  />
                );
              })}
            </div>
            <div className="flex items-center gap-3 mt-1.5">
              {(Object.keys(LEGENDA_BLOCO_KIND) as (keyof typeof LEGENDA_BLOCO_KIND)[]).map((kind) => (
                <span key={kind} className="flex items-center gap-1 text-[10px] text-fg/65">
                  <span className={`h-1.5 w-1.5 rounded-full ${CORES_BLOCO[kind].dot}`} />
                  {LEGENDA_BLOCO_KIND[kind]}
                </span>
              ))}
            </div>
          </div>
        )}

        {blocos.length === 0 ? (
          <div
            {...dropHandlers(0)}
            className={`rounded-xl border border-dashed p-6 text-center text-sm text-fg/65 ${
              indiceArrastandoSobre === 0 ? "border-amber/60 bg-amber/5" : "border-border-strong"
            }`}
          >
            Sequência vazia -- o ao vivo usa o roteiro padrão (abertura, música, comentário, notícia, chamada ao
            ouvinte). Arraste um item da paleta ao lado pra começar.
          </div>
        ) : (
          <ol className="space-y-2 mb-2">
            {blocos.map((bloco, i) => {
              const duracao = duracoes[i];
              const cor = corDoBloco(bloco);
              return (
                <li
                  key={`${bloco}-${i}`}
                  draggable
                  onDragStart={(e) => iniciarArraste(e, { origem: "sequencia", indice: i }, "move")}
                  {...dropHandlers(i)}
                  className={`flex items-center gap-3 rounded-xl border px-4 py-3 cursor-grab active:cursor-grabbing ${
                    indiceArrastandoSobre === i ? "border-amber/60 bg-amber/5" : `${cor.borda} bg-bg`
                  }`}
                >
                  <span className={`h-2 w-2 shrink-0 rounded-full ${cor.dot}`} />
                  <span className="font-mono text-xs text-fg/65 w-5 shrink-0">{i + 1}</span>
                  <span className="flex-1 min-w-0 text-sm font-medium text-fg truncate">{rotulo(bloco)}</span>
                  <span className="shrink-0 font-mono text-xs text-fg/65">
                    ~{formatarDuracaoBloco(duracao.segundos)}
                    {duracao.estimada ? "" : " (real)"}
                  </span>
                  <span className="flex items-center shrink-0">
                    <button
                      type="button"
                      onClick={() => mover(i, -1)}
                      disabled={i === 0}
                      className="text-amber-text/70 hover:text-amber-text leading-none px-1 disabled:opacity-25"
                      title="Mover pra cima"
                    >
                      ‹
                    </button>
                    <button
                      type="button"
                      onClick={() => mover(i, 1)}
                      disabled={i === blocos.length - 1}
                      className="text-amber-text/70 hover:text-amber-text leading-none px-1 disabled:opacity-25"
                      title="Mover pra baixo"
                    >
                      ›
                    </button>
                    <button
                      type="button"
                      onClick={() => remover(i)}
                      className="text-amber-text/70 hover:text-amber-text leading-none text-base px-1"
                      title="Remover"
                    >
                      ×
                    </button>
                  </span>
                </li>
              );
            })}
            <li
              {...dropHandlers(blocos.length)}
              className={`rounded-lg border border-dashed px-4 py-2 text-center text-xs text-fg/65 ${
                indiceArrastandoSobre === blocos.length ? "border-amber/60 bg-amber/5" : "border-border"
              }`}
            >
              soltar aqui adiciona no fim
            </li>
          </ol>
        )}

        <div className="flex gap-2 my-4">
          <input
            type="text"
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                adicionar(texto);
              }
            }}
            placeholder="Bloco personalizado e pressione Enter"
            className="flex-1 min-w-0 rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg placeholder:text-fg/65 focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
          />
          <button
            type="button"
            onClick={() => adicionar(texto)}
            className="rounded-lg border border-border-strong px-3 py-2 text-sm font-medium text-fg/80 hover:bg-paper/5"
          >
            Adicionar
          </button>
        </div>

        {totalCicloSegundos > 0 && (
          <div className="rounded-xl border border-border bg-bg p-4">
            <p className="text-sm font-medium text-fg">
              1 volta completa da estrutura ≈ {formatarDuracaoBloco(totalCicloSegundos)}
            </p>
            {ciclosNaJanela !== null && (
              <p className="text-xs text-fg/65 mt-1">
                Na janela do programa ({formatarDuracaoBloco(janelaSegundos!)}), isso dá aproximadamente{" "}
                {ciclosNaJanela < 1 ? ciclosNaJanela.toFixed(1) : Math.round(ciclosNaJanela)} volta(s) -- estimativa,
                o motor real varia por prosódia e blocos extra da IA.
              </p>
            )}
            {Object.keys(contagemPorTipo).length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-3">
                {Object.entries(contagemPorTipo).map(([r, qtd]) => (
                  <span key={r} className="rounded-full bg-paper/5 px-2.5 py-1 font-mono text-xs font-medium text-fg/60">
                    {r} × {qtd}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="space-y-5">
        <div>
          <input
            type="text"
            value={filtroPaleta}
            onChange={(e) => setFiltroPaleta(e.target.value)}
            placeholder="Buscar na paleta..."
            className="w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg placeholder:text-fg/65 focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
          />
        </div>

        {erroAudio && <p className="text-xs text-rust-text">{erroAudio}</p>}

        {presetsFiltrados.length > 0 && (
          <section>
            <h3 className="font-mono text-xs uppercase tracking-wide text-amber-text mb-2">Blocos automáticos</h3>
            <div className="grid grid-cols-2 gap-1.5">
              {presetsFiltrados.map((preset) => {
                const cor = corDoBloco(preset.value);
                return (
                  <button
                    key={preset.value}
                    type="button"
                    draggable
                    onDragStart={(e) => iniciarArraste(e, { origem: "novo", valor: preset.value }, "copy")}
                    onClick={() => adicionar(preset.value)}
                    className={`cursor-grab active:cursor-grabbing flex items-center gap-1.5 text-left rounded-lg border px-3 py-2 text-sm hover:border-amber/40 hover:bg-paper/5 ${cor.borda}`}
                  >
                    <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${cor.dot}`} />+ {preset.label}
                  </button>
                );
              })}
            </div>
          </section>
        )}

        {vinhetasFiltradas.length > 0 && (
          <section>
            <h3 className="font-mono text-xs uppercase tracking-wide text-amber-text mb-2">Vinhetas</h3>
            <div className="space-y-3">
              {agruparPorCategoria(vinhetasFiltradas, categoriasVinheta).map(([categoria, itens]) => (
                <div key={categoria.id ?? "sem-categoria-vinheta"}>
                  <p className="text-[10px] font-mono font-medium text-fg/65 uppercase tracking-wide mb-1">
                    {categoria.nome}
                  </p>
                  <div className="space-y-1">
                    {itens.map((v) => {
                      const cor = corDoBloco(`vinheta:${v.id}`);
                      const corPersonalizada = v.cor ?? undefined;
                      return (
                        <div
                          key={v.id}
                          data-testid={`vinheta-paleta-${v.id}`}
                          draggable
                          onDragStart={(e) => iniciarArraste(e, { origem: "novo", valor: `vinheta:${v.id}` }, "copy")}
                          className={`cursor-grab active:cursor-grabbing flex items-center gap-2 rounded-lg border px-2.5 py-1.5 text-sm hover:border-amber/40 hover:bg-paper/5 ${cor.borda}`}
                        >
                          <button
                            type="button"
                            onClick={(e) => tocarPreview(v, e)}
                            className="shrink-0 text-amber-text hover:text-amber-dim"
                            title="Ouvir"
                          >
                            {carregandoId === v.id ? (
                              <LocufySpin size={12} />
                            ) : tocandoId === v.id ? (
                              "■"
                            ) : (
                              "▶"
                            )}
                          </button>
                          <span
                            className={`h-1.5 w-1.5 shrink-0 rounded-full ${corPersonalizada ? "" : cor.dot}`}
                            style={corPersonalizada ? { backgroundColor: corPersonalizada } : undefined}
                          />
                          <button type="button" onClick={() => adicionar(`vinheta:${v.id}`)} className="min-w-0 flex-1 flex items-center justify-between gap-2 text-left">
                            <span className="truncate">{v.nome}</span>
                            <span className="shrink-0 font-mono text-xs text-fg/65">{formatarDuracao(v.duracao_segundos)}</span>
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {vinhetas.length === 0 && !filtro && (
          <section>
            <h3 className="font-mono text-xs uppercase tracking-wide text-amber-text mb-2">Vinhetas</h3>
            <p className="text-xs text-fg/65">Nenhuma vinheta cadastrada. Suba em /vinhetagem.</p>
          </section>
        )}

        {patrocinadoresFiltrados.length > 0 && (
          <section>
            <h3 className="font-mono text-xs uppercase tracking-wide text-amber-text mb-2">Propagandas</h3>
            <div className="space-y-3">
              {agruparPorCategoria(patrocinadoresFiltrados, categoriasPropaganda).map(([categoria, itens]) => (
                <div key={categoria.id ?? "sem-categoria-propaganda"}>
                  <p className="text-[10px] font-mono font-medium text-fg/65 uppercase tracking-wide mb-1">
                    {categoria.nome}
                  </p>
                  <div className="space-y-1">
                    {itens.map((p) => {
                      const cor = corDoBloco(`patrocinador:${p.id}`);
                      return (
                        <button
                          key={p.id}
                          type="button"
                          draggable
                          onDragStart={(e) => iniciarArraste(e, { origem: "novo", valor: `patrocinador:${p.id}` }, "copy")}
                          onClick={() => adicionar(`patrocinador:${p.id}`)}
                          className={`cursor-grab active:cursor-grabbing flex items-center gap-1.5 w-full text-left rounded-lg border px-3 py-2 text-sm hover:border-amber/40 hover:bg-paper/5 ${cor.borda}`}
                        >
                          <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${cor.dot}`} />
                          <span className="truncate">{p.nome}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {patrocinadores.filter((p) => p.ativo).length === 0 && !filtro && (
          <section>
            <h3 className="font-mono text-xs uppercase tracking-wide text-amber-text mb-2">Propagandas</h3>
            <p className="text-xs text-fg/65">Nenhuma propaganda cadastrada. Cadastre em /vinhetagem.</p>
          </section>
        )}
      </div>
    </div>
  );
}
