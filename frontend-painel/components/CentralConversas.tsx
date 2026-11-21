"use client";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { apiFetch, apiFetchDownload } from "../lib/api";
import { useEventosOuvintes } from "../hooks/useEventosOuvintes";
import { formatarTelefone } from "../lib/telefone";
import WhatsAppConexao from "./WhatsAppConexao";
import OperacaoWhatsapp from "./OperacaoWhatsapp";

type Conversa = { id: number; telefone: string; nome: string; humano: boolean; nao_lidas: number; ultima_mensagem: string; pode_responder?: boolean; responsavel_nome?: string | null };
type Mensagem = { id: string; log_id: number | null; origem: string; texto: string; status: string; em: string; usuario_id?: number; envio_id?: number };
type Historico = { mensagens: Mensagem[]; antes: number | null; ultimo_log_id: number; conversa: Conversa };
type Contexto = {
  programa_id: number | null;
  publico: { assunto: string | null; pergunta: string | null; discussao_id: number | null } | null;
  pedidos: { id: number; tipo: string; estado: string }[];
  notas: { id: number; texto: string }[];
  contribuicoes: { id: number; estado: string }[];
};
const campo = "w-full rounded-xl border border-border-strong bg-bg px-3 py-2 text-sm text-fg";
const botao = "rounded-xl border border-border-strong px-3 py-2 text-sm text-fg hover:bg-fg/5 disabled:opacity-40";
const rotulos: Record<string, string> = {
  pendente: "Aguardando envio", pendente_envio: "Aguardando envio", processando: "Processando mensagem",
  aceito_pelo_provedor: "Envio aceito pelo WhatsApp", enviada: "Enviada", respondido_whatsapp: "Respondida",
  incerto: "Envio incerto: confira no WhatsApp", envio_incerto: "Envio incerto: confira no WhatsApp",
  falha_conexao: "Falha de conexão", falha_envio: "Falha de envio", falha_processamento: "Falha ao processar",
  pausado: "Envio automático pausado", aguardando_humano: "Aguardando equipe", guardado: "Registrada",
  em_fila: "Na fila", aguardando_revisao: "Aguardando revisão", selecionado: "Selecionado no player",
  executado: "Reprodução confirmada", nao_atendido: "Não atendido", cancelado: "Cancelado", expirado: "Expirado",
};

function Revisao({ id, atualizar }: { id: number; atualizar: () => void }) {
  const [titulo, setTitulo] = useState(""); const [texto, setTexto] = useState("");
  const [autorizado, setAutorizado] = useState(false); const [erro, setErro] = useState(""); const [ocupado, setOcupado] = useState(false);
  async function agir(acao: string) {
    setOcupado(true); setErro("");
    try { await apiFetch(`/ouvintes/contribuicoes/${id}`, { method: "PATCH", body: JSON.stringify({ acao, titulo, texto_autorizado: texto, autorizacao_confirmada: autorizado }) }); atualizar(); }
    catch (e) { setErro(e instanceof Error ? e.message : "Falha ao revisar"); } finally { setOcupado(false); }
  }
  return <details className="border-t border-border py-3"><summary className="cursor-pointer text-sm">Revisar contribuição #{id}</summary><div className="mt-3 space-y-2">
    <label className="block text-xs">Título da pauta<input className={campo} value={titulo} maxLength={150} onChange={e => setTitulo(e.target.value)} /></label>
    <label className="block text-xs">Somente conteúdo autorizado para o ar<textarea className={campo} value={texto} maxLength={1500} onChange={e => setTexto(e.target.value)} /></label>
    <label className="flex gap-2 text-xs"><input type="checkbox" checked={autorizado} onChange={e => setAutorizado(e.target.checked)} />Conferi a autorização para divulgar este conteúdo.</label>
    <div className="flex flex-wrap gap-2"><button className={botao} disabled={ocupado || !autorizado || !titulo.trim() || !texto.trim()} onClick={() => agir("aprovar")}>Aprovar pauta</button><button className={botao} disabled={ocupado} onClick={() => agir("recusar")}>Recusar</button></div>
    {erro && <p role="alert" className="text-sm text-laranja">{erro}</p>}</div></details>;
}

