"use client";

import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "../lib/api";
import { BLOCOS_PRESET, CategoriaVinheta, normalizarPrograma, Patrocinador, Programa, rotuloBloco } from "../lib/types";
import { estimarDuracaoBloco, formatarDuracaoBloco } from "../lib/duracaoBloco";
import { agruparPorCategoria, BibliotecaAudioItem, formatarDuracao } from "../lib/bibliotecaAudio";
import RadialistasProgramaSection from "./RadialistasProgramaSection";
import { LocufySpin } from "./LocufyLogo";

function semCamposSistema(p: Programa) {
  const { id, radio_config_id, ...dados } = p;
  return dados;
}

function horarioParaSegundos(horario: string): number {
  const [h, m, s] = horario.split(":").map(Number);
  return h * 3600 + m * 60 + (s || 0);
}

function janelaSegundos(programa: Programa): number {
  const inicio = horarioParaSegundos(programa.horario_inicio);
  const fim = horarioParaSegundos(programa.horario_fim);
  return fim >= inicio ? fim - inicio : 24 * 3600 - inicio + fim;
}

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

type ItemArrastavelProps = {
  valor: string;
  onAdicionar: (valor: string) => void;
  children: React.ReactNode;
  className?: string;
};

// Cartao/chip da paleta -- clicavel (adiciona no fim, sempre funciona) e arrastavel (solta
// numa posicao especifica da sequencia). As duas vias fazem a mesma coisa no fundo.
function ItemArrastavel({ valor, onAdicionar, children, className = "" }: ItemArrastavelProps) {
  return (
    <button
      type="button"
      draggable
      onDragStart={(e) => {
        e.dataTransfer.effectAllowed = "copy";
        e.dataTransfer.setData("text/plain", JSON.stringify({ origem: "novo", valor } satisfies PayloadArraste));
      }}
      onClick={() => onAdicionar(valor)}
      className={`cursor-grab active:cursor-grabbing text-left rounded-lg border border-border-strong px-3 py-2 text-sm hover:border-amber/40 hover:bg-paper/5 ${className}`}
    >
      {children}
    </button>
  );
}

type Props = {
  programaId: number;
};

