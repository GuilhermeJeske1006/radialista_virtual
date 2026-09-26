"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "../lib/api";
import CombinacaoSelect from "./CombinacaoSelect";
import Modal from "./Modal";
import Paginacao, { paginar } from "./Paginacao";
import type { ModeloTarifado } from "./TarifasModelos";
import { CatalogoCombinacoes, Combinacao, HorarioPrograma, consumoMensalEstimado, nomeModelo, reais } from "../lib/combinacoes";
import { DIAS_SEMANA_LABEL } from "../lib/types";

type ProgramaConta = HorarioPrograma & { id: number; nome: string; radio_config_id?: number };
type Escolha = { texto?: string | null; voz?: string | null; combinacao?: string | null };
type Origem = "propria" | "locutor" | "padrao";
// Uma configuração da conta (WhatsApp ou programa) com o modelo que ela usa de fato hoje.
type Linha = { chave: string; nome: string; detalhe: string; programa: ProgramaConta | null; texto?: string; voz?: string; combinacao: Combinacao | null; origem: Origem };

const CARD = "space-y-5 bg-surface rounded-3xl border border-border-strong shadow-theme-xs p-6";
const ROTULO = "block text-sm font-medium text-fg/80";
const CAMPO = "block w-full rounded-xl border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-acento-claro/50 focus:ring-2 focus:ring-acento-claro/20";
const BOTAO = "rounded-xl bg-brand-500 px-4 py-2 text-sm font-medium text-on-brand hover:bg-brand-600 disabled:opacity-60 disabled:cursor-not-allowed";
const BOTAO_SECUNDARIO = "rounded-xl border border-border-strong px-4 py-2 text-sm font-medium text-fg hover:bg-fg/5 disabled:opacity-60 disabled:cursor-not-allowed";
const POR_PAGINA = 6;
const ORIGEM: Record<Origem, string> = { propria: "Escolha sua", locutor: "Herdada do radialista", padrao: "Padrão do Locufy" };

function horario(p: ProgramaConta) {
  const faixa = `${p.horario_inicio.slice(0, 5)}–${p.horario_fim.slice(0, 5)}`;
  if (p.data_especifica) return `${faixa} · ${new Date(`${p.data_especifica}T00:00`).toLocaleDateString("pt-BR")}`;
  const dias = p.dias_semana.length === 0 || p.dias_semana.length === 7
    ? "todos os dias" : [...p.dias_semana].sort().map(d => DIAS_SEMANA_LABEL[d]).join(", ");
  return `${faixa} · ${dias}`;
}

function acharCombinacao(catalogo: CatalogoCombinacoes | null, e: Escolha) {
  const lista = catalogo?.combinacoes ?? [];
  return lista.find(c => c.id === e.combinacao) ?? lista.find(c => c.modelo_texto === e.texto && c.modelo_voz === e.voz) ?? null;
}

// Mesma precedência do backend (contexto_ia.selecionar_programa): programa, locutor, padrão.
function montarLinhas(programas: ProgramaConta[], escolhas: Record<string, Escolha>, catalogo: CatalogoCombinacoes | null): Linha[] {
  const padrao = catalogo?.padrao;
  const whatsapp = escolhas.whatsapp?.texto;
  return [
    { chave: "whatsapp", nome: "Atendimento WhatsApp", detalhe: "Respostas de texto aos ouvintes", programa: null,
      texto: whatsapp ?? padrao?.texto, combinacao: null, origem: whatsapp ? "propria" : "padrao" },
    ...programas.map((p): Linha => {
      const propria = escolhas[String(p.id)];
      const locutor = p.radio_config_id != null ? escolhas[`radialista:${p.radio_config_id}`] : undefined;
      const origem: Origem = propria?.texto ? "propria" : locutor?.texto ? "locutor" : "padrao";
      const e: Escolha = origem === "propria" ? propria! : origem === "locutor" ? locutor! : { ...padrao };
      return { chave: String(p.id), nome: p.nome, detalhe: horario(p), programa: p, texto: e.texto ?? undefined,
        voz: e.voz ?? undefined, combinacao: acharCombinacao(catalogo, e), origem };
    }),
  ];
}

