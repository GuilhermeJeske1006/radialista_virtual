"use client";

import { useEffect, useState } from "react";
import { ajustarDuracao, formatarMinSeg, lerMinSeg, totais } from "../lib/relogio";
import { EventoRelogio, PresetRelogio, RelogioHora } from "../lib/types";

// Editor simples do relógio da hora (F1): escolher um preset e ajustar a duração de cada evento.
// Os tempos são hipóteses de projeto (pesquisa §9); o backend valida de novo ao gravar.

const inputClass =
  "w-full rounded-xl border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-acento-claro/50 focus:ring-2 focus:ring-acento-claro/20";
const labelClass = "block text-sm font-medium text-fg/80 mb-1.5";
const PASSO_S = 5;

const NATUREZA_LABEL: Record<EventoRelogio["natureza"], string> = {
  obrigatorio: "obrigatório",
  ajustavel: "ajustável",
  reserva: "reserva",
};

const FERIADO_LABEL: Record<RelogioHora["em_feriado"], string> = {
  mesmo: "Mesmo relógio",
  sem_intervalos: "Sem intervalos",
  sem_relogio: "Sem relógio no feriado (segue a sequência de blocos)",
};

type Props = {
  valor: RelogioHora | null;
  presets: PresetRelogio[];
  onChange: (relogio: RelogioHora | null) => void;
  /** Duração da janela do programa, para avisar quando não é múltipla de uma hora. */
  janelaSegundos?: number;
  /** Programa sem fonte de notícia configurada (as etapas de notícia viram música). */
  semFonteNoticia?: boolean;
};

function CampoDuracao({ evento, indice, onAjustar }: {
  evento: EventoRelogio;
  indice: number;
  onAjustar: (indice: number, segundos: number) => void;
}) {
  const [texto, setTexto] = useState(formatarMinSeg(evento.duracao_s));
  useEffect(() => setTexto(formatarMinSeg(evento.duracao_s)), [evento.duracao_s]);
  const rotulo = `Duração do evento ${indice + 1} (${evento.rotulo || evento.tipo})`;

  function confirmar() {
    const segundos = lerMinSeg(texto);
    if (segundos === null) {
      setTexto(formatarMinSeg(evento.duracao_s));
      return;
    }
    if (segundos !== evento.duracao_s) onAjustar(indice, segundos);
  }

  return (
    <div className="flex items-center gap-1">
      <button
        type="button"
        aria-label={`Diminuir 5 s: ${evento.rotulo || evento.tipo}`}
        className="rounded-lg border border-border-strong px-1.5 text-xs text-fg/70 hover:text-fg"
        onClick={() => onAjustar(indice, evento.duracao_s - PASSO_S)}
      >
        −
      </button>
      <input
        aria-label={rotulo}
        className="w-16 rounded-lg border border-border-strong bg-bg px-2 py-1 text-center font-mono text-xs text-fg"
        value={texto}
        onChange={(e) => setTexto(e.target.value)}
        onBlur={confirmar}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            confirmar();
          }
        }}
      />
      <button
        type="button"
        aria-label={`Aumentar 5 s: ${evento.rotulo || evento.tipo}`}
        className="rounded-lg border border-border-strong px-1.5 text-xs text-fg/70 hover:text-fg"
        onClick={() => onAjustar(indice, evento.duracao_s + PASSO_S)}
      >
        +
      </button>
    </div>
  );
}