export default function GradeProgramacaoForm({ programaId }: Props) {
  const [programa, setPrograma] = useState<Programa | null>(null);
  const [patrocinadores, setPatrocinadores] = useState<Patrocinador[]>([]);
  const [vinhetas, setVinhetas] = useState<BibliotecaAudioItem[]>([]);
  const [categorias, setCategorias] = useState<CategoriaVinheta[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [mensagem, setMensagem] = useState("");
  const [erro, setErro] = useState("");
  const [texto, setTexto] = useState("");
  const [indiceArrastandoSobre, setIndiceArrastandoSobre] = useState<number | null>(null);

  useEffect(() => {
    setCarregando(true);
    apiFetch<Programa>(`/config/programas/${programaId}`)
      .then((dados) => setPrograma(normalizarPrograma(dados)))
      .catch((err) => setErro(err instanceof ApiError ? err.message : "Erro ao carregar programa"))
      .finally(() => setCarregando(false));
    apiFetch<Patrocinador[]>("/patrocinadores")
      .then(setPatrocinadores)
      .catch(() => setPatrocinadores([]));
    apiFetch<BibliotecaAudioItem[]>("/biblioteca-audio")
      .then(setVinhetas)
      .catch(() => setVinhetas([]));
    apiFetch<CategoriaVinheta[]>("/categorias-vinheta")
      .then(setCategorias)
      .catch(() => setCategorias([]));
  }, [programaId]);

  function atualizarBlocos(blocos: string[]) {
    if (!programa) return;
    setPrograma({ ...programa, estrutura_blocos: blocos });
  }

  function adicionar(bloco: string) {
    const valor = bloco.trim();
    if (!valor || !programa) return;
    atualizarBlocos([...programa.estrutura_blocos, valor]);
    setTexto("");
  }

  function inserirEm(indiceAlvo: number, payload: PayloadArraste) {
    if (!programa) return;
    const blocos = [...programa.estrutura_blocos];
    if (payload.origem === "novo") {
      blocos.splice(indiceAlvo, 0, payload.valor);
    } else {
      if (payload.indice === indiceAlvo || payload.indice === indiceAlvo - 1) return; // ja esta ali
      const [item] = blocos.splice(payload.indice, 1);
      const alvoAjustado = payload.indice < indiceAlvo ? indiceAlvo - 1 : indiceAlvo;
      blocos.splice(alvoAjustado, 0, item);
    }
    atualizarBlocos(blocos);
  }

  function remover(indice: number) {
    if (!programa) return;
    atualizarBlocos(programa.estrutura_blocos.filter((_, i) => i !== indice));
  }

  function mover(indice: number, direcao: -1 | 1) {
    if (!programa) return;
    const novo = indice + direcao;
    if (novo < 0 || novo >= programa.estrutura_blocos.length) return;
    const copia = [...programa.estrutura_blocos];
    [copia[indice], copia[novo]] = [copia[novo], copia[indice]];
    atualizarBlocos(copia);
  }

  async function salvar() {
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
      setMensagem("Programação salva.");
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao salvar");
    } finally {
      setSalvando(false);
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

  const nomesPatrocinadores = Object.fromEntries(patrocinadores.map((p) => [p.id, p.nome]));
  const nomesVinhetas = Object.fromEntries(vinhetas.map((v) => [v.id, v.nome]));
  const rotulo = (bloco: string) => rotuloBloco(bloco, nomesPatrocinadores, nomesVinhetas);
  const duracoes = programa.estrutura_blocos.map((bloco) => estimarDuracaoBloco(bloco, patrocinadores, vinhetas));
  const totalCicloSegundos = duracoes.reduce((soma, d) => soma + d.segundos, 0);
  const janela = janelaSegundos(programa);
  const ciclosNaJanela = totalCicloSegundos > 0 ? janela / totalCicloSegundos : 0;

  const contagemPorTipo = programa.estrutura_blocos.reduce<Record<string, number>>((mapa, bloco) => {
    const r = rotulo(bloco);
    mapa[r] = (mapa[r] ?? 0) + 1;
    return mapa;
  }, {});

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
    <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6">
      <h2 className="font-display text-lg font-bold text-fg mb-1">Montagem de blocos · {programa.nome}</h2>
      <p className="text-sm text-fg/65 mb-5">
        Arraste vinhetas, propagandas e blocos automáticos da paleta pra sequência (ou clique pra adicionar no
        fim). O ao vivo segue essa sequência em loop. Durações abaixo são estimativas -- o motor real varia por
        prosódia e a IA pode inserir blocos extra.
      </p>

      {erro && <p className="text-sm text-rust-text mb-4">{erro}</p>}
      {mensagem && <p className="text-sm text-teal-text mb-4">{mensagem}</p>}

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_320px] gap-6">
        <div>
          {programa.estrutura_blocos.length === 0 ? (
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
              {programa.estrutura_blocos.map((bloco, i) => {
                const duracao = duracoes[i];
                return (
                  <li
                    key={`${bloco}-${i}`}
                    draggable
                    onDragStart={(e) => {
                      e.dataTransfer.effectAllowed = "move";
                      e.dataTransfer.setData(
                        "text/plain",
                        JSON.stringify({ origem: "sequencia", indice: i } satisfies PayloadArraste)
                      );
                    }}
                    {...dropHandlers(i)}
                    className={`flex items-center gap-3 rounded-xl border px-4 py-3 cursor-grab active:cursor-grabbing ${
                      indiceArrastandoSobre === i
                        ? "border-amber/60 bg-amber/5"
                        : "border-border-strong bg-bg"
                    }`}
                  >
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
                        disabled={i === programa.estrutura_blocos.length - 1}
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
                {...dropHandlers(programa.estrutura_blocos.length)}
                className={`rounded-lg border border-dashed px-4 py-2 text-center text-xs text-fg/65 ${
                  indiceArrastandoSobre === programa.estrutura_blocos.length
                    ? "border-amber/60 bg-amber/5"
                    : "border-border"
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

          <div className="rounded-xl border border-border bg-bg p-4">
            <p className="text-sm font-medium text-fg">
              1 volta completa da estrutura ≈ {formatarDuracaoBloco(totalCicloSegundos)}
            </p>
            {totalCicloSegundos > 0 && (
              <p className="text-xs text-fg/65 mt-1">
                Na janela do programa ({formatarDuracaoBloco(janela)}), isso dá aproximadamente{" "}
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

          <button
            type="button"
            onClick={salvar}
            disabled={salvando}
            className="mt-4 rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-ink hover:bg-brand-600 disabled:opacity-60"
          >
            {salvando ? "Salvando..." : "Salvar programação"}
          </button>
        </div>

        <div className="space-y-5">
          <section>
            <h3 className="font-mono text-xs uppercase tracking-wide text-amber-text mb-2">Blocos automáticos</h3>
            <div className="grid grid-cols-2 gap-1.5">
              {BLOCOS_PRESET.map((preset) => (
                <ItemArrastavel key={preset.value} valor={preset.value} onAdicionar={adicionar}>
                  + {preset.label}
                </ItemArrastavel>
              ))}
            </div>
          </section>

          <section>
            <h3 className="font-mono text-xs uppercase tracking-wide text-amber-text mb-2">Vinhetas</h3>
            {vinhetas.length === 0 ? (
              <p className="text-xs text-fg/65">Nenhuma vinheta cadastrada. Suba em /vinhetagem.</p>
            ) : (
              <div className="space-y-3">
                {agruparPorCategoria(vinhetas, categoriasVinheta).map(([categoria, itens]) => (
                  <div key={categoria.id ?? "sem-categoria-vinheta"}>
                    <p className="text-[10px] font-mono font-medium text-fg/65 uppercase tracking-wide mb-1">
                      {categoria.nome}
                    </p>
                    <div className="space-y-1">
                      {itens.map((v) => (
                        <ItemArrastavel key={v.id} valor={`vinheta:${v.id}`} onAdicionar={adicionar} className="w-full flex items-center justify-between gap-2">
                          <span className="truncate">{v.nome}</span>
                          <span className="shrink-0 font-mono text-xs text-fg/65">{formatarDuracao(v.duracao_segundos)}</span>
                        </ItemArrastavel>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section>
            <h3 className="font-mono text-xs uppercase tracking-wide text-amber-text mb-2">Propagandas</h3>
            {patrocinadores.length === 0 ? (
              <p className="text-xs text-fg/65">Nenhuma propaganda cadastrada. Cadastre em /vinhetagem.</p>
            ) : (
              <div className="space-y-3">
                {agruparPorCategoria(patrocinadores, categoriasPropaganda).map(([categoria, itens]) => (
                  <div key={categoria.id ?? "sem-categoria-propaganda"}>
                    <p className="text-[10px] font-mono font-medium text-fg/65 uppercase tracking-wide mb-1">
                      {categoria.nome}
                    </p>
                    <div className="space-y-1">
                      {itens
                        .filter((p) => p.ativo)
                        .map((p) => (
                          <ItemArrastavel key={p.id} valor={`patrocinador:${p.id}`} onAdicionar={adicionar} className="w-full block">
                            <span className="truncate block">{p.nome}</span>
                          </ItemArrastavel>
                        ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section>
            <h3 className="font-mono text-xs uppercase tracking-wide text-amber-text mb-2">Elenco do programa</h3>
            <p className="text-xs text-fg/65 mb-2">
              Quem participa do diálogo -- o motor já monta a conversa entre todos automaticamente, sem precisar
              apontar radialista por bloco.
            </p>
            <RadialistasProgramaSection programaId={programaId} />
          </section>
        </div>
      </div>
    </div>
  );
}
