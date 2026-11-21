"use client";

import { useEffect, useState } from "react";
import { apiFetch, apiFetchBlob, apiFetchDownload, apiFetchForm } from "../../lib/api";
import { BlocoEsportivo, ConteudoEsportivo, dataNoFuso, EdicaoEsportiva, FonteEsportiva, isoNoFuso, rotuloEstado, tempoEsportivo } from "../../lib/esportes";
import { botao, campo, Campo, primario } from "./ConfiguracaoEsportiva";
import FatosEditor from "./FatosEditor";

export default function EdicaoEditor({ edicao, fontes, onSave, onDirty, onBusy }: {
  edicao: EdicaoEsportiva; fontes: FonteEsportiva[]; onSave: (e: EdicaoEsportiva) => void; onDirty: (v: boolean) => void; onBusy?: (v: boolean) => void;
}) {
  const [valor, setValor] = useState<ConteudoEsportivo>(edicao.conteudo);
  const [blocoId, setBlocoId] = useState(edicao.conteudo.blocos[0].id);
  const [ocupado, setOcupado] = useState("");
  const [erro, setErro] = useState("");
  const [mensagem, setMensagem] = useState("");
  const [confereRoteiro, setConfereRoteiro] = useState(false);
  const [confereAudio, setConfereAudio] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  const sujo = JSON.stringify(valor) !== JSON.stringify(edicao.conteudo);
  const bloco = valor.blocos.find((b) => b.id === blocoId) ?? valor.blocos[0];
  const fuso = valor.perfil.fuso;
  useEffect(() => { setValor(edicao.conteudo); setConfereRoteiro(false); setConfereAudio(false); setPreview(null); }, [edicao]);
  useEffect(() => { onDirty(sujo); }, [sujo, onDirty]);
  useEffect(() => { onBusy?.(!!ocupado); return () => onBusy?.(false); }, [ocupado, onBusy]);
  useEffect(() => { if (!sujo) return; const avisar = (e: BeforeUnloadEvent) => { e.preventDefault(); }; window.addEventListener("beforeunload", avisar); return () => window.removeEventListener("beforeunload", avisar); }, [sujo]);
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);
  useEffect(() => { setPreview(null); }, [blocoId]);
  const atualizarBloco = (p: Partial<BlocoEsportivo>) => setValor({ ...valor, blocos: valor.blocos.map((b) => b.id === bloco.id ? { ...b, ...p } : b) });
  async function executar(nome: string, tarefa: () => Promise<void>) {
    setOcupado(nome); setErro(""); setMensagem("");
    try { await tarefa(); } catch (e) { setErro(e instanceof Error ? e.message : "Não foi possível concluir a ação."); } finally { setOcupado(""); }
  }
  async function acao(nome: string, caminho: string, dados: object = {}) {
    await executar(nome, async () => { const resposta = await apiFetch<EdicaoEsportiva>(`/esportes/edicoes/${edicao.id}/${caminho}`, { method: "POST", body: JSON.stringify({ revisao: edicao.revisao, ...dados }) }); onSave(resposta); setMensagem("Etapa concluída. A revisão foi registrada."); });
  }
  const travado = !!ocupado;
  const pronto = !sujo && !travado;
  const totalAudio = Object.values(edicao.audios).reduce((s, a) => s + a.duracao_s, 0);
  return <div className="space-y-5">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-sm text-acento-claro">{rotuloEstado[edicao.estado] ?? edicao.estado} · Revisão {edicao.revisao}</p><h2 className="mt-1 font-display text-2xl font-semibold">{valor.titulo}</h2></div><div className="flex gap-2"><button className={botao} disabled={!pronto} onClick={() => executar("manifesto", () => apiFetchDownload(`/esportes/edicoes/${edicao.id}/manifesto`, `esportes-${edicao.id}-r${edicao.revisao}.json`))}>Registro editorial</button><button className={primario} disabled={!sujo || travado} onClick={() => executar("salvar", async () => { onSave(await apiFetch<EdicaoEsportiva>(`/esportes/edicoes/${edicao.id}`, { method: "PUT", body: JSON.stringify({ revisao: edicao.revisao, conteudo: valor }) })); setMensagem("Roteiro salvo. Os áudios e as aprovações precisam ser refeitos para esta versão."); })}>{ocupado === 'salvar' ? "Salvando…" : "Salvar edição"}</button></div></div>
    <div className="grid gap-4 sm:grid-cols-2"><Campo label="Título da edição"><input disabled={travado} className={campo} value={valor.titulo} onChange={(e) => setValor({ ...valor, titulo: e.target.value })} /></Campo><Campo label={`Exibição prevista (${fuso})`}><input disabled={travado} type="datetime-local" className={campo} value={dataNoFuso(valor.exibicao_em, fuso)} onChange={(e) => { try { setValor({ ...valor, exibicao_em: isoNoFuso(e.target.value, fuso) }); } catch (e) { setErro(e instanceof Error ? e.message : "Horário inválido"); } }} /></Campo></div>
    {sujo && <div className="flex flex-wrap items-center gap-3"><p role="status" className="text-sm text-laranja">Há alterações não salvas. Salve para validar, pedir sugestões ou produzir áudio.</p><button className={botao} disabled={travado} onClick={() => executar("recarregar", async () => { onSave(await apiFetch<EdicaoEsportiva>(`/esportes/edicoes/${edicao.id}`)); })}>Descartar alterações e recarregar</button></div>}
    {erro && <p role="alert" className="rounded-xl border border-laranja/40 p-3 text-sm text-laranja">{erro}</p>}
    {mensagem && <p role="status" className="text-sm text-acento-claro">{mensagem}</p>}
    <FatosEditor fatos={valor.fatos} fontes={fontes} fuso={fuso} exibicao={valor.exibicao_em} disabled={travado} onChange={(fatos) => setValor({ ...valor, fatos })} />
    <div className="overflow-hidden rounded-2xl border border-border-strong bg-surface lg:grid lg:grid-cols-[250px_minmax(0,1fr)]">
      <aside className="border-b border-border lg:border-b-0 lg:border-r"><div className="border-b border-border p-4"><h3 className="font-semibold">Espelho da edição</h3><p className="text-xs text-fg/65">{tempoEsportivo(valor.blocos.reduce((s, b) => s + b.duracao_s, 0))} previstos · {tempoEsportivo(totalAudio)} de áudio</p></div><ol className="flex overflow-x-auto lg:block">{valor.blocos.map((b, i) => <li key={b.id} className="shrink-0 lg:shrink"><button disabled={travado} onClick={() => setBlocoId(b.id)} aria-current={b.id === bloco.id ? "step" : undefined} className={`flex w-full items-start gap-3 px-4 py-3 text-left text-sm ${b.id === bloco.id ? 'bg-acento/15 text-acento-claro' : 'text-fg/75 hover:bg-fg/5'}`}><span className="text-xs tabular-nums pt-0.5">{i + 1}</span><span><span className="block font-semibold">{b.titulo}</span><span className="text-xs tabular-nums">{tempoEsportivo(b.duracao_s)}{edicao.audios[b.id] ? ` · Áudio ${tempoEsportivo(edicao.audios[b.id].duracao_s)}` : " · Sem áudio"}</span></span></button></li>)}</ol></aside>
      <section className="min-w-0 space-y-4 p-4 sm:p-5" aria-label={`Editor do bloco ${bloco.titulo}`}>
        <div className="flex flex-wrap justify-between gap-2"><h3 className="font-display text-xl font-semibold">{bloco.titulo}</h3><span className="text-sm tabular-nums text-fg/65">Alvo {tempoEsportivo(bloco.duracao_s)}</span></div>
        <div className="grid gap-3 sm:grid-cols-3"><Campo label="Duração-alvo (segundos)"><input className={campo} type="number" min={5} max={600} disabled={travado} value={bloco.duracao_s} onChange={(e) => atualizarBloco({ duracao_s: Number(e.target.value) })} /></Campo><Campo label="Responsável"><input className={campo} disabled={travado} value={bloco.responsavel} onChange={(e) => atualizarBloco({ responsavel: e.target.value })} /></Campo><Campo label="Transição / vinheta"><input className={campo} disabled={travado} value={bloco.transicao} onChange={(e) => atualizarBloco({ transicao: e.target.value })} /></Campo></div>
        <fieldset className="space-y-2"><legend className="mb-2 text-sm font-semibold">Fatos usados nesta fala</legend>{!valor.fatos.length && <p className="text-sm text-fg/65">Adicione fatos à ficha para vincular evidências ao bloco.</p>}{valor.fatos.map((f) => <label key={f.id} className="flex items-start gap-2 text-sm"><input disabled={travado} className="mt-1" type="checkbox" checked={bloco.fato_ids.includes(f.id)} onChange={(e) => atualizarBloco({ fato_ids: e.target.checked ? [...bloco.fato_ids, f.id] : bloco.fato_ids.filter((id) => id !== f.id) })} /><span>{f.texto}<span className="block text-xs text-fg/65">{f.evento} · {f.confirmacao}</span></span></label>)}</fieldset>
        <Campo label={bloco.tipo === 'intervalo' ? "Descrição / transcrição da inserção aprovada" : "Fala proposta"}><textarea disabled={travado} rows={10} className={`${campo} leading-relaxed`} value={bloco.texto} onChange={(e) => atualizarBloco({ texto: e.target.value })} /></Campo>
        <p className="text-xs text-fg/65">{bloco.texto.trim() ? bloco.texto.trim().split(/\s+/).length : 0} palavras. A duração será medida no áudio. Inclua vinhetas e transições no arquivo de cada bloco.</p>
        {bloco.opcional && <Campo label="Reserva editorial aprovada para este quadro"><textarea disabled={travado} rows={2} className={campo} value={bloco.reserva} onChange={(e) => atualizarBloco({ reserva: e.target.value })} /></Campo>}
        <div className="flex flex-wrap gap-2">
          {bloco.tipo !== 'intervalo' && <button className={botao} disabled={!pronto} onClick={() => executar("sugestao", async () => { const sugestao = await apiFetch<Pick<BlocoEsportivo, 'texto' | 'fato_ids'>>(`/esportes/edicoes/${edicao.id}/blocos/${bloco.id}/sugerir`, { method: "POST", body: JSON.stringify({ revisao: edicao.revisao }) }); atualizarBloco(sugestao); setMensagem("Sugestão recebida. Confira cada frase com a evidência e salve a edição."); })}>{ocupado === 'sugestao' ? "Escrevendo…" : "Sugerir fala com IA"}</button>}
          {bloco.tipo !== 'intervalo' && <button className={botao} disabled={!pronto || !edicao.aprovacao_roteiro || !!edicao.alertas.length} onClick={() => acao("voz", `blocos/${bloco.id}/gerar-audio`)}>{ocupado === 'voz' ? "Gerando áudio…" : "Gerar voz do bloco"}</button>}
          <label className={`${botao} ${!pronto || !edicao.aprovacao_roteiro || edicao.alertas.length ? 'opacity-50' : 'cursor-pointer'}`}>Enviar áudio / reserva<input aria-label="Enviar áudio do bloco" className="sr-only" type="file" accept="audio/mpeg,.mp3" disabled={!pronto || !edicao.aprovacao_roteiro || !!edicao.alertas.length} onChange={(e) => { const arquivo = e.target.files?.[0]; if (!arquivo) return; e.target.value = ''; executar("upload", async () => { const form = new FormData(); form.append("arquivo", arquivo); onSave(await apiFetchForm<EdicaoEsportiva>(`/esportes/edicoes/${edicao.id}/blocos/${bloco.id}/audio?revisao=${edicao.revisao}`, form)); }); }} /></label>
          {edicao.audios[bloco.id] && <button className={botao} disabled={!pronto || !!edicao.alertas.length} onClick={() => executar("ouvir", async () => { const audio = await apiFetchBlob(`/esportes/edicoes/${edicao.id}/blocos/${bloco.id}/audio`); setPreview(URL.createObjectURL(audio)); })}>Ouvir bloco</button>}
        </div>
        {preview && <audio controls src={preview} className="w-full" aria-label={`Áudio de ${bloco.titulo}`} />}
        {bloco.fato_ids.map((id) => { const f = valor.fatos.find((f) => f.id === id); if (!f) return null; const fonte = fontes.find((s) => s.id === f.fonte_id); return <div className="rounded-xl bg-bg p-3 text-sm" key={id}><p className="font-semibold">{fonte?.organizacao ?? 'Fonte ausente'} · {f.confirmacao}</p><blockquote className="mt-2 border-l-2 border-border-strong pl-3 text-fg/80">{f.evidencia}</blockquote><a className="mt-2 block break-all text-acento-claro underline" href={f.url} target="_blank" rel="noopener noreferrer">Página original</a><p className="mt-1 text-xs text-fg/65">Evento: {dataNoFuso(f.ocorrido_em, fuso).replace('T', ' ')} · Coleta: {dataNoFuso(f.coletado_em, fuso).replace('T', ' ')} · Validade: {dataNoFuso(f.valido_ate, fuso).replace('T', ' ')} ({fuso})</p></div>; })}
      </section>
    </div>
    <section className="space-y-4 rounded-2xl border border-border-strong p-5"><h3 className="font-display text-lg font-semibold">Revisão e liberação da edição</h3>
      {!!edicao.alertas.length && <details open><summary className="cursor-pointer text-sm font-semibold text-laranja">{edicao.alertas.length} {edicao.alertas.length === 1 ? "pendência editorial" : "pendências editoriais"} na versão salva</summary><ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-fg/80">{edicao.alertas.map((a) => <li key={a}>{a}</li>)}</ul></details>}
      <label className="flex items-start gap-2 text-sm"><input className="mt-1" disabled={!pronto || !!edicao.alertas.length} type="checkbox" checked={confereRoteiro} onChange={(e) => setConfereRoteiro(e.target.checked)} />Conferi cada afirmação com sua evidência, nomes, placares, datas, contas e atribuições. A revisão da IA serve de apoio à minha decisão editorial.</label>
      <button className={botao} disabled={!pronto || !confereRoteiro || !!edicao.alertas.length} onClick={() => acao("aprovar-roteiro", "aprovar-roteiro", { conferido: true })}>Aprovar roteiro desta versão</button>
      {!!edicao.alertas_audio.length && <details><summary className="cursor-pointer text-sm text-fg/80">Pendências de áudio e duração</summary><ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-fg/65">{edicao.alertas_audio.map((a) => <li key={a}>{a}</li>)}</ul></details>}
      <label className="flex items-start gap-2 text-sm"><input className="mt-1" disabled={!pronto || !edicao.aprovacao_roteiro || !!edicao.alertas.length || !!edicao.alertas_audio.length} type="checkbox" checked={confereAudio} onChange={(e) => setConfereAudio(e.target.checked)} />Ouvi todos os áudios desta versão. Conferi pronúncias, pausas, números, negativas, inserções e correspondência com o roteiro aprovado.</label>
      <div className="flex flex-wrap gap-2"><button className={botao} disabled={!pronto || !confereAudio || !!edicao.alertas.length || !!edicao.alertas_audio.length} onClick={() => acao("aprovar-audio", "aprovar-audio", { conferido: true })}>Aprovar áudios desta versão</button><button className={primario} disabled={!pronto || !edicao.aprovacao_audio || !!edicao.alertas.length || !!edicao.alertas_audio.length} onClick={() => executar("exportar", () => apiFetchDownload(`/esportes/edicoes/${edicao.id}/exportar`, `esportes-${edicao.id}-r${edicao.revisao}.mp3`))}>{ocupado === 'exportar' ? "Montando edição…" : "Exportar edição em MP3"}</button></div>
      <p className="text-xs text-fg/65">O arquivo reúne os blocos inteiros na ordem do espelho. Ajuste o roteiro ou envie inserções revisadas para fechar a duração. A exportação é revalidada e não confirma agendamento ou exibição.</p>
    </section>
    {!!edicao.historico.length && <details className="text-sm"><summary className="cursor-pointer text-fg/65">Histórico editorial ({edicao.historico.length})</summary><ol className="mt-3 space-y-2">{edicao.historico.slice().reverse().map((h, i) => <li key={i} className="border-l-2 border-border pl-3"><span className="font-semibold">{({ roteiro_editado: 'Roteiro editado', roteiro_aprovado: 'Roteiro aprovado', audio_renderizado: 'Áudio preparado', audio_aprovado: 'Áudios aprovados' } as Record<string, string>)[h.acao] ?? h.acao}</span><span className="ml-2 text-fg/65">{dataNoFuso(h.em, fuso).replace('T', ' ')} · Revisão {h.revisao} · Editor #{h.usuario_id}</span></li>)}</ol></details>}
  </div>;
}
