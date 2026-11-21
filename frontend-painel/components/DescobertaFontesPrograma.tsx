"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch, ApiError } from "../lib/api";
import { Programa } from "../lib/types";
import { dominioFonte, linkFonte } from "../lib/fontesPrograma";
import { LocufySpin } from "./LocufyLogo";

type Fonte = { nome: string; dominio: string; url: string; motivo: string };
type Resultado = { status: "ok" | "sem_resultados" | "indisponivel"; fontes: Fonte[] };

type Props = {
  programa: Omit<Programa, "id" | "radio_config_id">;
  criando: boolean;
  suspenso: boolean;
  nomeRadio?: string;
  onAplicar: (noticias: string[], pesquisa: string[], habilitarPesquisa: boolean) => void;
  onBusy: (ocupado: boolean) => void;
};

export default function DescobertaFontesPrograma({ programa, criando, suspenso, nomeRadio, onAplicar, onBusy }: Props) {
  const [automatico, setAutomatico] = useState(criando);
  const [tentativa, setTentativa] = useState(0);
  const [briefingManual, setBriefingManual] = useState("");
  const [concluido, setConcluido] = useState("");
  const [resultado, setResultado] = useState<Resultado | null>(null);
  const [erro, setErro] = useState("");
  const fontesAutomaticas = useRef({ noticias: [] as string[], pesquisa: [] as string[] });
  const programaAtual = useRef(programa);
  programaAtual.current = programa;
  const aplicar = useCallback((urls: string[], remover?: string) => {
    const mesclar = (atuais: string[], anteriores: string[], novas: string[]) => {
      const manuais = atuais.filter((f) => !anteriores.includes(f) && dominioFonte(f) !== remover
        && !novas.some((url) => dominioFonte(url) === dominioFonte(f)));
      return [...new Set([...manuais, ...novas])];
    };
    const atuais = programaAtual.current;
    const novasNoticias = atuais.dose_noticia === "nenhuma" ? [] : urls;
    const noticias = mesclar(atuais.fontes_noticias, fontesAutomaticas.current.noticias, novasNoticias);
    const pesquisa = mesclar(atuais.fontes_pesquisa, fontesAutomaticas.current.pesquisa, urls);
    const gerenciadas = (atuais: string[], anteriores: string[], novas: string[]) => novas.filter((url) => !atuais
      .some((f) => !anteriores.includes(f) && dominioFonte(f) === dominioFonte(url)));
    fontesAutomaticas.current = {
      noticias: gerenciadas(atuais.fontes_noticias, fontesAutomaticas.current.noticias, novasNoticias),
      pesquisa: gerenciadas(atuais.fontes_pesquisa, fontesAutomaticas.current.pesquisa, urls),
    };
    onAplicar(noticias, pesquisa, urls.length > 0);
  }, [onAplicar]);
  const pronto = programa.nome.trim().length >= 3;
  const briefing = JSON.stringify({
    nome: programa.nome.trim(), descricao: programa.descricao, perfil: programa.perfil,
    publico_alvo: programa.publico_alvo, topicos_permitidos: programa.topicos_permitidos,
    topicos_proibidos: programa.topicos_proibidos, tipos_noticias: programa.tipos_noticias,
    generos_musicais: programa.generos_musicais, assuntos_ao_vivo: programa.assuntos_ao_vivo,
    instrucoes_pesquisa: programa.instrucoes_pesquisa,
    dose_noticia: programa.dose_noticia,
  });
  const [briefingInicial] = useState(briefing);
  const [fontesPreenchidas] = useState(() => programa.fontes_pesquisa.length > 0
    && (programa.dose_noticia === "nenhuma" || programa.fontes_noticias.length > 0));
  const identidade = `${briefing}:${tentativa}`;
  const buscar = pronto && !suspenso && ((criando && automatico) || briefingManual === briefing)
    && (!fontesPreenchidas || briefing !== briefingInicial || tentativa > 0);
  const pendente = buscar && concluido !== identidade;

  useEffect(() => {
    onBusy(pendente);
    return () => onBusy(false);
  }, [pendente, onBusy]);

  useEffect(() => {
    if (!buscar || concluido === identidade) return;
    const controller = new AbortController();
    // Espera a pessoa terminar de preencher o contexto antes de consumir uma busca.
    const timer = setTimeout(async () => {
      setErro("");
      try {
        const resposta = await apiFetch<Resultado>("/config/programas/fontes/descobrir", {
          method: "POST", body: JSON.stringify({ ...JSON.parse(briefing), atualizar: tentativa > 0 }), signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        if (resposta.status === "indisponivel") {
          setErro("A busca de fontes está indisponível. Tente novamente ou informe os sites manualmente.");
        } else {
          setResultado(resposta);
          aplicar(resposta.fontes.map((fonte) => fonte.url));
        }
      } catch (err) {
        if (controller.signal.aborted) return;
        setErro(err instanceof ApiError ? err.message : "Não foi possível buscar fontes. Tente novamente.");
      } finally {
        if (!controller.signal.aborted) setConcluido(identidade);
      }
    }, 2000);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [buscar, briefing, identidade, concluido, aplicar, tentativa]);

  function alternar(dominio: string) {
    const candidatos = resultado?.fontes ?? [];
    const selecionados = candidatos.filter((f) => [...programa.fontes_noticias, ...programa.fontes_pesquisa]
      .some((url) => dominioFonte(url) === f.dominio));
    const marcado = selecionados.some((f) => f.dominio === dominio);
    const novos = marcado ? selecionados.filter((f) => f.dominio !== dominio)
      : [...selecionados, ...candidatos.filter((f) => f.dominio === dominio)];
    aplicar(novos.map((f) => f.url), marcado ? dominio : undefined);
  }

  return (
    <section aria-label="Busca de fontes do programa" className="rounded-xl border border-border-strong p-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-fg">Fontes para este programa</h3>
        <button type="button" disabled={!pronto || pendente || suspenso}
          onClick={() => { setBriefingManual(briefing); setTentativa((t) => t + 1); }}
          className="text-sm font-medium text-acento-claro hover:text-acento-dim disabled:opacity-60 disabled:cursor-not-allowed">
          {resultado ? "Atualizar fontes" : "Buscar fontes"}
        </button>
      </div>
      <p className="text-xs text-fg/65">
        Buscamos sites conforme a cidade e o perfil da rádio, os temas e o público do programa.
        Os links de notícias e pesquisa externa ficam vinculados ao programa “{programa.nome || "Novo programa"}”
        {nomeRadio ? `, da rádio ${nomeRadio}.` : ", desta rádio."}
      </p>
      {criando && (
        <label className="flex items-center gap-2 text-sm text-fg/80">
          <input type="checkbox" checked={automatico} onChange={(e) => { setAutomatico(e.target.checked); setBriefingManual(""); }}
            className="h-4 w-4 accent-brand-500" />
          Buscar fontes automaticamente durante a criação
        </label>
      )}
      <div role="status" aria-live="polite" className="text-xs text-fg/65">
        {pendente ? <span className="flex items-center gap-2"><LocufySpin size={14} /> Buscando fontes para o programa…</span>
          : !pronto ? "Preencha o nome e descreva o programa para encontrar fontes mais relevantes."
          : erro || (resultado?.status === "sem_resultados" ? "Nenhuma fonte confirmada para este perfil. Detalhe os temas ou adicione sites manualmente." : "")}
      </div>
      {resultado?.fontes.map((fonte) => (
        <div key={fonte.dominio} className="flex items-start gap-2">
          <input type="checkbox" id={`fonte-descoberta-${fonte.dominio}`} checked={[...programa.fontes_noticias, ...programa.fontes_pesquisa].some((url) => dominioFonte(url) === fonte.dominio)}
            onChange={() => alternar(fonte.dominio)} disabled={pendente || suspenso}
            className="mt-1 h-4 w-4 shrink-0 accent-brand-500" />
          <div className="min-w-0 text-sm">
            <label htmlFor={`fonte-descoberta-${fonte.dominio}`} className="font-medium text-fg">{fonte.nome}</label>{" "}
            <a href={fonte.url} target="_blank" rel="noopener noreferrer" className="break-all text-xs text-acento-claro hover:underline">
              {fonte.dominio} ↗
            </a>
            <p className="text-xs text-fg/65">{fonte.motivo}</p>
          </div>
        </div>
      ))}
      {([
        ["Fontes de notícias do programa", programa.fontes_noticias],
        ["Fontes de pesquisa externa do programa", programa.fontes_pesquisa],
      ] as const).map(([titulo, fontes]) => fontes.length > 0 && (
        <div key={titulo}>
          <h4 className="text-xs font-semibold text-fg/80">{titulo}</h4>
          <ul className="mt-1 space-y-1 text-xs">
            {fontes.map((fonte) => <li key={fonte} className="break-all">
              {linkFonte(fonte) ? <a href={linkFonte(fonte)!} target="_blank" rel="noopener noreferrer" className="text-acento-claro hover:underline">{linkFonte(fonte)} ↗</a> : fonte}
              <button type="button" disabled={pendente || suspenso} aria-label={`${titulo}: remover ${fonte}`}
                className="ml-2 text-fg/65 hover:text-laranja disabled:opacity-60"
                onClick={() => onAplicar(
                  titulo === "Fontes de notícias do programa" ? programa.fontes_noticias.filter((f) => f !== fonte) : programa.fontes_noticias,
                  titulo === "Fontes de pesquisa externa do programa" ? programa.fontes_pesquisa.filter((f) => f !== fonte) : programa.fontes_pesquisa,
                  false,
                )}>Remover</button>
            </li>)}
          </ul>
        </div>
      ))}
      {resultado?.status === "ok" && <p className="text-xs text-fg/65">Revise a seleção. A pesquisa externa é ativada ao adicionar fontes. Feeds RSS podem ser cadastrados em Assuntos e notícias.</p>}
    </section>
  );
}
