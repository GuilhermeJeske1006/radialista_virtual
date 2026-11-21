"use client";

import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "../lib/api";
import { PecaReserva, TIPOS_RESERVA, TipoReserva } from "../lib/types";

// F11 item 3: peças de reserva. Nasce não aprovada; só o operador aprova. Editar tipo ou texto desaprova
// (o backend faz isso ao salvar). Só peça aprovada entra no ar quando a contingência acontece.
type Props = { programaId: number };

type Rascunho = { id?: number; tipo: TipoReserva; texto: string; aprovada?: boolean };

const inputClass =
  "w-full rounded-xl border border-border-strong bg-bg px-3 py-2 text-sm text-fg placeholder:text-fg/65 focus:outline-none focus:border-acento-claro/50 focus:ring-2 focus:ring-acento-claro/20";

export default function PecasReservaSection({ programaId }: Props) {
  const [salvas, setSalvas] = useState<PecaReserva[] | null>(null);
  const [itens, setItens] = useState<Rascunho[]>([]);
  const [novoTipo, setNovoTipo] = useState<TipoReserva>("convidado");
  const [novoTexto, setNovoTexto] = useState("");
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const url = `/config/programas/${programaId}/pecas-reserva`;

  useEffect(() => {
    apiFetch<PecaReserva[]>(url)
      .then((dados) => {
        setSalvas(dados);
        setItens(dados.map((p) => ({ id: p.id, tipo: p.tipo, texto: p.texto, aprovada: p.aprovada })));
      })
      .catch((err) => setErro(err instanceof ApiError ? err.message : "Erro ao carregar peças de reserva"));
  }, [url]);

  const sujo = JSON.stringify(itens.map(({ id, tipo, texto }) => ({ id, tipo, texto }))) !==
    JSON.stringify((salvas ?? []).map(({ id, tipo, texto }) => ({ id, tipo, texto })));

  function atualizar(indice: number, campo: "tipo" | "texto", valor: string) {
    setItens((atual) => atual.map((it, i) => (i === indice ? { ...it, [campo]: valor } : it)));
  }

  function adicionar() {
    if (!novoTexto.trim()) return;
    setItens((atual) => [...atual, { tipo: novoTipo, texto: novoTexto.trim() }]);
    setNovoTexto("");
  }

  async function salvar() {
    setOcupado(true);
    setErro("");
    try {
      const body = itens.map(({ id, tipo, texto }) => ({ id, tipo, texto }));
      const dados = await apiFetch<PecaReserva[]>(url, { method: "PUT", body: JSON.stringify(body) });
      setSalvas(dados);
      setItens(dados.map((p) => ({ id: p.id, tipo: p.tipo, texto: p.texto, aprovada: p.aprovada })));
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao salvar peças de reserva");
    } finally {
      setOcupado(false);
    }
  }

  async function aprovar(id: number) {
    setOcupado(true);
    setErro("");
    try {
      await apiFetch(`${url}/${id}/aprovar`, { method: "POST" });
      const dados = await apiFetch<PecaReserva[]>(url);
      setSalvas(dados);
      setItens(dados.map((p) => ({ id: p.id, tipo: p.tipo, texto: p.texto, aprovada: p.aprovada })));
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao aprovar a peça");
    } finally {
      setOcupado(false);
    }
  }

  return (
    <section aria-label="Peças de reserva" className="space-y-3">
      <h3 className="font-mono text-xs uppercase tracking-wide text-acento-claro">Peças de reserva</h3>
      <p className="text-xs text-fg/70">
        Usadas quando convidado, fonte, pedido, áudio ou horário falham. Só entram no ar depois de aprovadas aqui.
      </p>
      {erro && <p role="alert" className="text-xs text-red-400">{erro}</p>}

      {itens.map((peca, indice) => (
        <div key={peca.id ?? `novo-${indice}`} className="space-y-2 rounded-xl border border-border p-3">
          <div className="flex items-center justify-between gap-2">
            <select
              aria-label={`Tipo da peça ${indice + 1}`}
              className={inputClass + " max-w-xs"}
              value={peca.tipo}
              onChange={(e) => atualizar(indice, "tipo", e.target.value)}
            >
              {TIPOS_RESERVA.map((t) => (
                <option key={t.valor} value={t.valor}>{t.rotulo}</option>
              ))}
            </select>
            <span className="text-xs text-fg/70">
              {peca.id === undefined ? "novo" : peca.aprovada && !sujo ? "aprovada" : "não aprovada"}
            </span>
          </div>
          <textarea
            aria-label={`Texto da peça ${indice + 1}`}
            className={inputClass}
            rows={2}
            maxLength={600}
            value={peca.texto}
            onChange={(e) => atualizar(indice, "texto", e.target.value)}
          />
          <div className="flex gap-2">
            {peca.id !== undefined && (
              <button
                type="button"
                onClick={() => aprovar(peca.id!)}
                disabled={ocupado || sujo || peca.aprovada === true}
                title={sujo ? "Salve as alterações antes de aprovar" : undefined}
                className="rounded-xl border border-border-strong px-3 py-1.5 text-xs font-medium text-fg/80 hover:bg-fg/5 disabled:opacity-60"
              >
                Aprovar
              </button>
            )}
            <button
              type="button"
              onClick={() => setItens((atual) => atual.filter((_, i) => i !== indice))}
              disabled={ocupado}
              className="rounded-xl border border-border-strong px-3 py-1.5 text-xs font-medium text-fg/80 hover:bg-fg/5 disabled:opacity-60"
            >
              Remover
            </button>
          </div>
        </div>
      ))}

      <div className="space-y-2 rounded-xl border border-dashed border-border p-3">
        <select
          aria-label="Tipo da nova peça"
          className={inputClass + " max-w-xs"}
          value={novoTipo}
          onChange={(e) => setNovoTipo(e.target.value as TipoReserva)}
        >
          {TIPOS_RESERVA.map((t) => (
            <option key={t.valor} value={t.valor}>{t.rotulo}</option>
          ))}
        </select>
        <textarea
          aria-label="Texto da nova peça"
          className={inputClass}
          rows={2}
          maxLength={600}
          placeholder="Texto que o locutor lê quando a contingência acontece"
          value={novoTexto}
          onChange={(e) => setNovoTexto(e.target.value)}
        />
        <button
          type="button"
          onClick={adicionar}
          disabled={!novoTexto.trim()}
          className="rounded-xl border border-border-strong px-3 py-1.5 text-xs font-medium text-fg/80 hover:bg-fg/5 disabled:opacity-60"
        >
          Adicionar peça
        </button>
      </div>

      <button
        type="button"
        onClick={salvar}
        disabled={ocupado || !sujo}
        className="rounded-xl bg-acento-claro/20 px-3 py-1.5 text-xs font-medium text-fg hover:bg-acento-claro/30 disabled:opacity-60"
      >
        {ocupado ? "Salvando…" : "Salvar peças"}
      </button>
    </section>
  );
}
