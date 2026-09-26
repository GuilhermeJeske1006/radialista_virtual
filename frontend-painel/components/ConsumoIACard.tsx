"use client";
import { useEffect, useState } from "react";
import { apiFetch } from "../lib/api";
import { nomeModelo, reais, reaisPreciso } from "../lib/combinacoes";
import { formatarDecimal, rotuloEstadoFatura, rotuloEstadoUso, rotuloFuncionalidade, resumirUnidades } from "../lib/rotulosConsumo";
import Paginacao, { paginar } from "./Paginacao";

type Consumo = { ciclo_inicio?: string; ciclo_fim?: string; consumo_brl: number; reservado_brl: number; comprometido_brl: number; orcamento_brl: number; previsao_brl: number; regra_cambio: string };
type Uso = { id: string; funcionalidade: string; modelo: string; unidades: Record<string, string>; preco_brl: number; estado: string; iniciado_em: string; tarifa: { versao: string; cambio: string; acrescimo: string } };
type Fatura = { id: string; inicio: string; fim: string; estado: string; total_brl: number; url: string | null };

const CARD = "space-y-6 bg-surface rounded-3xl border border-border-strong shadow-theme-xs p-6";
const INPUT = "block w-full rounded-xl border border-border-strong bg-bg px-3 py-2 text-sm text-fg tabular-nums focus:outline-none focus:border-acento-claro/50 focus:ring-2 focus:ring-acento-claro/20";
const BOTAO = "rounded-xl bg-brand-500 px-4 py-2 text-sm font-medium text-on-brand hover:bg-brand-600 disabled:opacity-60 disabled:cursor-not-allowed";
const BOTAO_SECUNDARIO = "rounded-xl border border-border-strong px-3 py-1.5 text-xs font-medium text-fg hover:bg-fg/5";
const LINK_FATURA = "font-medium text-acento-claro hover:underline";
const USOS_POR_PAGINA = 10;
const FATURAS_POR_PAGINA = 6;
const data = (iso: string) => new Date(iso).toLocaleDateString("pt-BR");
const dataHora = (iso: string) => new Date(iso).toLocaleString("pt-BR");
const tarifa = (t: Uso["tarifa"]) => `${t.versao} · câmbio ${formatarDecimal(t.cambio)} · +${formatarDecimal(t.acrescimo)}%`;