function Reenvio({ id, agir }: { id: number; agir: (path: string, method: string, body: object) => Promise<boolean> }) {
  const [conferido, setConferido] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  return <details className="mt-2 text-xs"><summary className="cursor-pointer underline">Conferir envio</summary>
    <label className="my-2 flex gap-2"><input type="checkbox" checked={conferido} onChange={e => setConferido(e.target.checked)} />Conferi no WhatsApp que esta mensagem não foi entregue.</label>
    <button className={botao} disabled={!conferido || ocupado} onClick={async () => { setOcupado(true); await agir(`/ouvintes/envios/${id}/reenviar`, "POST", { confirmei_nao_entregue: true }); setOcupado(false); }}>Tentar novamente</button>
  </details>;
}

export default function CentralConversas() {
  const [conversas, setConversas] = useState<Conversa[]>([]); const [selecionada, setSelecionada] = useState<Conversa | null>(null);
  const [mensagens, setMensagens] = useState<Mensagem[]>([]); const [contexto, setContexto] = useState<Contexto | null>(null);
  const [busca, setBusca] = useState(""); const [modo, setModo] = useState("todas"); const [pagina, setPagina] = useState(1); const [paginas, setPaginas] = useState(1);
  const [antes, setAntes] = useState<number | null>(null); const [texto, setTexto] = useState(""); const [nota, setNota] = useState(""); const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(false); const [ocupado, setOcupado] = useState(false);
  const idRef = useRef<number | null>(null); const versao = useRef(0); const listaVersao = useRef(0); const antigas = useRef(false);
  const envio = useRef<{ texto: string; chave: string; conversa: number } | null>(null);
  const carregarLista = useCallback(async () => {
    const pedido = ++listaVersao.current;
    try {
      const dados = await apiFetch<{ conversas: Conversa[]; total_paginas: number }>(`/ouvintes/central?pagina=${pagina}&modo=${modo}&busca=${encodeURIComponent(busca)}`);
      if (pedido === listaVersao.current) { setConversas(dados.conversas); setPaginas(dados.total_paginas); }
    } catch (e) { if (pedido === listaVersao.current) setErro(e instanceof Error ? e.message : "Falha ao carregar conversas"); }
  }, [pagina, modo, busca]);
  const carregar = useCallback(async (id: number, cursor?: number) => {
    const pedido = ++versao.current; if (!cursor) setCarregando(true);
    try {
      const [dados, ctx] = await Promise.all([apiFetch<Historico>(`/ouvintes/conversas/${id}/mensagens${cursor ? `?antes=${cursor}` : ""}`), apiFetch<Contexto>(`/ouvintes/conversas/${id}/contexto`)]);
      if (idRef.current !== id || pedido !== versao.current) return;
      setSelecionada(dados.conversa); setContexto(ctx);
      setMensagens(atuais => {
        const primeiro = Math.min(...dados.mensagens.flatMap(m => m.log_id ? [m.log_id] : []));
        const preservadas = cursor ? atuais : atuais.filter(m => m.log_id && m.log_id < primeiro);
        return [...new Map([...preservadas, ...dados.mensagens].map(m => [m.id, m])).values()].sort((a, b) => new Date(a.em).getTime() - new Date(b.em).getTime() || (a.log_id ?? Infinity) - (b.log_id ?? Infinity) || a.id.localeCompare(b.id));
      });
      if (cursor || !antigas.current) setAntes(dados.antes); if (cursor) antigas.current = true;
      if (!cursor && dados.ultimo_log_id) await apiFetch(`/ouvintes/conversas/${id}/leitura`, { method: "POST", body: JSON.stringify({ ultimo_log_id: dados.ultimo_log_id }) });
    } catch (e) { if (idRef.current === id && pedido === versao.current) setErro(e instanceof Error ? e.message : "Falha ao carregar mensagens"); }
    finally { if (pedido === versao.current) setCarregando(false); }
  }, []);
  const atualizar = useCallback(() => { void carregarLista(); if (idRef.current) void carregar(idRef.current); }, [carregarLista, carregar]);
  const conexao = useEventosOuvintes(atualizar);
  useEffect(() => { void carregarLista(); }, [carregarLista]);
  useEffect(() => () => { idRef.current = null; versao.current++; listaVersao.current++; }, []);
  function selecionar(c: Conversa) {
    idRef.current = c.id; versao.current++; antigas.current = false; setSelecionada(c); setMensagens([]); setContexto(null); setAntes(null); setTexto(""); setNota(""); setErro(""); void carregar(c.id);
  }
  async function agir(path: string, method: string, body: object) {
    setOcupado(true); setErro("");
    try { await apiFetch(path, { method, body: JSON.stringify(body) }); atualizar(); return true; }
    catch (e) { setErro(e instanceof Error ? e.message : "Não foi possível concluir a ação"); return false; } finally { setOcupado(false); }
  }
  async function enviarMensagem(e: FormEvent) {
    e.preventDefault(); if (!selecionada || !texto.trim()) return;
    if (!envio.current || envio.current.texto !== texto.trim() || envio.current.conversa !== selecionada.id) envio.current = { texto: texto.trim(), chave: crypto.randomUUID(), conversa: selecionada.id };
    const id = selecionada.id;
    if (await agir(`/ouvintes/conversas/${id}/mensagens`, "POST", envio.current)) { if (idRef.current === id) setTexto(""); envio.current = null; }
  }
  return <div className="space-y-4"><WhatsAppConexao compacta /><OperacaoWhatsapp />
    <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-fg/65"><p role="status">{conexao === "conectado" ? "Atualizações em tempo real" : conexao === "conectando" ? "Conectando atualizações…" : "Reconectando; atualização periódica ativa"}</p><button className="underline" onClick={() => apiFetchDownload("/metrics/export?dias=30", "conversas.csv").catch(e => setErro(e.message))}>Exportar últimos 30 dias</button></div>
    {erro && <p role="alert" className="rounded-xl border border-laranja/40 p-3 text-sm text-laranja">{erro}</p>}
    <div className="grid min-h-[70vh] grid-cols-1 gap-4 lg:grid-cols-[17rem_minmax(0,1fr)] xl:grid-cols-[17rem_minmax(0,1fr)_18rem]">
      <section aria-label="Lista de conversas" className={`${selecionada ? "hidden lg:flex" : "flex"} flex-col rounded-2xl border border-border-strong bg-surface overflow-hidden`}>
        <div className="space-y-2 p-3 border-b border-border"><label className="sr-only" htmlFor="buscar-conversa">Buscar conversa</label><input id="buscar-conversa" className={campo} placeholder="Nome ou telefone" value={busca} onChange={e => { setBusca(e.target.value); setPagina(1); }} />
          <label className="sr-only" htmlFor="filtro-conversa">Filtrar conversas</label><select id="filtro-conversa" className={campo} value={modo} onChange={e => { setModo(e.target.value); setPagina(1); }}><option value="todas">Todas as conversas</option><option value="nao_lidas">Não lidas</option><option value="humano">Com a equipe</option><option value="agente">Com o agente</option></select></div>
        <div className="flex-1 overflow-y-auto max-h-[65vh]">{conversas.map(c => <button key={c.id} onClick={() => selecionar(c)} aria-pressed={selecionada?.id === c.id} className={`block w-full border-b border-border p-4 text-left hover:bg-fg/5 ${selecionada?.id === c.id ? "bg-ciano/10" : ""}`}>
          <span className="flex justify-between gap-2 text-sm font-medium text-fg"><span className="truncate">{c.nome || formatarTelefone(c.telefone)}</span>{c.nao_lidas > 0 && <span aria-label={`${c.nao_lidas} não lidas`} className="rounded-full bg-ciano/20 px-2">{c.nao_lidas}</span>}</span><span className="block text-xs text-fg/65">{c.humano ? "Com a equipe" : "Com o agente"}</span><span className="mt-1 block truncate text-xs text-fg/65">{c.ultima_mensagem}</span></button>)}{!conversas.length && <p className="p-4 text-sm text-fg/65">Nenhuma conversa encontrada.</p>}</div>
        <nav aria-label="Páginas das conversas" className="flex justify-between p-3 text-xs"><button disabled={pagina === 1} onClick={() => setPagina(p => p - 1)}>Anterior</button><span>{pagina}/{paginas}</span><button disabled={pagina >= paginas} onClick={() => setPagina(p => p + 1)}>Próxima</button></nav>
      </section>
      <section aria-label="Mensagens da conversa" className={`${selecionada ? "flex" : "hidden lg:flex"} min-w-0 flex-col rounded-2xl border border-border-strong bg-surface overflow-hidden`}>
        {!selecionada ? <p className="m-auto p-6 text-sm text-fg/65">Selecione uma conversa para atender o ouvinte.</p> : <>
          <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border p-4"><div><button className="mr-3 text-xs underline lg:hidden" onClick={() => { idRef.current = null; setSelecionada(null); }}>Voltar</button><strong className="text-sm">{selecionada.nome || formatarTelefone(selecionada.telefone)}</strong><p className="text-xs text-fg/65">{formatarTelefone(selecionada.telefone)} · {selecionada.humano ? selecionada.responsavel_nome || "Equipe atendendo" : "Agente atendendo"}</p></div><button className={botao} disabled={ocupado} onClick={() => agir(`/ouvintes/conversas/${selecionada.id}`, "PATCH", { humano: !selecionada.humano })}>{selecionada.humano ? "Devolver ao agente" : "Assumir conversa"}</button></header>
          <div className="flex max-h-[62vh] min-h-80 flex-1 flex-col gap-3 overflow-y-auto bg-bg/50 p-4" aria-busy={carregando}>
            {antes && <button disabled={carregando} className="self-center text-xs underline" onClick={() => carregar(selecionada.id, antes)}>Carregar mensagens anteriores</button>}
            {mensagens.map(m => <article key={m.id} className={`max-w-[88%] rounded-2xl px-4 py-3 ${m.origem === "radio" ? "self-end bg-ciano/10" : "self-start border border-border bg-surface"}`}><p className="whitespace-pre-wrap break-words text-sm text-fg">{m.texto}</p><p className="mt-2 text-[11px] text-fg/65">{m.origem === "radio" ? m.usuario_id ? "Equipe" : "Rádio" : "Ouvinte"} · {new Date(m.em).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}</p><p className="text-[11px] text-fg/65">{rotulos[m.status] || m.status}</p>
              {m.envio_id && ["incerto", "falha_conexao", "pausado"].includes(m.status) && <Reenvio id={m.envio_id} agir={agir} />}
              {m.origem === "ouvinte" && m.log_id && contexto?.programa_id && <button className="mt-2 text-xs text-acento-claro underline" disabled={ocupado} onClick={() => agir(`/ouvintes/conversas/${selecionada.id}/contribuicoes`, "POST", { log_id: m.log_id, programa_id: contexto.programa_id, discussao_id: contexto.publico?.discussao_id })}>Sugerir para pauta</button>}</article>)}
            {!mensagens.length && <p className="text-sm text-fg/65">{carregando ? "Carregando mensagens…" : "Sem mensagens neste histórico."}</p>}
          </div>
          <form className="space-y-2 border-t border-border p-3" onSubmit={enviarMensagem}><label htmlFor="resposta-conversa" className="text-xs text-fg/65">{selecionada.humano ? "Resposta da equipe" : "Assuma a conversa para responder pessoalmente"}</label><textarea id="resposta-conversa" className={campo} value={texto} maxLength={4000} rows={3} disabled={!selecionada.humano || selecionada.pode_responder === false || ocupado} onChange={e => setTexto(e.target.value)} /><button className={botao} disabled={!selecionada.humano || selecionada.pode_responder === false || ocupado || !texto.trim()}>Enviar mensagem</button></form>
        </>}
      </section>
      {selecionada && contexto && <aside aria-label="Contexto da conversa" className="space-y-4 rounded-2xl border border-border-strong bg-surface p-4 lg:col-span-2 xl:col-span-1">
        <div><h2 className="font-display text-base font-semibold">Contexto do programa</h2><p className="mt-2 text-sm text-fg/65">{contexto.publico?.pergunta || contexto.publico?.assunto || "Sem assunto recente confirmado pelo player."}</p></div>
        <div><h3 className="text-sm font-semibold">Pedidos deste ouvinte</h3>{contexto.pedidos.map(p => <p key={p.id} className="mt-2 text-xs text-fg/65">#{p.id} {p.tipo} · {rotulos[p.estado] || p.estado}</p>)}<Link className="mt-2 block text-xs text-acento-claro underline" href="/live">Revisar participações no Ao Vivo</Link></div>
        <div><h3 className="text-sm font-semibold">Contribuições para pauta</h3>{contexto.contribuicoes.map(c => c.estado === "aguardando_revisao" ? <Revisao key={c.id} id={c.id} atualizar={atualizar} /> : <p className="mt-2 text-xs text-fg/65" key={c.id}>#{c.id} · {c.estado}</p>)}</div>
        <div><h3 className="text-sm font-semibold">Notas internas</h3><p className="mb-2 text-xs text-fg/65">Visíveis apenas para a equipe.</p>{contexto.notas.map(n => <p className="my-2 whitespace-pre-wrap text-xs text-fg/80" key={n.id}>{n.texto}</p>)}<label className="sr-only" htmlFor="nota-interna">Nota interna</label><textarea id="nota-interna" className={campo} rows={2} maxLength={2000} value={nota} onChange={e => setNota(e.target.value)} /><button className={`${botao} mt-2`} disabled={ocupado || !nota.trim()} onClick={async () => { if (await agir(`/ouvintes/conversas/${selecionada.id}/notas`, "POST", { texto: nota })) setNota(""); }}>Salvar nota</button></div>
      </aside>}
    </div></div>;
}
