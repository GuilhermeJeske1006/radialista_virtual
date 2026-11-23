"use client";

import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "../lib/api";

// F11 item 2: relatório pós-programa de um dia, montado pelo backend a partir do as-run confirmado pelo player, das
// promessas e dos pedidos (GET /config/programas/{id}/relatorio). Só leitura.
export type RelatorioPrograma = {
  data: string;
  as_run: { enviados: number; confirmados: number; falharam: number; sem_relato: number };
  nao_medido: string[];
  secoes: {
    promessas: { cumpridas: number; vencidas: number; canceladas_com_contingencia: number; abertas_no_fim: number };
    pedidos: { recebidos: number; executados: number; nao_atendidos: number; expirados: number; pendentes_fim: number };
    oralidade: { avisos: number };
    repeticao: { estrutura: number };
  };
  alertas: string[];
  sugestoes: string[];
};

type Props = { programaId: number };

function valido(r: unknown): r is RelatorioPrograma {
  return !!r && typeof r === "object" && "as_run" in r && "secoes" in r;
}

export default function RelatorioProgramaPanel({ programaId }: Props) {
  // Dia escolhido pelo operador; vazio = o backend decide (hoje no fuso da rádio) e devolve em `data`.
  const [diaEscolhido, setDiaEscolhido] = useState("");
  const [relatorio, setRelatorio] = useState<RelatorioPrograma | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    let ativo = true;
    setErro("");
    const sufixo = diaEscolhido ? `?data=${diaEscolhido}` : "";
    Promise.resolve(apiFetch<RelatorioPrograma>(`/config/programas/${programaId}/relatorio${sufixo}`))
      .then((r) => {
        if (!ativo) return;
        if (valido(r)) setRelatorio(r);
        else setErro("Relatório indisponível");
      })
      .catch((err) => ativo && setErro(err instanceof ApiError ? err.message : "Erro ao carregar o relatório"));
    return () => {
      ativo = false;
    };
  }, [programaId, diaEscolhido]);

  const r = relatorio;
  const data = diaEscolhido || r?.data || "";
  return (
    <section aria-label="Relatório do programa" className="space-y-3">
      <h3 className="font-mono text-xs uppercase tracking-wide text-acento-claro">Relatório do programa</h3>
      <div className="flex items-center gap-2 text-xs text-fg/70">
        <label htmlFor={`relatorio-data-${programaId}`}>Dia</label>
        <input
          id={`relatorio-data-${programaId}`}
          type="date"
          value={data}
          onChange={(e) => setDiaEscolhido(e.target.value)}
          className="rounded-lg border border-border-strong bg-bg px-2 py-1 text-xs text-fg"
        />
      </div>
      {erro && <p role="alert" className="text-xs text-red-400">{erro}</p>}
      {!r && !erro && <p className="text-xs text-fg/60">Carregando…</p>}
      {r && r.as_run.enviados === 0 && <p className="text-xs text-fg/60">Nada foi ao ar neste dia.</p>}
      {r && r.as_run.enviados > 0 && (
        <div className="space-y-2 text-sm text-fg">
          <p>
            No ar: {r.as_run.confirmados} de {r.as_run.enviados} blocos confirmados pelo player
            {r.as_run.falharam > 0 && `, ${r.as_run.falharam} com falha`}
            {r.as_run.sem_relato > 0 && `, ${r.as_run.sem_relato} sem relato`}.
          </p>
          <p>
            Promessas: {r.secoes.promessas.cumpridas} cumpridas, {r.secoes.promessas.vencidas} vencidas,{" "}
            {r.secoes.promessas.canceladas_com_contingencia} com contingência, {r.secoes.promessas.abertas_no_fim} abertas.
          </p>
          <p>
            Pedidos: {r.secoes.pedidos.recebidos} recebidos, {r.secoes.pedidos.executados} atendidos,{" "}
            {r.secoes.pedidos.nao_atendidos} não atendidos, {r.secoes.pedidos.pendentes_fim} pendentes.
          </p>
          <p>
            Oralidade: {r.secoes.oralidade.avisos} avisos. Aberturas repetidas: {r.secoes.repeticao.estrutura}.
          </p>
          {r.alertas.length > 0 && (
            <ul aria-label="Alertas" className="list-disc pl-5 text-laranja">
              {r.alertas.map((a) => <li key={a}>{a}</li>)}
            </ul>
          )}
          {r.sugestoes.length > 0 && (
            <ul aria-label="Sugestões para a próxima edição" className="list-disc pl-5 text-fg/80">
              {r.sugestoes.map((s) => <li key={s}>{s}</li>)}
            </ul>
          )}
        </div>
      )}
      {r && r.nao_medido.length > 0 && (
        <p className="text-xs text-fg/60">Não medido no ar: orçamento das falas e hard time do relógio.</p>
      )}
    </section>
  );
}
