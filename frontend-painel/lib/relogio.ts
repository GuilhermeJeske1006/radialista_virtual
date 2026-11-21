// Edição do relógio da hora no painel (F1). Puro: o backend (app/live/relogio.py) valida de novo
// e é a fonte de verdade dos presets. Os tempos são hipóteses de projeto, ajustáveis à operação.
import { EventoRelogio, RelogioHora } from "./types";

export const DURACAO_HORA_S = 3600;
// Uma música ajustável nunca fica com menos que isso ao compensar o ajuste de outro evento.
export const MINIMO_COMPENSACAO_S = 30;

export function formatarMinSeg(segundos: number): string {
  const total = Math.max(0, Math.round(segundos));
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

// "0:50", "00:50", "1:05" ou só segundos ("50"). Inválido = null.
export function lerMinSeg(texto: string): number | null {
  const limpo = texto.trim();
  const partes = limpo.match(/^(\d{1,2}):([0-5]\d)$/);
  if (partes) return Number(partes[1]) * 60 + Number(partes[2]);
  if (/^\d{1,4}$/.test(limpo)) return Number(limpo);
  return null;
}

export function recalcularInicios(eventos: EventoRelogio[]): EventoRelogio[] {
  let inicio = 0;
  return eventos.map((evento) => {
    const atualizado = { ...evento, inicio_s: inicio };
    inicio += evento.duracao_s;
    return atualizado;
  });
}

export function totais(eventos: EventoRelogio[]) {
  const soma = { musica_s: 0, fala_s: 0, intervalo_s: 0, total_s: 0 };
  for (const evento of eventos) {
    if (evento.tipo === "musica") soma.musica_s += evento.duracao_s;
    else if (evento.tipo === "intervalo") soma.intervalo_s += evento.duracao_s;
    else soma.fala_s += evento.duracao_s;
    soma.total_s += evento.duracao_s;
  }
  return soma;
}

function compensavel(evento: EventoRelogio): boolean {
  return evento.tipo === "musica" && evento.natureza === "ajustavel";
}

export type ResultadoAjuste = { relogio: RelogioHora; erro?: undefined } | { relogio?: undefined; erro: string };

// Muda a duração de um evento e compensa a diferença na próxima música ajustável (ou na anterior,
// se não houver próxima), para o total continuar em 60:00.
export function ajustarDuracao(relogio: RelogioHora, indice: number, novaDuracao: number): ResultadoAjuste {
  const atual = relogio.eventos[indice];
  if (!atual) return { erro: "Evento inexistente." };
  if (!Number.isFinite(novaDuracao) || novaDuracao <= 0) return { erro: "A duração precisa ser maior que zero." };
  const diferenca = Math.round(novaDuracao) - atual.duracao_s;
  if (diferenca === 0) return { relogio };
  const depois = relogio.eventos.findIndex((e, i) => i > indice && compensavel(e));
  const antes = [...relogio.eventos.keys()].reverse().find((i) => i < indice && compensavel(relogio.eventos[i]));
  const alvo = depois >= 0 ? depois : antes;
  if (alvo === undefined) {
    return { erro: "Não há música ajustável para compensar a mudança; o relógio precisa somar 60:00." };
  }
  const compensada = relogio.eventos[alvo].duracao_s - diferenca;
  if (compensada < MINIMO_COMPENSACAO_S) {
    return {
      erro: `"${relogio.eventos[alvo].rotulo}" ficaria com ${formatarMinSeg(Math.max(0, compensada))}; o mínimo é ${formatarMinSeg(MINIMO_COMPENSACAO_S)}.`,
    };
  }
  const eventos = relogio.eventos.map((e, i) =>
    i === indice ? { ...e, duracao_s: Math.round(novaDuracao) } : i === alvo ? { ...e, duracao_s: compensada } : e,
  );
  return { relogio: { ...relogio, eventos: recalcularInicios(eventos) } };
}
