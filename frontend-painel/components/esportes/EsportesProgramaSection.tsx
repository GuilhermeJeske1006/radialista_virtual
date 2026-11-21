"use client";

import { useEffect, useRef, useState } from "react";
import { FontesEditor, PerfilEditor, botao, campo, Campo, primario } from "./ConfiguracaoEsportiva";
import EdicaoEditor from "./EdicaoEditor";
import { apiFetch } from "../../lib/api";
import { ConteudoEsportivo, dataNoFuso, EdicaoEsportiva, FonteEsportiva, isoNoFuso, PerfilEsportivo, ResumoEdicao, rotuloEstado } from "../../lib/esportes";
import { Programa } from "../../lib/types";
import { modeloEsportivoDoPrograma, proximaExibicaoEsportiva } from "../../lib/esportes";

export default function EsportesProgramaSection({ programa, onDirty, onBusy }: {
  programa: Programa;
  onDirty?: (pendente: boolean) => void;
  onBusy?: (ocupado: boolean) => void;
}) {
  const programaId = programa.id;
  const [perfil, setPerfil] = useState<PerfilEsportivo | null>(null);
  const [fontes, setFontes] = useState<FonteEsportiva[]>([]);
  const [edicoes, setEdicoes] = useState<ResumoEdicao[]>([]);
  const [edicao, setEdicao] = useState<EdicaoEsportiva | null>(null);
  const [aba, setAba] = useState<"producao" | "perfil" | "fontes">("producao");
  const [modelo, setModelo] = useState<ConteudoEsportivo['modelo']>(() => modeloEsportivoDoPrograma(programa));
  const [exibicao, setExibicao] = useState("");
  const [carregando, setCarregando] = useState(true);
  const [ocupado, setOcupado] = useState(false);
  const [edicaoPendente, setSujo] = useState(false);
  const [configuracaoPendente, setConfiguracaoPendente] = useState(false);
  const [configuracaoOcupada, setConfiguracaoOcupada] = useState(false);
  const sujo = edicaoPendente || configuracaoPendente;
  const [ocupadoEditor, setOcupadoEditor] = useState(false);
  const [erro, setErro] = useState("");
  const sujoRef = useRef(false);
  const programaRef = useRef(programaId);
  sujoRef.current = sujo;
  programaRef.current = programaId;
  useEffect(() => { onDirty?.(sujo); return () => onDirty?.(false); }, [sujo, onDirty]);
  useEffect(() => { onBusy?.(ocupado || ocupadoEditor || configuracaoOcupada); return () => onBusy?.(false); }, [ocupado, ocupadoEditor, configuracaoOcupada, onBusy]);
  useEffect(() => {
    let ativo = true;
    setCarregando(true);
    setErro("");
    Promise.all([
      apiFetch<FonteEsportiva[]>("/esportes/fontes"),
      apiFetch<PerfilEsportivo>(`/esportes/programas/${programaId}/perfil`),
      apiFetch<ResumoEdicao[]>(`/esportes/programas/${programaId}/edicoes`),
    ]).then(([f, p, e]) => {
      if (!ativo) return;
      setFontes(f);
      setPerfil(p);
      setEdicoes(e);
      setExibicao(proximaExibicaoEsportiva(programa, p.fuso));
    }).catch((e) => {
      if (ativo) setErro(e instanceof Error ? e.message : "Erro ao carregar a produção esportiva.");
    }).finally(() => { if (ativo) setCarregando(false); });
    return () => { ativo = false; };
    // O componente é remontado ao trocar o programa; alterações do cadastro não descartam a edição aberta.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [programaId]);
  // Revalida validade e bloqueio de fontes durante a revisão, sem sobrescrever edições locais.
  useEffect(() => {
    if (!edicao || sujo || ocupado || ocupadoEditor) return;
    const id = window.setInterval(() => {
      apiFetch<EdicaoEsportiva>(`/esportes/edicoes/${edicao.id}`).then((atual) => {
        if (sujoRef.current || atual.programa_id !== programaRef.current) return;
        setEdicao((anterior) => anterior && anterior.id === atual.id && JSON.stringify(anterior) !== JSON.stringify(atual) ? atual : anterior);
      }).catch((e) => setErro(e instanceof Error ? e.message : "Falha ao revalidar a edição."));
    }, 30_000);
    return () => window.clearInterval(id);
  }, [edicao?.id, sujo, ocupado, ocupadoEditor]);
  function receberEdicao(e: EdicaoEsportiva) {
    setEdicao(e); setSujo(false);
    setEdicoes((lista) => [{ id: e.id, titulo: e.conteudo.titulo, estado: e.estado, exibicao_em: e.conteudo.exibicao_em }, ...lista.filter((item) => item.id !== e.id)].sort((a, b) => b.id - a.id));
  }
  async function abrir(id: number) {
    setOcupado(true); setErro("");
    try { receberEdicao(await apiFetch<EdicaoEsportiva>(`/esportes/edicoes/${id}`)); } catch (e) { setErro(e instanceof Error ? e.message : "Erro ao abrir edição."); } finally { setOcupado(false); }
  }
  return <section aria-label="Produção esportiva" className="space-y-5">
    <div>
      <h3 className="font-display text-xl font-semibold">Produção esportiva</h3>
      <p className="mt-1 text-sm text-fg/65">Prepare os boletins e as edições de {programa.nome}. O radialista e a programação são os deste programa.</p>
    </div>
    {erro && <p role="alert" className="rounded-xl border border-laranja/40 p-3 text-sm text-laranja">{erro}</p>}
    {carregando && <p role="status" className="text-sm text-fg/65">Carregando a produção esportiva…</p>}
    {!carregando && !perfil && <button type="button" className={botao} onClick={() => window.location.reload()}>Recarregar programa</button>}
    {perfil && <>
      <nav aria-label="Etapas da produção esportiva" className="flex flex-wrap gap-1 rounded-xl bg-bg p-1">
        {([['producao', 'Edições'], ['perfil', 'Perfil editorial'], ['fontes', 'Fontes']] as const).map(([id, titulo]) => (
          <button type="button" key={id} disabled={sujo || ocupado || ocupadoEditor || configuracaoOcupada} aria-current={aba === id ? 'page' : undefined}
            className={`rounded-lg px-3 py-2 text-sm font-semibold disabled:opacity-50 ${aba === id ? 'bg-acento text-on-brand' : 'text-fg/65 hover:text-fg'}`}
            onClick={() => setAba(id)}>{titulo}</button>
        ))}
      </nav>
      {aba === 'perfil' && perfil && <PerfilEditor key={programaId} perfil={perfil} programaId={programaId} onSave={(p) => { if (p.fuso !== perfil.fuso) setExibicao(proximaExibicaoEsportiva(programa, p.fuso)); setPerfil(p); }} onDirty={setConfiguracaoPendente} onBusy={setConfiguracaoOcupada} />}
      {aba === 'fontes' && <FontesEditor fontes={fontes} onDirty={setConfiguracaoPendente} onBusy={setConfiguracaoOcupada} onSave={async () => { setFontes(await apiFetch<FonteEsportiva[]>("/esportes/fontes")); if (edicao) await abrir(edicao.id); }} />}
      {aba === 'producao' && perfil && !carregando && <div className="space-y-6">
        <form className="flex flex-wrap items-end gap-3 rounded-2xl bg-surface p-4" onSubmit={async (e) => {
          e.preventDefault(); setOcupado(true); setErro("");
          try { receberEdicao(await apiFetch<EdicaoEsportiva>(`/esportes/programas/${programaId}/edicoes`, { method: "POST", body: JSON.stringify({ modelo, exibicao_em: isoNoFuso(exibicao, perfil.fuso) }) })); }
          catch (e) { setErro(e instanceof Error ? e.message : "Erro ao criar edição."); } finally { setOcupado(false); }
        }}><div className="min-w-48 flex-1"><Campo label="Modelo de edição"><select className={campo} value={modelo} disabled={sujo || ocupado || ocupadoEditor || configuracaoOcupada} onChange={(e) => setModelo(e.target.value as ConteudoEsportivo['modelo'])}><option value="boletim_2">Boletim de 2 minutos</option><option value="boletim_3">Boletim de 3 minutos</option><option value="programa_30">Programa de 30 minutos</option></select></Campo></div><div className="min-w-48 flex-1"><Campo label={`Exibição prevista (${perfil.fuso})`}><input required type="datetime-local" className={campo} value={exibicao} disabled={sujo || ocupado || ocupadoEditor || configuracaoOcupada} onChange={(e) => setExibicao(e.target.value)} /></Campo></div><button className={primario} disabled={sujo || ocupado || ocupadoEditor || configuracaoOcupada}>{ocupado ? 'Preparando…' : 'Criar edição'}</button><p className="w-full text-xs text-fg/65">A exibição prevista serve à conferência de validade. Para 30 minutos: 28 editoriais + 2 de intervalo. Sem publicidade, envie chamadas ou quadros aprovados.</p></form>
        {!!edicoes.length && <div className="flex flex-wrap items-end gap-3"><div className="min-w-0 flex-1"><Campo label="Retomar uma edição"><select disabled={sujo || ocupado || ocupadoEditor || configuracaoOcupada} className={campo} value={edicao?.id ?? ''} onChange={(e) => { if (e.target.value) abrir(Number(e.target.value)); }}><option value="">Selecione a edição</option>{edicoes.map((e) => <option key={e.id} value={e.id}>#{e.id} · {e.titulo} · {dataNoFuso(e.exibicao_em, perfil.fuso).replace('T', ' ')} · {rotuloEstado[e.estado] ?? e.estado}</option>)}</select></Campo></div>{edicao && <button className={botao} disabled={sujo || ocupado || ocupadoEditor || configuracaoOcupada} onClick={() => abrir(edicao.id)}>Revalidar edição</button>}</div>}
        {edicao ? <EdicaoEditor key={edicao.id} edicao={edicao} fontes={fontes} onSave={receberEdicao} onDirty={setSujo} onBusy={setOcupadoEditor} /> : <div className="rounded-2xl border border-dashed border-border-strong p-8"><h3 className="font-display text-xl font-semibold">Sua próxima edição começa aqui</h3><p className="mt-2 max-w-xl text-sm text-fg/65">Configure o perfil da emissora, aprove as fontes e crie uma edição. Depois registre a ficha factual, prepare as falas e revise o áudio de cada bloco.</p></div>}
      </div>}
    </>}
  </section>;
}
