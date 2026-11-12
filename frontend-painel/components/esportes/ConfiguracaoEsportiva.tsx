"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api";
import { FonteEsportiva, novaFonte, PerfilEsportivo } from "../../lib/esportes";

export const campo = "w-full rounded-xl border border-border-strong bg-bg px-3 py-2 text-sm text-fg";
export const botao = "rounded-xl border border-border-strong px-3 py-2 text-sm font-semibold hover:bg-fg/5 disabled:opacity-50 disabled:cursor-not-allowed";
export const primario = `${botao} bg-acento text-on-brand hover:bg-brand-600 border-transparent`;
export function Campo({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="flex min-w-0 flex-col gap-1.5 text-sm text-fg/80">{label}{children}</label>;
}
const lista = (v: string) => v.split(",").map((s) => s.trim()).filter(Boolean);

export function PerfilEditor({ perfil, programaId, onSave, onDirty, onBusy }: { perfil: PerfilEsportivo; programaId: number; onSave: (p: PerfilEsportivo) => void; onDirty?: (v: boolean) => void; onBusy?: (v: boolean) => void }) {
  const [valor, setValor] = useState(perfil);
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [salvo, setSalvo] = useState(false);
  const pendente = JSON.stringify(valor) !== JSON.stringify(perfil);
  useEffect(() => { onDirty?.(pendente); return () => onDirty?.(false); }, [pendente, onDirty]);
  useEffect(() => { onBusy?.(ocupado); return () => onBusy?.(false); }, [ocupado, onBusy]);
  function mudar(p: Partial<PerfilEsportivo>) { setValor({ ...valor, ...p }); setSalvo(false); }
  return <form className="space-y-5 rounded-2xl bg-surface p-5" onSubmit={async (e) => {
    e.preventDefault(); setOcupado(true); setErro("");
    try { const p = await apiFetch<PerfilEsportivo>(`/esportes/programas/${programaId}/perfil`, { method: "PUT", body: JSON.stringify(valor) }); onSave(p); setSalvo(true); }
    catch (e) { setErro(e instanceof Error ? e.message : "Erro ao salvar perfil."); } finally { setOcupado(false); }
  }}>
    <div><h2 className="font-display text-xl font-semibold">A identidade da sua edição</h2><p className="mt-1 max-w-2xl text-sm text-fg/65">O perfil será copiado para as próximas edições. Cada edição conserva a configuração com que foi criada. A voz é a do radialista do programa.</p></div>
    <div className="grid gap-4 sm:grid-cols-2">
      <Campo label="Nome padrão das edições esportivas"><input required maxLength={120} className={campo} value={valor.nome} onChange={(e) => mudar({ nome: e.target.value })} /></Campo>
      <Campo label="Região"><input className={campo} value={valor.regiao} onChange={(e) => mudar({ regiao: e.target.value })} /></Campo>
      <Campo label="Clubes, separados por vírgula"><input className={campo} defaultValue={valor.clubes.join(", ")} onBlur={(e) => mudar({ clubes: lista(e.target.value) })} /></Campo>
      <Campo label="Campeonatos, separados por vírgula"><input className={campo} defaultValue={valor.campeonatos.join(", ")} onBlur={(e) => mudar({ campeonatos: lista(e.target.value) })} /></Campo>
      <Campo label="Modalidades, separadas por vírgula"><input className={campo} defaultValue={valor.modalidades.join(", ")} onBlur={(e) => mudar({ modalidades: lista(e.target.value) })} /></Campo>
      <Campo label="Fuso horário da emissora"><input required className={campo} value={valor.fuso} onChange={(e) => mudar({ fuso: e.target.value })} placeholder="America/Sao_Paulo" /></Campo>
      <Campo label="Estilo de apresentação"><textarea className={campo} rows={3} value={valor.estilo} onChange={(e) => mudar({ estilo: e.target.value })} /></Campo>
      <Campo label="Orientação de identidade sonora"><textarea className={campo} rows={3} value={valor.identidade_sonora} onChange={(e) => mudar({ identidade_sonora: e.target.value })} /></Campo>
    </div>
    <fieldset><legend className="mb-2 text-sm font-semibold">Distribuição sugerida do conteúdo (%)</legend><div className="grid grid-cols-2 gap-3 sm:grid-cols-4">{([['regional', 'Regional'], ['nacional', 'Nacional'], ['internacional', 'Internacional'], ['outras', 'Outras modalidades']] as const).map(([k, label]) => <Campo key={k} label={label}><input type="number" min={0} max={100} required className={campo} value={valor.distribuicao[k]} onChange={(e) => mudar({ distribuicao: { ...valor.distribuicao, [k]: Number(e.target.value) } })} /></Campo>)}</div><p className="mt-2 text-xs text-fg/65">Devem somar 100%. A relevância e a qualidade da pauta prevalecem.</p></fieldset>
    <label className="flex gap-2 text-sm"><input type="checkbox" checked={valor.participacao} onChange={(e) => mudar({ participacao: e.target.checked })} />Planejar espaço para participação real e autorizada</label>
    <p className="text-xs text-fg/65">Neste piloto, o operador prepara as participações autorizadas como áudio e revisa sua transcrição no bloco. Sem participação, use uma reserva verificada.</p>
    {erro && <p role="alert" className="text-sm text-laranja">{erro}</p>}{salvo && <p role="status" className="text-sm text-acento-claro">Perfil salvo para as próximas edições.</p>}
    <button disabled={ocupado} className={primario}>{ocupado ? "Salvando…" : "Salvar perfil"}</button>
  </form>;
}

export function FontesEditor({ fontes, onSave, onDirty, onBusy }: { fontes: FonteEsportiva[]; onSave: () => Promise<void>; onDirty?: (v: boolean) => void; onBusy?: (v: boolean) => void }) {
  const [valor, setValor] = useState<ReturnType<typeof novaFonte> & { id?: number; revisao?: number }>(novaFonte);
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [aberto, setAberto] = useState(false);
  useEffect(() => { onDirty?.(aberto); return () => onDirty?.(false); }, [aberto, onDirty]);
  useEffect(() => { onBusy?.(ocupado); return () => onBusy?.(false); }, [ocupado, onBusy]);
  return <div className="space-y-4">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="font-display text-xl font-semibold">Fontes aprovadas pela emissora</h2><p className="mt-1 max-w-2xl text-sm text-fg/65">Cadastre o domínio exato após conferir organização, redirecionamentos e condições de uso. A coleta do piloto é manual; registrar um método não ativa integração.</p></div><button className={primario} onClick={() => { setValor(novaFonte()); setErro(""); setAberto(true); }}>Cadastrar fonte</button></div>
    {fontes.length === 0 && <p className="rounded-2xl border border-dashed border-border-strong p-6 text-sm text-fg/65">Nenhuma fonte aprovada. Cadastre a primeira fonte antes de preparar a pauta.</p>}
    {fontes.map((f) => <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-surface p-4" key={f.id}><div><p className="font-semibold">{f.organizacao} <span className={`ml-2 text-xs ${f.ativa ? "text-acento-claro" : "text-laranja"}`}>{f.ativa ? "Ativa" : "Bloqueada"}</span></p><p className="break-all text-sm text-fg/65">{f.dominio}</p><p className="text-xs text-fg/65">Revisão {f.revisao} · Cadastro conferido em {f.ultima_revisao.split("-").reverse().join("/")}</p></div><button className={botao} onClick={() => { setValor(f); setErro(""); setAberto(true); }}>Revisar fonte</button></div>)}
    {aberto && <form className="space-y-4 rounded-2xl border border-border-strong bg-surface p-5" onSubmit={async (e) => {
      e.preventDefault(); setOcupado(true); setErro("");
      try { const { id, ...payload } = valor; await apiFetch(`/esportes/fontes${id ? `/${id}` : ""}`, { method: id ? "PUT" : "POST", body: JSON.stringify(payload) }); await onSave(); setAberto(false); }
      catch (e) { setErro(e instanceof Error ? e.message : "Erro ao salvar fonte."); } finally { setOcupado(false); }
    }}><h3 className="font-semibold">{valor.id ? "Revisar cadastro" : "Nova fonte"}</h3><div className="grid gap-4 sm:grid-cols-2">
      {([['dominio', 'Domínio exato (ex.: www.organizacao.com.br)'], ['organizacao', 'Organização responsável'], ['temas', 'Temas cobertos'], ['regiao', 'Região'], ['idioma', 'Idioma'], ['frequencia_permitida', 'Frequência permitida']] as const).map(([k, label]) => <Campo key={k} label={label}><input required className={campo} value={valor[k]} onChange={(e) => setValor({ ...valor, [k]: e.target.value })} /></Campo>)}
      <Campo label="Método de acesso disponível"><select className={campo} value={valor.acesso} onChange={(e) => setValor({ ...valor, acesso: e.target.value as FonteEsportiva['acesso'] })}><option value="manual">Consulta manual</option><option value="api_autorizada">API autorizada</option><option value="feed_autorizado">Feed autorizado</option><option value="pagina_permitida">Página com acesso permitido</option></select></Campo>
      <Campo label="Última revisão do cadastro"><input required type="date" className={campo} value={valor.ultima_revisao} onChange={(e) => setValor({ ...valor, ultima_revisao: e.target.value })} /></Campo>
      <Campo label="Prioridade (1 é a maior)"><input required type="number" min={1} max={10} className={campo} value={valor.prioridade} onChange={(e) => setValor({ ...valor, prioridade: Number(e.target.value) })} /></Campo>
      <Campo label="Condições de uso e retenção verificadas"><textarea required rows={3} className={campo} value={valor.condicoes_uso} onChange={(e) => setValor({ ...valor, condicoes_uso: e.target.value })} /></Campo>
    </div><label className="flex gap-2 text-sm"><input type="checkbox" checked={valor.ativa} onChange={(e) => setValor({ ...valor, ativa: e.target.checked })} />Fonte ativa e aprovada para consulta</label><p className="text-xs text-fg/65">Alterar ou bloquear esta fonte exige nova revisão dos fatos vinculados antes da exportação das edições.</p>
      {erro && <p role="alert" className="text-sm text-laranja">{erro}</p>}<div className="flex gap-2"><button disabled={ocupado} className={primario}>Salvar fonte</button><button type="button" disabled={ocupado} className={botao} onClick={() => setAberto(false)}>Cancelar</button></div>
    </form>}
  </div>;
}
