"use client";
import { useEffect, useState } from "react";
import { apiFetch } from "../lib/api";
import VoiceSelect from "./VoiceSelect";
import { nomeModelo, reais, reaisPreciso } from "../lib/combinacoes";
import { formatarDecimal, formatarTarifa, rotuloFuncionalidade, rotuloUnidade } from "../lib/rotulosConsumo";

export type ModeloTarifado = { id: string; tipo: string; modelo: string; descricao: string; limitacoes: string; moeda: string; cambio: string; acrescimo: string; unidades: Record<string, { preco: string; divisor: string }>; exemplos: { texto?: string; audio_url?: string; custo_brl?: string }[] };

const CARD = "space-y-5 bg-surface rounded-3xl border border-border-strong shadow-theme-xs p-6";
const ROTULO = "block text-sm font-medium text-fg/80 mb-1.5";
const CAMPO = "block w-full rounded-xl border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-acento-claro/50 focus:ring-2 focus:ring-acento-claro/20";
const BOTAO = "rounded-xl bg-brand-500 px-4 py-2 text-sm font-medium text-on-brand hover:bg-brand-600 disabled:opacity-60 disabled:cursor-not-allowed";
const BOTAO_SECUNDARIO = "rounded-xl border border-border-strong px-4 py-2 text-sm font-medium text-fg hover:bg-fg/5 disabled:opacity-60 disabled:cursor-not-allowed";