export default function ConsumoIACard({ plano }: { plano?: string }) {
  const [consumo, setConsumo] = useState<Consumo | null>(null);
  const [usos, setUsos] = useState<Uso[]>([]);
  const [paginaUsos, setPaginaUsos] = useState(1);
  const [temMaisUsos, setTemMaisUsos] = useState(false);
  const [carregandoUsos, setCarregandoUsos] = useState(true);
  const [erroUsos, setErroUsos] = useState(false);
  const [faturas, setFaturas] = useState<Fatura[]>([]);
  const [paginaFaturas, setPaginaFaturas] = useState(1);
  const [limite, setLimite] = useState("");
  const [erro, setErro] = useState("");
  const [salvando, setSalvando] = useState(false);
  const [revisao, setRevisao] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    const options = { signal: controller.signal };
    Promise.all([apiFetch<Consumo>("/billing/consumo-ia", options), apiFetch<Fatura[]>("/billing/faturas", options)])
      .then(([c, f]) => { setConsumo(c); setLimite(String(c.orcamento_brl)); setFaturas(f); setErro(""); })
      .catch(() => { if (!controller.signal.aborted) setErro("Não foi possível consultar o consumo. Tente atualizar."); });
    return () => controller.abort();
  }, [plano, revisao]);
  // Extrato paginado no servidor: pede um item a mais para saber se existe a próxima página.
  useEffect(() => {
    const controller = new AbortController();
    setCarregandoUsos(true);
    apiFetch<Uso[]>(`/billing/extrato?offset=${(paginaUsos - 1) * USOS_POR_PAGINA}&limite=${USOS_POR_PAGINA + 1}`, { signal: controller.signal })
      .then(u => { setUsos(u.slice(0, USOS_POR_PAGINA)); setTemMaisUsos(u.length > USOS_POR_PAGINA); setErroUsos(false); })
      .catch(() => { if (!controller.signal.aborted) setErroUsos(true); })
      .finally(() => { if (!controller.signal.aborted) setCarregandoUsos(false); });
    return () => controller.abort();
  }, [plano, revisao, paginaUsos]);
  function atualizar() { setPaginaUsos(1); setPaginaFaturas(1); setRevisao(n => n + 1); }
  async function salvar() {
    setSalvando(true); setErro("");
    try { await apiFetch("/billing/limite-financeiro", { method: "PUT", body: JSON.stringify({ limite_brl: limite }) }); setRevisao(n => n + 1); }
    catch (e) { setErro(e instanceof Error ? e.message : "Não foi possível salvar o limite."); }
    finally { setSalvando(false); }
  }
  const paginaDeFaturas = paginar(faturas, paginaFaturas, FATURAS_POR_PAGINA);
  return <section className={CARD} aria-labelledby="consumo-titulo">
    <div className="flex items-center justify-between gap-4">
      <h2 id="consumo-titulo" className="font-display text-lg font-bold text-fg">Consumo e faturas</h2>
      <button type="button" onClick={atualizar} className={BOTAO_SECUNDARIO}>Atualizar</button>
    </div>
    {erro && <p role="alert" className="text-sm text-laranja">{erro}</p>}
    {!consumo && !erro && <p role="status" className="text-sm text-fg/65">Consultando consumo…</p>}
    {consumo && <>
      {consumo.ciclo_inicio && consumo.ciclo_fim && <p className="text-sm text-fg/65">Ciclo: {data(consumo.ciclo_inicio)} — {data(consumo.ciclo_fim)}</p>}
      <dl className="grid gap-4 sm:grid-cols-3">
        {([["Uso a faturar", consumo.consumo_brl], ["Previsão com mensalidade", consumo.previsao_brl], ["Operações em andamento", consumo.reservado_brl]] as const).map(([rotulo, valor]) =>
          <div key={rotulo} className="rounded-xl border border-border-strong bg-bg p-4">
            <dt className="text-xs font-medium uppercase tracking-wide text-fg/65">{rotulo}</dt>
            <dd className="mt-1 text-2xl font-bold text-fg tabular-nums">{reais(valor)}</dd>
          </div>)}
      </dl>
      <p className="text-sm text-fg/80">Total comprometido: <span className="tabular-nums">{reais(consumo.comprometido_brl)}</span>. Soma o uso deste ciclo, operações em andamento e uso ainda não pago de ciclos anteriores. É esse total que o limite financeiro controla.</p>
      <form id="limite" onSubmit={e => { e.preventDefault(); void salvar(); }} className="scroll-mt-24 flex flex-wrap items-end gap-3">
        <label className="block text-sm font-medium text-fg/80">Limite financeiro mensal (R$)
          <input type="number" name="limite_brl" inputMode="decimal" autoComplete="off" min="0" max="100000" step="0.01" required value={limite} onChange={e => setLimite(e.target.value)} className={`${INPUT} mt-1.5 w-40`} />
        </label>
        <button disabled={salvando} className={BOTAO}>{salvando ? "Salvando…" : "Salvar limite"}</button>
      </form>
      <p className="text-xs text-fg/65">Ao atingir o limite, novas gerações com IA pausam até você aumentá-lo ou o ciclo virar. A previsão não inclui operações em andamento. Reproduzir áudios prontos não gera nova cobrança. {consumo.regra_cambio}</p>
    </>}

    <div className="space-y-3 border-t border-border-strong pt-6">
      <h3 className="font-display text-base font-bold text-fg">Últimos usos</h3>
      {erroUsos && <p className="text-sm text-laranja">Não foi possível carregar os usos. Tente atualizar.</p>}
      {!erroUsos && usos.length === 0 && (carregandoUsos
        ? <p role="status" className="text-sm text-fg/65">Carregando usos…</p>
        : <p className="text-sm text-fg/65">Nenhum uso registrado.</p>)}
      {usos.length > 0 && <div aria-busy={carregandoUsos} className={carregandoUsos ? "opacity-60 transition-opacity" : "transition-opacity"}>
        {/* Celular: um cartão por uso; seis colunas não cabem em 390px. */}
        <ul className="space-y-3 sm:hidden">{usos.map(u => <li key={u.id} className="rounded-xl border border-border-strong p-3 text-sm">
          <div className="flex items-baseline justify-between gap-3">
            <span className="font-medium text-fg">{rotuloFuncionalidade(u.funcionalidade)}</span>
            <span className="font-semibold tabular-nums">{reaisPreciso(u.preco_brl)}</span>
          </div>
          <p className="text-xs text-fg/65"><span translate="no">{nomeModelo(u.modelo)}</span> · {rotuloEstadoUso(u.estado)}</p>
          <p className="mt-1 tabular-nums break-words">{resumirUnidades(u.unidades)}</p>
          <p className="mt-1 text-xs text-fg/65 tabular-nums">{dataHora(u.iniciado_em)}</p>
        </li>)}</ul>
        <div className="hidden sm:block overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase tracking-wide text-fg/65"><tr>
              {["Data", "O que foi gerado", "Quantidade"].map(t => <th key={t} scope="col" className="p-2 font-medium">{t}</th>)}
              <th scope="col" className="p-2 font-medium text-right">Preço</th>
              <th scope="col" className="p-2 font-medium">Estado</th>
            </tr></thead>
            <tbody>{usos.map(u => <tr key={u.id} title={`Tarifa ${tarifa(u.tarifa)}`} className="border-t border-border-strong align-top">
              <td className="p-2 whitespace-nowrap tabular-nums">{dataHora(u.iniciado_em)}</td>
              <td className="p-2">{rotuloFuncionalidade(u.funcionalidade)}<br /><span className="text-fg/65" translate="no">{nomeModelo(u.modelo)}</span></td>
              <td className="p-2 tabular-nums">{resumirUnidades(u.unidades)}</td>
              <td className="p-2 text-right tabular-nums">{reaisPreciso(u.preco_brl)}</td>
              <td className="p-2">{rotuloEstadoUso(u.estado)}</td>
            </tr>)}</tbody>
          </table>
        </div>
      </div>}
      <Paginacao rotulo="Páginas dos últimos usos" pagina={paginaUsos} temProxima={temMaisUsos} carregando={carregandoUsos} onMudar={setPaginaUsos} />
    </div>

    <div className="space-y-3 border-t border-border-strong pt-6">
      <h3 className="font-display text-base font-bold text-fg">Histórico de faturas</h3>
      {faturas.length === 0 ? <p className="text-sm text-fg/65">Nenhuma fatura emitida.</p> : <>
        <ul className="space-y-3 sm:hidden">{paginaDeFaturas.itens.map(f => <li key={f.id} className="rounded-xl border border-border-strong p-3 text-sm">
          <div className="flex items-baseline justify-between gap-3">
            <span className="tabular-nums">{data(f.inicio)} — {data(f.fim)}</span>
            <span className="font-semibold tabular-nums">{reais(f.total_brl)}</span>
          </div>
          <div className="mt-1 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
            <span className="text-xs text-fg/65">{rotuloEstadoFatura(f.estado)}</span>
            {f.url && <a className={LINK_FATURA} href={f.url} target="_blank" rel="noopener noreferrer">Abrir fatura ↗</a>}
          </div>
        </li>)}</ul>
        <table className="hidden w-full text-left text-sm sm:table">
          <thead className="text-xs uppercase tracking-wide text-fg/65"><tr>
            <th scope="col" className="p-2 font-medium">Período</th>
            <th scope="col" className="p-2 font-medium">Estado</th>
            <th scope="col" className="p-2 font-medium text-right">Total</th>
            <th scope="col" className="p-2"><span className="sr-only">Ações</span></th>
          </tr></thead>
          <tbody>{paginaDeFaturas.itens.map(f => <tr key={f.id} className="border-t border-border-strong">
            <td className="p-2 tabular-nums">{data(f.inicio)} — {data(f.fim)}</td>
            <td className="p-2">{rotuloEstadoFatura(f.estado)}</td>
            <td className="p-2 text-right tabular-nums">{reais(f.total_brl)}</td>
            <td className="p-2 text-right">{f.url && <a className={LINK_FATURA} href={f.url} target="_blank" rel="noopener noreferrer">Abrir fatura / regularizar ↗</a>}</td>
          </tr>)}</tbody>
        </table>
      </>}
      <Paginacao rotulo="Páginas do histórico de faturas" pagina={paginaDeFaturas.pagina} totalPaginas={paginaDeFaturas.totalPaginas} onMudar={setPaginaFaturas} />
    </div>
  </section>;
}