export default function RelogioHoraEditor({ valor, presets, onChange, janelaSegundos, semFonteNoticia }: Props) {
  const [erro, setErro] = useState("");

  function escolher(id: string) {
    setErro("");
    if (!id) {
      onChange(null);
      return;
    }
    const preset = presets.find((p) => p.id === id);
    if (preset) onChange({ ...(JSON.parse(JSON.stringify(preset.relogio)) as RelogioHora), em_feriado: valor?.em_feriado ?? preset.relogio.em_feriado });
  }

  function ajustar(indice: number, segundos: number) {
    if (!valor) return;
    const resultado = ajustarDuracao(valor, indice, segundos);
    if (resultado.erro) {
      setErro(resultado.erro);
      return;
    }
    setErro("");
    if (resultado.relogio) onChange(resultado.relogio);
  }

  const soma = valor ? totais(valor.eventos) : null;
  const selecionado = valor ? valor.preset ?? "personalizado" : "";

  return (
    <div>
      <label htmlFor="relogio-hora" className={labelClass}>Relógio da hora</label>
      <select id="relogio-hora" className={inputClass} value={selecionado} onChange={(e) => escolher(e.target.value)}>
        <option value="">Sem relógio (segue a sequência de blocos)</option>
        {presets.map((p) => (
          <option key={p.id} value={p.id}>{`${p.id}: ${p.nome}`}</option>
        ))}
        {valor && !valor.preset && <option value="personalizado">Personalizado</option>}
      </select>
      {!valor && (
        <p className="mt-1 text-xs text-fg/65">
          Sem relógio, o ao vivo segue a sequência de blocos abaixo, em loop, até perto do fim do programa.
        </p>
      )}
      {valor && soma && (
        <div className="mt-3 space-y-3">
          <ul className="space-y-1 text-xs text-fg/65">
            <li>
              Com relógio, a sequência deixa de rodar em loop: a ordem vem do horário. Vinhetas de abertura e
              de passagem do programa e os patrocinadores da sequência entram nas etapas; blocos extras da IA
              e vinhetas sem papel não tocam.
            </li>
            {janelaSegundos !== undefined && janelaSegundos % 3600 !== 0 && (
              <li>
                A janela do programa não é um número inteiro de horas: a última hora é cortada e o
                encerramento entra nos segundos finais.
              </li>
            )}
            {valor.preset === "B" && semFonteNoticia && (
              <li>Sem fontes de notícia configuradas, as etapas de notícia viram música até haver fontes.</li>
            )}
            <li>Os tempos são hipóteses de partida; ajuste à sua operação.</li>
          </ul>
          <div className="overflow-x-auto rounded-xl border border-border-strong">
            <table className="w-full text-xs">
              <thead className="text-left text-fg/65">
                <tr>
                  <th className="px-2 py-1.5 font-medium">Início</th>
                  <th className="px-2 py-1.5 font-medium">Etapa</th>
                  <th className="px-2 py-1.5 font-medium">Duração</th>
                  <th className="px-2 py-1.5 font-medium">Natureza</th>
                </tr>
              </thead>
              <tbody>
                {valor.eventos.map((evento, indice) => (
                  <tr key={`${evento.inicio_s}-${indice}`} className="border-t border-border">
                    <td className="px-2 py-1.5 font-mono text-fg/70">{formatarMinSeg(evento.inicio_s)}</td>
                    <td className="px-2 py-1.5 text-fg">{evento.rotulo || evento.tipo}</td>
                    <td className="px-2 py-1.5">
                      <CampoDuracao evento={evento} indice={indice} onAjustar={ajustar} />
                    </td>
                    <td className="px-2 py-1.5">
                      <span className="rounded-full bg-fg/5 px-2 py-0.5 text-fg/70">{NATUREZA_LABEL[evento.natureza]}</span>
                      {evento.hard_time && (
                        <span className="ml-1 rounded-full bg-acento/10 px-2 py-0.5 text-acento-claro">horário fixo</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-fg/70" data-testid="relogio-total">
            {`Total: ${formatarMinSeg(soma.total_s)} — música ${formatarMinSeg(soma.musica_s)}, fala ${formatarMinSeg(soma.fala_s)}, intervalos ${formatarMinSeg(soma.intervalo_s)}`}
          </p>
          {erro && <p role="alert" className="text-xs text-laranja">{erro}</p>}
          <div>
            <label htmlFor="relogio-feriado" className={labelClass}>Em feriados</label>
            <select
              id="relogio-feriado"
              className={inputClass}
              value={valor.em_feriado}
              onChange={(e) => onChange({ ...valor, em_feriado: e.target.value as RelogioHora["em_feriado"] })}
            >
              {(Object.keys(FERIADO_LABEL) as RelogioHora["em_feriado"][]).map((chave) => (
                <option key={chave} value={chave}>{FERIADO_LABEL[chave]}</option>
              ))}
            </select>
          </div>
        </div>
      )}
    </div>
  );
}
