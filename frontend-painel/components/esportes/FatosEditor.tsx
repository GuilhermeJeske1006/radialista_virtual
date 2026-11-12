"use client";

import { useState } from "react";
import { dataNoFuso, FatoEsportivo, FonteEsportiva, isoNoFuso } from "../../lib/esportes";
import { botao, campo, Campo, primario } from "./ConfiguracaoEsportiva";

function novoFato(fontes: FonteEsportiva[], exibicao: string): FatoEsportivo {
  const agora = new Date().toISOString();
  const fonte = fontes.find((f) => f.ativa);
  return { id: `f_${crypto.randomUUID().slice(0, 8)}`, texto: "", tipo: "noticia", evento: "", ocorrido_em: agora,
    publicado_em: agora, coletado_em: agora, valido_ate: new Date(Date.parse(exibicao) + 3600_000).toISOString(),
    fonte_id: fonte?.id ?? 0, fonte_revisao: fonte?.revisao ?? 1, url: "", evidencia: "", origem_comum: "",
    confirmacao: "provavel", oficial: false, revisado: false, sensivel: false, revisao_sensivel: false,
    participantes: [], competicao: "", placar: [] };
}
export default function FatosEditor({ fatos, fontes, fuso, exibicao, onChange, disabled }: {
  fatos: FatoEsportivo[]; fontes: FonteEsportiva[]; fuso: string; exibicao: string;
  onChange: (f: FatoEsportivo[]) => void; disabled: boolean;
}) {
  const [valor, setValor] = useState<FatoEsportivo | null>(null);
  const [erro, setErro] = useState("");
  const mudar = (dados: Partial<FatoEsportivo>) => valor && setValor({ ...valor, ...dados, revisado: false, revisao_sensivel: false });
  return <section className="space-y-3">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-display text-lg font-semibold">Ficha factual</h3><p className="mt-1 max-w-2xl text-sm text-fg/65">Leia a página original e registre cada fato com sua evidência. Publicação recente não torna um evento antigo uma novidade.</p></div><button disabled={disabled || !fontes.some((f) => f.ativa)} className={botao} onClick={() => { setValor(novoFato(fontes, exibicao)); setErro(""); }}>Adicionar fato</button></div>
    {!fatos.length && <p className="text-sm text-fg/65">Nenhum fato registrado. Comece pela fonte original; títulos e resultados de busca não bastam.</p>}
    {fatos.map((f) => <div key={f.id} className="flex items-start justify-between gap-3 border-l-2 border-acento/50 bg-surface-2/50 p-3"><div className="min-w-0"><p className="text-sm font-semibold">{f.evento}</p><p className="mt-1 text-sm text-fg/80">{f.texto}</p><p className="mt-1 text-xs text-fg/65">{fontes.find((s) => s.id === f.fonte_id)?.organizacao ?? "Fonte ausente"} · {f.revisado ? "Evidência revisada" : "Revisão pendente"} · {f.confirmacao}</p></div><button disabled={disabled} className={botao} onClick={() => { setValor(structuredClone(f)); setErro(""); }}>Editar</button></div>)}
    {valor && <form className="space-y-4 rounded-2xl border border-border-strong bg-surface p-4" onSubmit={(e) => {
      e.preventDefault();
      if (!valor.fonte_id || !valor.texto.trim() || !valor.evidencia.trim()) { setErro("Informe a fonte, o fato e a evidência."); return; }
      onChange(fatos.some((f) => f.id === valor.id) ? fatos.map((f) => f.id === valor.id ? valor : f) : [...fatos, valor]); setValor(null);
    }}><h4 className="font-semibold">Fato e evidência</h4><div className="grid gap-4 sm:grid-cols-2">
      <Campo label="Evento / acontecimento"><input required className={campo} value={valor.evento} onChange={(e) => mudar({ evento: e.target.value })} /></Campo>
      <Campo label="Registro editorial"><select className={campo} value={valor.tipo} onChange={(e) => mudar({ tipo: e.target.value as FatoEsportivo['tipo'] })}>{([['noticia', 'Notícia'], ['agenda', 'Agenda'], ['resultado', 'Resultado final'], ['escalacao', 'Escalação oficial'], ['transferencia', 'Transferência confirmada'], ['analise', 'Análise com fundamento'], ['atemporal', 'Conteúdo atemporal']] as const).map(([v, label]) => <option key={v} value={v}>{label}</option>)}</select></Campo>
      <Campo label="Fato verificado, declaração atribuída ou análise identificada"><textarea required className={campo} rows={3} value={valor.texto} onChange={(e) => mudar({ texto: e.target.value })} /></Campo>
      <Campo label="Trecho de evidência da página original"><textarea required className={campo} rows={3} value={valor.evidencia} onChange={(e) => mudar({ evidencia: e.target.value })} /></Campo>
      <Campo label="Fonte e revisão do cadastro"><select required className={campo} value={valor.fonte_id} onChange={(e) => { const fonte = fontes.find((f) => f.id === Number(e.target.value)); if (fonte) mudar({ fonte_id: fonte.id, fonte_revisao: fonte.revisao }); }}><option value={0}>Selecione uma fonte</option>{fontes.filter((f) => f.ativa || f.id === valor.fonte_id).map((f) => <option key={f.id} value={f.id}>{f.organizacao} (revisão {f.revisao})</option>)}</select></Campo>
      <Campo label="Link exato da página original"><input required type="url" className={campo} value={valor.url} onChange={(e) => mudar({ url: e.target.value })} /></Campo>
      <Campo label="Origem comum (agência, comunicado ou apuração própria)"><input required className={campo} value={valor.origem_comum} onChange={(e) => mudar({ origem_comum: e.target.value })} /></Campo>
      <Campo label="Condição de confirmação"><select className={campo} value={valor.confirmacao} onChange={(e) => mudar({ confirmacao: e.target.value as FatoEsportivo['confirmacao'] })}>{([['confirmado', 'Confirmado'], ['provavel', 'Provável / não confirmado'], ['negociacao', 'Negociação em andamento'], ['encerrado', 'Evento encerrado'], ['contestado', 'Fontes divergentes'], ['adiado', 'Adiado'], ['cancelado', 'Cancelado']] as const).map(([v, label]) => <option key={v} value={v}>{label}</option>)}</select></Campo>
      {([['ocorrido_em', 'Data do evento'], ['publicado_em', 'Publicação na fonte'], ['coletado_em', 'Coleta / conferência'], ['valido_ate', 'Válido até']] as const).map(([k, label]) => <Campo key={k} label={`${label} (${fuso})`}><input required type="datetime-local" className={campo} value={dataNoFuso(valor[k], fuso)} onChange={(e) => { try { mudar({ [k]: isoNoFuso(e.target.value, fuso) }); setErro(""); } catch (e) { setErro(e instanceof Error ? e.message : "Horário inválido"); } }} /></Campo>)}
      {(valor.tipo === "resultado" || valor.tipo === "agenda") && <>
        <Campo label="Participantes, separados por vírgula"><input className={campo} defaultValue={valor.participantes.join(", ")} onBlur={(e) => mudar({ participantes: e.target.value.split(",").map((v) => v.trim()).filter(Boolean) })} /></Campo>
        <Campo label="Competição"><input required={valor.tipo === 'resultado'} className={campo} value={valor.competicao} onChange={(e) => mudar({ competicao: e.target.value })} /></Campo>
      </>}
      {valor.tipo === "resultado" && <Campo label="Placar (dois gols, separados por vírgula)"><input required className={campo} defaultValue={valor.placar.join(", ")} placeholder="0, 0" onBlur={(e) => mudar({ placar: e.target.value.split(",").map((s) => Number(s.trim())) })} /></Campo>}
    </div>
      <p className="text-xs text-fg/65">Validade deve cobrir toda a edição. Resultado exige status encerrado; escalação e transferência precisam de confirmação. Fontes divergentes bloqueiam a pauta.</p>
      <div className="space-y-2 text-sm">
        <label className="flex gap-2"><input type="checkbox" checked={valor.oficial} onChange={(e) => mudar({ oficial: e.target.checked })} />Confirmação oficial</label>
        <label className="flex gap-2"><input type="checkbox" checked={valor.sensivel} onChange={(e) => mudar({ sensivel: e.target.checked })} />Tema sensível, como acusação ou saúde de atleta</label>
        <label className="flex gap-2"><input type="checkbox" checked={valor.revisado} onChange={(e) => {
          const fonte = fontes.find((f) => f.id === valor.fonte_id);
          setValor({ ...valor, revisado: e.target.checked, fonte_revisao: fonte?.revisao ?? valor.fonte_revisao });
        }} />Li a página original, conferi a evidência e suas datas</label>
        {valor.sensivel && <label className="flex gap-2"><input type="checkbox" checked={valor.revisao_sensivel} onChange={(e) => setValor({ ...valor, revisao_sensivel: e.target.checked })} />Revisei especificamente o tema sensível, sem inferir diagnóstico ou culpa</label>}
      </div>
      {erro && <p role="alert" className="text-sm text-laranja">{erro}</p>}
      <div className="flex gap-2"><button className={primario}>Incluir na ficha</button><button type="button" className={botao} onClick={() => setValor(null)}>Cancelar</button></div>
    </form>}
  </section>;
}