// Tarifa de referência de cada modelo e amostra paga com o conteúdo do cliente.
export default function TarifasModelos() {
  const [catalogo, setCatalogo] = useState<ModeloTarifado[] | null>(null);
  const [amostraModelo, setAmostraModelo] = useState("");
  const [conteudo, setConteudo] = useState(""); const [vozId, setVozId] = useState<string | null>(null);
  const [estimativa, setEstimativa] = useState<{ limite_brl: number; autorizacao: string } | null>(null);
  const [resultado, setResultado] = useState<{ texto?: string; audio_base64?: string } | null>(null);
  const [gerando, setGerando] = useState(false);
  const [erro, setErro] = useState("");

  useEffect(() => {
    apiFetch<ModeloTarifado[]>("/billing/catalogo-modelos")
      .then(setCatalogo)
      .catch(() => { setCatalogo([]); setErro("Não foi possível carregar as tarifas. Atualize a página para tentar de novo."); });
  }, []);

  async function estimar() {
    setGerando(true); setEstimativa(null); setResultado(null); setErro("");
    const modelo = catalogo?.find(m => m.id === amostraModelo);
    try { setEstimativa(await apiFetch("/billing/amostras/estimar", { method: "POST", body: JSON.stringify({ tipo: modelo?.tipo, modelo: modelo?.modelo, texto: conteudo, voz_id: vozId }) })); }
    catch (e) { setErro(e instanceof Error ? e.message : "Não foi possível calcular a estimativa. Tente novamente."); }
    finally { setGerando(false); }
  }
  async function executar() {
    if (!estimativa) return;
    setGerando(true); setErro("");
    try { setResultado(await apiFetch("/billing/amostras/executar", { method: "POST", body: JSON.stringify({ autorizacao: estimativa.autorizacao }) })); setEstimativa(null); }
    catch (e) { setErro(e instanceof Error ? e.message : "A geração não foi concluída. Consulte uma nova estimativa."); }
    finally { setGerando(false); }
  }

  const modelos = catalogo ?? [];
  const amostraEhVoz = modelos.find(m => m.id === amostraModelo)?.tipo === "tts";

  return <section className={CARD} aria-labelledby="tarifas-titulo">
    <div>
      <h2 id="tarifas-titulo" className="font-display text-lg font-bold text-fg">Tarifas e testes</h2>
      <p className="mt-1 text-sm text-fg/65">Custo de referência de cada modelo; o preço inclui o câmbio e o acréscimo indicados. Exemplos publicados são gratuitos para reproduzir.</p>
    </div>
    {erro && <p role="alert" className="text-sm text-laranja">{erro}</p>}
    {!catalogo && <p role="status" className="text-sm text-fg/65">Carregando tarifas…</p>}
    {catalogo?.length === 0 && !erro && <p className="text-sm text-fg/65">O catálogo será liberado após a confirmação das tarifas contratadas e a avaliação de qualidade.</p>}

    {modelos.length > 0 && <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{modelos.map(m => <article key={m.id} className="rounded-xl border border-border-strong p-4 text-sm">
      <h3 className="font-display text-base font-bold text-fg" translate="no">{nomeModelo(m.modelo)}</h3>
      <p className="text-xs text-fg/65">{rotuloFuncionalidade(m.tipo)}</p>
      <p className="mt-2 text-fg/80">{m.descricao}</p>
      {m.limitacoes && <p className="mt-1 text-xs text-fg/65">{m.limitacoes}</p>}
      <ul className="my-2 space-y-0.5 tabular-nums">{Object.entries(m.unidades).map(([u, t]) =>
        <li key={u}>{formatarTarifa(t.preco, m.moeda)} por {Number(t.divisor).toLocaleString("pt-BR")} {rotuloUnidade(u)}</li>)}</ul>
      <p className="text-xs text-fg/65">Câmbio: {formatarDecimal(m.cambio)} · Acréscimo: {formatarDecimal(m.acrescimo)}%</p>
      {m.exemplos.map((e, i) => <div key={i} className="mt-3 space-y-1">
        {e.texto && <p className="break-words">{e.texto}</p>}
        {e.audio_url && <audio controls preload="none" src={e.audio_url} className="h-9 w-full" aria-label={`Exemplo de ${nomeModelo(m.modelo)}`} />}
        {e.custo_brl && <small className="block text-fg/65">Custo desta amostra: {reais(Number(e.custo_brl))}. Reprodução gratuita.</small>}
      </div>)}
    </article>)}</div>}

    {modelos.length > 0 && <form className="space-y-3 border-t border-border-strong pt-5" onSubmit={e => { e.preventDefault(); void estimar(); }}>
      <h3 className="font-display text-base font-bold text-fg">Testar com seu conteúdo</h3>
      <p className="text-sm text-fg/65">Consulte a estimativa e confirme o processamento pago antes de gerar.</p>
      <label className={`${ROTULO} max-w-sm`}>Modelo da amostra
        <select required name="modelo_amostra" className={`${CAMPO} mt-1.5`} value={amostraModelo} onChange={e => { setAmostraModelo(e.target.value); setEstimativa(null); }}>
          <option value="">Selecione</option>
          {modelos.filter(m => ["llm", "tts"].includes(m.tipo)).map(m => <option key={m.id} value={m.id}>{rotuloFuncionalidade(m.tipo)} · {nomeModelo(m.modelo)}</option>)}
        </select>
      </label>
      <label className={ROTULO}>{amostraEhVoz ? "Texto a ser locutado" : "Pedido"}
        <textarea required name="conteudo_amostra" autoComplete="off" maxLength={2000} rows={3} placeholder={amostraEhVoz ? "Ex.: Bom dia, você está ouvindo a Rádio Aurora…" : "Ex.: Anuncie a próxima música pedida pela Ana…"} className={`${CAMPO} mt-1.5`} value={conteudo} onChange={e => { setConteudo(e.target.value); setEstimativa(null); }} />
      </label>
      {amostraEhVoz && <div><span className={ROTULO}>Voz</span><VoiceSelect value={vozId} onChange={v => { setVozId(v); setEstimativa(null); }} /></div>}
      <button disabled={gerando || (amostraEhVoz && !vozId)} className={BOTAO_SECUNDARIO}>{gerando && !estimativa ? "Consultando…" : "Consultar estimativa"}</button>
    </form>}
    {estimativa && <div className="rounded-xl border border-acento-claro/30 bg-acento/5 p-4 text-sm">
      <p>Limite desta geração: <strong className="tabular-nums">{reaisPreciso(estimativa.limite_brl)}</strong>. Você paga as unidades realmente processadas até esse valor.</p>
      <button type="button" disabled={gerando} className={`${BOTAO} mt-3`} onClick={() => void executar()}>{gerando ? "Gerando…" : "Confirmar geração paga"}</button>
    </div>}
    {resultado && <div className="rounded-xl border border-border-strong p-4 text-sm">
      {resultado.texto && <p className="whitespace-pre-wrap break-words">{resultado.texto}</p>}
      {resultado.audio_base64 && <audio controls src={`data:audio/mpeg;base64,${resultado.audio_base64}`} className="w-full" aria-label="Resultado da amostra" />}
    </div>}
  </section>;
}