function Modelos({ texto, voz }: { texto?: string; voz?: string }) {
  return <span className="text-xs text-fg/65">
    {texto && <>Texto: <span translate="no">{nomeModelo(texto)}</span></>}
    {voz && <> · Voz: <span translate="no">{nomeModelo(voz)}</span></>}
  </span>;
}

export default function ModelosConsumo() {
  const [programas, setProgramas] = useState<ProgramaConta[]>([]);
  const [escolhas, setEscolhas] = useState<Record<string, Escolha>>({});
  const [combinacoes, setCombinacoes] = useState<CatalogoCombinacoes | null>(null);
  const [tarifados, setTarifados] = useState<ModeloTarifado[]>([]);
  const [carregado, setCarregado] = useState(false);
  const [pagina, setPagina] = useState(1);
  const [aviso, setAviso] = useState(""); const [erro, setErro] = useState("");
  // Troca em andamento (modal).
  const [editando, setEditando] = useState<Linha | null>(null);
  const [selecionada, setSelecionada] = useState<Combinacao | null>(null);
  const [texto, setTexto] = useState(""); const [voz, setVoz] = useState("");
  const [salvando, setSalvando] = useState(false);
  const [erroTroca, setErroTroca] = useState("");

  useEffect(() => {
    Promise.all([
      apiFetch<Record<string, Escolha>>("/billing/modelos"),
      apiFetch<ProgramaConta[]>("/config/programas"),
      // Sem catálogo publicado, a lista ainda mostra os modelos; só a troca fica limitada.
      apiFetch<CatalogoCombinacoes>("/billing/combinacoes").catch(() => null),
      apiFetch<ModeloTarifado[]>("/billing/catalogo-modelos").catch(() => [] as ModeloTarifado[]),
    ])
      .then(([e, p, c, t]) => { setEscolhas(e); setProgramas(p); setCombinacoes(c); setTarifados(t); })
      .catch(() => setErro("Não foi possível carregar os modelos em uso. Atualize a página para tentar de novo."))
      .finally(() => setCarregado(true));
  }, []);

  function abrir(linha: Linha) {
    setEditando(linha); setSelecionada(linha.combinacao); setTexto(linha.texto ?? ""); setVoz(linha.voz ?? "");
    setErroTroca(""); setAviso("");
  }
  function fechar() { if (!salvando) setEditando(null); }

  async function salvar(acao: () => Promise<Record<string, Escolha>>, sucesso: string) {
    setSalvando(true); setErroTroca("");
    try { setEscolhas(await acao()); setAviso(sucesso); setEditando(null); }
    catch (e) { setErroTroca(e instanceof Error ? e.message : "Não foi possível trocar o modelo. Tente novamente."); }
    finally { setSalvando(false); }
  }
  const putCombinacao = (combinacao: Combinacao, programaId: number) => apiFetch<Record<string, Escolha>>("/billing/combinacao",
    { method: "PUT", body: JSON.stringify({ combinacao_id: combinacao.id, programa_id: programaId }) });

  function aplicar() {
    if (!editando?.programa || !selecionada) return;
    const programaId = editando.programa.id;
    void salvar(() => putCombinacao(selecionada, programaId),
      `${editando.nome} agora usa ${selecionada.nome}. Vale para as próximas falas geradas.`);
  }
  function aplicarEmTodos() {
    if (!selecionada) return;
    void salvar(async () => {
      let resposta = escolhas;
      for (const [i, p] of programas.entries()) {
        try { resposta = await putCombinacao(selecionada, p.id); }
        catch (e) {
          // Os anteriores já trocaram: mostra o estado real antes de avisar a falha.
          setEscolhas(resposta);
          throw new Error(`Trocado em ${i} de ${programas.length} programas. ${e instanceof Error ? e.message : ""}`.trim());
        }
      }
      return resposta;
    }, `Todos os ${programas.length} programas agora usam ${selecionada.nome}.`);
  }
  function salvarSeparado() {
    if (!editando) return;
    const programa = editando.programa;
    void salvar(() => apiFetch("/billing/modelos", { method: "PUT",
      body: JSON.stringify({ texto, voz: programa ? voz : null, programa_id: programa?.id ?? null }) }),
      programa ? `${editando.nome} agora usa texto ${nomeModelo(texto)} e voz ${nomeModelo(voz)}.`
        : `Atendimento WhatsApp agora responde com ${nomeModelo(texto)}.`);
  }

  const linhas = montarLinhas(programas, escolhas, combinacoes);
  const paginaAtual = paginar(linhas, pagina, POR_PAGINA);
  const opcoes = (tipo: string) => tarifados.filter(m => m.tipo === tipo);
  const podeTrocar = (linha: Linha) => opcoes("llm").length > 0 && (!linha.programa || opcoes("tts").length > 0) || (!!linha.programa && !!combinacoes?.combinacoes.length);
  const emUso = editando?.origem === "propria" && selecionada != null && selecionada.id === editando.combinacao?.id;

  // Rodapé do modal: fica visível enquanto a lista de combinações rola.
  function acoes(linha: Linha) {
    return <div className="space-y-2">
      {erroTroca && <p role="alert" className="text-sm text-laranja">{erroTroca}</p>}
      {/* Celular: principal em cima e sem "Cancelar" (o X fecha), para sobrar espaço à lista. */}
      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:flex-wrap sm:justify-end sm:gap-3">
        <button type="button" className={`${BOTAO_SECUNDARIO} hidden sm:block`} disabled={salvando} onClick={fechar}>Cancelar</button>
        {linha.programa ? <>
          {programas.length > 1 && <button type="button" className={BOTAO_SECUNDARIO} disabled={salvando || !selecionada} onClick={aplicarEmTodos}>
            Usar em todos os programas ({programas.length})
          </button>}
          <button type="button" className={BOTAO} disabled={salvando || !selecionada || emUso} onClick={aplicar}>
            {salvando ? "Salvando…" : emUso ? "Já em uso" : `Usar ${selecionada?.nome ?? ""} neste programa`}
          </button>
        </> : <button form="troca-whatsapp" className={BOTAO} disabled={salvando || !texto || (linha.origem === "propria" && texto === linha.texto)}>
          {salvando ? "Salvando…" : "Salvar modelo"}
        </button>}
      </div>
    </div>;
  }

  return <section className={CARD} aria-labelledby="modelos-titulo">
    <div>
      <h2 id="modelos-titulo" className="font-display text-lg font-bold text-fg">Modelos em uso</h2>
      <p className="mt-1 text-sm text-fg/65">Cada programa usa um modelo de texto, que escreve as falas, e um de voz, que as transforma em áudio. Troque quando quiser: vale para as próximas falas geradas.</p>
    </div>
    <div aria-live="polite">
      {aviso && <p role="status" className="rounded-xl bg-ciano/10 px-3 py-2 text-sm text-ciano">{aviso}</p>}
      {erro && <p role="alert" className="text-sm text-laranja">{erro}</p>}
    </div>
    {!carregado && <p role="status" className="text-sm text-fg/65">Carregando modelos em uso…</p>}

    {carregado && !erro && <div className="space-y-3">
      <ul className="divide-y divide-border-strong rounded-xl border border-border-strong">
        {paginaAtual.itens.map(l => <li key={l.chave} className="grid gap-3 p-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)_auto] sm:items-center">
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-fg">{l.nome}</p>
            <p className="text-xs text-fg/65 tabular-nums">{l.detalhe}</p>
          </div>
          <div className="min-w-0">
            <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-fg">
              <span className="font-medium">{l.programa ? l.combinacao?.nome ?? (l.origem === "padrao" ? "Padrão" : "Personalizada") : l.texto ? nomeModelo(l.texto) : "Padrão"}</span>
              <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${l.origem === "propria" ? "bg-acento/15 text-acento-claro" : "bg-fg/5 text-fg/65"}`}>{ORIGEM[l.origem]}</span>
            </p>
            {l.programa && <Modelos texto={l.texto} voz={l.voz} />}
            {l.programa && l.combinacao && <p className="text-xs text-fg/65 tabular-nums">≈ {reais(consumoMensalEstimado(l.combinacao, l.programa))}/mês de uso</p>}
          </div>
          <button type="button" className={`${BOTAO_SECUNDARIO} justify-self-start sm:justify-self-end`} disabled={!podeTrocar(l)} onClick={() => abrir(l)} aria-label={`Trocar modelo de ${l.nome}`}>
            Trocar modelo
          </button>
        </li>)}
      </ul>
      <Paginacao rotulo="Páginas dos modelos em uso" pagina={paginaAtual.pagina} totalPaginas={paginaAtual.totalPaginas} onMudar={setPagina} />
      {programas.length === 0 && <p className="text-sm text-fg/65">
        Crie um programa em <Link href="/programas" className="font-medium text-acento-claro hover:underline">Programas</Link> para escolher o modelo de locução.
      </p>}
      {!combinacoes?.combinacoes.length && tarifados.length === 0 && <p className="text-sm text-fg/65">A troca de modelos será liberada após a confirmação das tarifas contratadas e a avaliação de qualidade.</p>}
    </div>}

    <Modal open={!!editando} onClose={fechar} title={editando ? `Trocar modelo · ${editando.nome}` : ""} maxWidthClassName="max-w-4xl" footer={editando && acoes(editando)}>
      {editando && <div className="space-y-4">
        <p className="text-sm text-fg/80">
          Em uso agora: <strong className="text-fg">{editando.programa ? editando.combinacao?.nome ?? (editando.origem === "padrao" ? "Padrão" : "Personalizada") : nomeModelo(editando.texto ?? "")}</strong>
          {" "}({ORIGEM[editando.origem].toLowerCase()}). {editando.programa ? "Falas já geradas não mudam." : "Respostas já enviadas não mudam."}
        </p>

        {editando.programa ? <>
          {!!combinacoes?.combinacoes.length && <CombinacaoSelect key={editando.chave} catalogo={combinacoes} value={selecionada?.id ?? null} onChange={setSelecionada}
            programa={editando.programa} disabled={salvando} dicaTroca={false} />}
          {opcoes("llm").length > 0 && opcoes("tts").length > 0 && <details className="rounded-xl border border-border-strong p-4 text-sm" open={!combinacoes?.combinacoes.length}>
            <summary className="cursor-pointer font-medium text-fg hover:text-acento-claro">Prefere escolher o texto e a voz separadamente?</summary>
            <form className="mt-3 flex flex-wrap items-end gap-3" onSubmit={e => { e.preventDefault(); salvarSeparado(); }}>
              <label className={`${ROTULO} min-w-48`}>Texto
                <select required name="modelo_texto" className={`${CAMPO} mt-1.5`} value={texto} onChange={e => setTexto(e.target.value)}>
                  <option value="">Selecione</option>{opcoes("llm").map(m => <option key={m.id} value={m.modelo}>{nomeModelo(m.modelo)}</option>)}
                </select>
              </label>
              <label className={`${ROTULO} min-w-48`}>Voz
                <select required name="modelo_voz" className={`${CAMPO} mt-1.5`} value={voz} onChange={e => setVoz(e.target.value)}>
                  <option value="">Selecione</option>{opcoes("tts").map(m => <option key={m.id} value={m.modelo}>{nomeModelo(m.modelo)}</option>)}
                </select>
              </label>
              <button disabled={salvando} className={BOTAO_SECUNDARIO}>Salvar texto e voz</button>
            </form>
          </details>}
        </> : <form id="troca-whatsapp" className="space-y-2" onSubmit={e => { e.preventDefault(); salvarSeparado(); }}>
          <fieldset disabled={salvando} className="space-y-2">
            <legend className="mb-1 text-sm font-medium text-fg">Modelo de texto das respostas</legend>
            {opcoes("llm").map(m => <label key={m.id} className={`flex cursor-pointer items-start gap-2 rounded-xl border p-3 ${texto === m.modelo ? "border-acento-claro bg-acento/5" : "border-border-strong hover:border-acento-claro/40"}`}>
              <input type="radio" name="whatsapp_texto" value={m.modelo} checked={texto === m.modelo} onChange={() => setTexto(m.modelo)} className="accent-brand-500 mt-1 h-4 w-4 shrink-0" />
              <span className="min-w-0 text-sm">
                <span className="font-semibold text-fg" translate="no">{nomeModelo(m.modelo)}</span>
                {m.modelo === combinacoes?.padrao?.texto && <span className="ml-2 rounded-full bg-fg/5 px-2 py-0.5 text-[11px] font-medium text-fg/65">Padrão</span>}
                <span className="mt-0.5 block text-xs text-fg/75">{combinacoes?.modelos?.[m.modelo]?.descricao ?? m.descricao}</span>
              </span>
            </label>)}
          </fieldset>
        </form>}
      </div>}
    </Modal>
  </section>;
}
