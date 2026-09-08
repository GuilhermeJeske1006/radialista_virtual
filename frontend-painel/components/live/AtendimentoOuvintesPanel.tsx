"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../../lib/api";

type Pedido = { id: number; nome: string; tipo: string; estado: string; programa_id: number | null; transmissao: string | null; mensagem_usuario: string; texto_autorizado: string; musica_query: string | null; motivo: string; eventos?: {acao: string; em: string; usuario_id: number | null; programa_id: number | null}[] };
type Conversa = { id: number; nome: string; telefone: string; humano: boolean; historico: {role: string; content: string}[] };
type Envio = {id: number; nome: string; telefone: string; texto: string; status: string};
type Programa = {id: number; nome: string};
const ESTADOS: Record<string, string> = {historico_legado: "Histórico anterior ao novo atendimento",aguardando_revisao: "Aguardando revisão", em_fila: "Na fila", selecionado: "Selecionado no player", executado: "Executado", nao_atendido: "Não atendido", expirado: "Expirado", cancelado: "Cancelado"};
const campo = "w-full rounded border border-border bg-surface p-2 text-sm text-fg";
const botao = "rounded border border-border px-3 py-2 text-xs text-fg disabled:opacity-40";

function RevisarPedido({pedido, programas, atualizar}: {pedido: Pedido; programas: Programa[]; atualizar: () => Promise<void>}) {
  const [texto, setTexto] = useState(pedido.texto_autorizado);
  const [nome, setNome] = useState(pedido.nome);
  const [autorizado, setAutorizado] = useState(false);
  const [destino, setDestino] = useState("");
  const [motivo, setMotivo] = useState("");
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);
  async function agir(acao: string) {
    setOcupado(true); setErro("");
    try {
      await apiFetch(`/ouvintes/pedidos/${pedido.id}`, {method: "PATCH", body: JSON.stringify({acao, texto_autorizado: texto, nome, autorizacao_confirmada: autorizado, motivo, programa_id: destino ? Number(destino) : null})});
      await atualizar();
    } catch (e) { setErro(e instanceof Error ? e.message : "Não foi possível atualizar o pedido."); }
    finally { setOcupado(false); }
  }
  return <details className="rounded border border-border p-3">
    <summary className="cursor-pointer text-sm">{pedido.nome || "Ouvinte"} · {pedido.tipo} · {ESTADOS[pedido.estado] || pedido.estado}</summary>
    <p className="my-2 text-xs text-fg/65">{programas.find(p => p.id === pedido.programa_id)?.nome || "Sem programa vinculado"} · {pedido.transmissao || "Pedido anterior ao novo atendimento"}</p>
    <p className="whitespace-pre-wrap text-sm">Mensagem privada: {pedido.mensagem_usuario}</p>
    {pedido.musica_query && <p className="text-sm">Música solicitada: {pedido.musica_query}</p>}
    {pedido.motivo && <p className="text-xs text-fg/65">{pedido.motivo}</p>}
    {!!pedido.eventos?.length && <details className="mt-2"><summary className="text-xs cursor-pointer">Histórico do pedido</summary>{pedido.eventos.map((e, i) => <p key={i} className="text-xs text-fg/65">{new Date(e.em).toLocaleString("pt-BR")} · {e.acao} · {e.usuario_id ? `Equipe #${e.usuario_id}` : "Sistema / ouvinte"}</p>)}</details>}
    {!["executado", "historico_legado"].includes(pedido.estado) && <div className="mt-3 space-y-3">
      <label className="block text-xs">Nome para o ar<input className={campo} value={nome} maxLength={100} onChange={e => setNome(e.target.value)} /></label>
      <label className="block text-xs">Somente conteúdo autorizado para o ar<textarea className={campo} value={texto} maxLength={1500} onChange={e => setTexto(e.target.value)} /></label>
      <label className="flex gap-2 text-xs"><input type="checkbox" checked={autorizado} onChange={e => setAutorizado(e.target.checked)} />Conferi com o ouvinte a autorização para divulgar este conteúdo e nome.</label>
      <label className="block text-xs">Motivo / observação<input className={campo} value={motivo} maxLength={300} onChange={e => setMotivo(e.target.value)} /></label>
      <div className="flex flex-wrap gap-2">
        <button className={botao} disabled={ocupado || !autorizado || !texto.trim() || pedido.estado === "selecionado"} onClick={() => agir("aprovar")}>Aprovar para o ar</button>
        <button className={botao} disabled={ocupado || pedido.estado === "selecionado"} onClick={() => agir("recusar")}>Não atender</button>
        <button className={botao} disabled={ocupado || pedido.estado === "selecionado"} onClick={() => agir("cancelar")}>Cancelar pedido</button>
      </div>
      {pedido.estado === "selecionado" && <div className="space-y-2"><p className="text-xs">Interrompa o bloco no player e confira se a participação já tocou antes de solicitar nova revisão.</p><button disabled={ocupado} className={botao} onClick={() => agir("reenfileirar")}>Interrompi o bloco; revisar novamente</button></div>}
      <label className="block text-xs">Transferir para programa no horário de exibição<select className={campo} value={destino} onChange={e => setDestino(e.target.value)}><option value="">Escolha o programa</option>{programas.map(p => <option value={p.id} key={p.id}>{p.nome}</option>)}</select></label>
      <button className={botao} disabled={ocupado || !destino || pedido.estado === "selecionado"} onClick={() => agir("transferir")}>Transferir para revisão</button>
    </div>}
    {erro && <p role="alert" className="mt-2 text-sm text-rust-text">{erro}</p>}
  </details>;
}

