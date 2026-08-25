"use client";

import { useEffect, useRef, useState } from "react";
import { apiFetch, ApiError } from "../../lib/api";
import { OndaLed, OndaSpin } from "../OndaLogo";

type Interaction = {
  id: number;
  telefone: string;
  nome: string | null;
  mensagem_usuario: string;
  resposta: string | null;
  status: string;
  criado_em: string;
};

const STATUS_STYLE: Record<string, string> = {
  fila_musica: "bg-teal/10 text-teal",
  fila_abraco: "bg-amber/10 text-amber",
  guardado: "bg-paper/10 text-fg/60",
  bloqueado_horario: "bg-amber/10 text-amber",
  bloqueado_rate_limit: "bg-amber/10 text-amber",
  bloqueado_conteudo: "bg-rust/10 text-rust",
};

const STATUS_LABEL: Record<string, string> = {
  fila_musica: "Pedido de musica na fila",
  fila_abraco: "Na fila do alo",
  guardado: "So guardado",
  bloqueado_horario: "Fora do horario",
  bloqueado_rate_limit: "Limite atingido",
  bloqueado_conteudo: "Topico bloqueado",
};

const POLL_MS = 4000;

function formatarHora(iso: string): string {
  return new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

type Props = {
  radialistaId: number | null;
  nomeLocutor: string;
  pulso?: boolean;
  onNovaInteracao?: () => void;
};

export default function InteracoesPanel({ radialistaId, nomeLocutor, pulso, onNovaInteracao }: Props) {
  const [interacoes, setInteracoes] = useState<Interaction[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");
  const ultimoIdRef = useRef<number | null>(null);

  useEffect(() => {
    if (radialistaId === null) return;
    let ativo = true;
    ultimoIdRef.current = null;
    setCarregando(true);

    async function buscar() {
      try {
        const dados = await apiFetch<Interaction[]>(`/metrics/interactions?radialista_id=${radialistaId}&limit=30`);
        if (!ativo) return;
        if (dados.length > 0 && dados[0].id !== ultimoIdRef.current) {
          const primeiraCarga = ultimoIdRef.current === null;
          ultimoIdRef.current = dados[0].id;
          if (!primeiraCarga) onNovaInteracao?.();
        }
        setInteracoes(dados);
        setErro("");
      } catch (err) {
        if (ativo) setErro(err instanceof ApiError ? err.message : "Erro ao carregar interacoes");
      } finally {
        if (ativo) setCarregando(false);
      }
    }

    buscar();
    const intervalo = setInterval(buscar, POLL_MS);
    return () => {
      ativo = false;
      clearInterval(intervalo);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [radialistaId]);

  return (
    <section className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6 flex flex-col">
      <div className="flex items-center justify-between mb-4 shrink-0">
        <h2 className="font-display text-base font-bold text-fg flex items-center gap-2">
          Conversas
          <OndaLed color="rust" pulse={Boolean(pulso)} />
        </h2>
        <span className="font-mono text-xs font-medium text-fg/35">Atualiza a cada 4s</span>
      </div>

      {erro && <p className="text-sm text-rust mb-3">{erro}</p>}

      {carregando ? (
        <p className="flex items-center gap-2 text-sm text-fg/55">
          <OndaSpin size={16} /> Carregando conversas...
        </p>
      ) : interacoes.length === 0 ? (
        <p className="text-sm text-fg/55">
          Nenhuma interacao ainda. Assim que um ouvinte mandar mensagem no WhatsApp, ela aparece aqui.
        </p>
      ) : (
        <div className="space-y-3 max-h-96 overflow-y-auto pr-1 -mr-1">
          {interacoes.map((it) => (
            <article key={it.id} className="rounded-xl border border-border-strong p-4">
              <div className="flex items-center justify-between font-mono text-xs text-fg/35 mb-2">
                <span>{it.nome ? `${it.nome} · ${it.telefone}` : `Ouvinte ${it.telefone}`}</span>
                <span>{formatarHora(it.criado_em)}</span>
              </div>

              <div className="text-sm text-fg/85 mb-2">
                <span className="font-medium text-fg/55">Ouvinte: </span>
                {it.mensagem_usuario}
              </div>

              {it.resposta && (
                <div className="text-sm text-fg/85">
                  <span className="font-medium text-amber">{nomeLocutor}: </span>
                  {it.resposta}
                </div>
              )}

              <div className="mt-3">
                <span
                  className={`inline-block text-xs font-medium px-2 py-0.5 rounded-full ${
                    STATUS_STYLE[it.status] ?? "bg-paper/10 text-fg/60"
                  }`}
                >
                  {STATUS_LABEL[it.status] ?? it.status}
                </span>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