export default function AtendimentoOuvintesPanel() {
  const [ativo, setAtivo] = useState(false);
  const [pedidos, setPedidos] = useState<Pedido[]>([]);
  const [conversas, setConversas] = useState<Conversa[]>([]);
  const [envios, setEnvios] = useState<Envio[]>([]);
  const [conferidos, setConferidos] = useState<Record<number, boolean>>({});
  const [programas, setProgramas] = useState<Programa[]>([]);
  const [contagens, setContagens] = useState<Record<string, number>>({});
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const carregar = useCallback(async () => {
    const [config, fila, chats, grade, indicadores, pendentes] = await Promise.all([
      apiFetch<{ativo: boolean}>("/ouvintes/config"), apiFetch<Pedido[]>("/ouvintes/pedidos"),
      apiFetch<Conversa[]>("/ouvintes/conversas"), apiFetch<Programa[]>("/ouvintes/programas"),
      apiFetch<{pedidos_por_estado: Record<string, number>}>("/ouvintes/indicadores"),
      apiFetch<Envio[]>("/ouvintes/envios-pendentes"),
    ]);
    setEnvios(pendentes); setAtivo(config.ativo); setPedidos(fila); setConversas(chats); setProgramas(grade); setContagens(indicadores.pedidos_por_estado);
  }, []);
  useEffect(() => {
    let montado = true;
    const atualizar = () => { if (montado) carregar().catch(e => { if (montado) setErro(e instanceof Error ? e.message : "Falha ao carregar atendimento."); }); };
    atualizar(); const timer = setInterval(atualizar, 15000);
    return () => { montado = false; clearInterval(timer); };
  }, [carregar]);
  async function alterar(url: string, method: string, dados: object) {
    setOcupado(true); setErro("");
    try { await apiFetch(url, {method, body: JSON.stringify(dados)}); await carregar(); }
    catch (e) { setErro(e instanceof Error ? e.message : "Não foi possível atualizar."); }
    finally { setOcupado(false); }
  }
  return <section className="rounded-2xl border border-border-strong bg-surface p-6 space-y-4">
    <h2 className="font-display font-bold">Atendimento aos ouvintes</h2>
    <p className="text-xs text-fg/65">O novo atendimento mantém a conversa e exige revisão antes de levar pedidos ao ar. A configuração de resposta automática de cada radialista continua sendo respeitada.</p>
    <button className={botao} disabled={ocupado} onClick={() => alterar("/ouvintes/config", "PUT", {ativo: !ativo})}>{ativo ? "Desativar novo atendimento" : "Ativar novo atendimento nesta rádio"}</button>
    {erro && <p role="alert" className="text-sm text-rust-text">{erro}</p>}
    <p className="text-xs text-fg/65">Últimos 30 dias: {Object.entries(contagens).map(([estado, n]) => `${ESTADOS[estado] || estado}: ${n}`).join(" · ") || "Sem pedidos"}</p>
    {envios.length > 0 && <details><summary className="text-sm cursor-pointer">Respostas sem confirmação de envio ({envios.length})</summary>{envios.map(e => <div key={e.id} className="space-y-2 border border-border p-3 rounded mt-2">
      <p className="text-sm">{e.nome || e.telefone}: {e.texto}</p>
      <label className="flex gap-2 text-xs"><input type="checkbox" checked={!!conferidos[e.id]} onChange={ev => setConferidos({...conferidos, [e.id]: ev.target.checked})} />Conferi no WhatsApp que esta resposta não foi entregue.</label>
      <button className={botao} disabled={ocupado || !conferidos[e.id]} onClick={() => alterar(`/ouvintes/envios-pendentes/${e.id}/reenviar`, "POST", {confirmei_nao_entregue: true})}>Tentar enviar novamente</button>
    </div>)}</details>}
    <details><summary className="cursor-pointer text-sm font-medium">Conversas recentes ({conversas.length})</summary>
      <div className="mt-3 space-y-3 max-h-96 overflow-y-auto">{conversas.map(c => <details key={c.id} className="border border-border rounded p-3">
        <summary className="text-sm cursor-pointer">{c.nome || c.telefone} · {c.humano ? "Com a equipe" : "Com o agente"}</summary>
        <div className="space-y-2 my-3">{c.historico.map((m, i) => <p className="text-xs whitespace-pre-wrap" key={i}><strong>{m.role === "user" ? "Ouvinte" : "Rádio"}:</strong> {m.content}</p>)}</div>
        <button className={botao} disabled={ocupado} onClick={() => alterar(`/ouvintes/conversas/${c.id}`, "PATCH", {humano: !c.humano})}>{c.humano ? "Devolver ao agente" : "Assumir e pausar agente"}</button>
        {c.humano && <p className="text-xs mt-2">Continue a conversa pelo WhatsApp conectado da rádio.</p>}
      </details>)}</div>
    </details>
    <details open><summary className="cursor-pointer text-sm font-medium">Revisão de participações ({pedidos.length})</summary><div className="mt-3 space-y-2 max-h-[36rem] overflow-y-auto">{pedidos.map(p => <RevisarPedido key={`${p.id}:${p.estado}:${p.transmissao}`} pedido={p} programas={programas} atualizar={carregar} />)}</div></details>
  </section>;
}
