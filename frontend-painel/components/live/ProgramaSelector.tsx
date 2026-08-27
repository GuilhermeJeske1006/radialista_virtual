"use client";

import { Radialista, DIAS_SEMANA_LABEL } from "../../lib/types";
import { ProgramaOpcao } from "../../lib/liveTypes";

function formatarDiasSemana(dias: number[], dataEspecifica?: string | null): string {
  if (dataEspecifica) return `Avulso em ${dataEspecifica.split("-").reverse().join("/")}`;
  if (dias.length === 0) return "Todos os dias";
  return dias
    .slice()
    .sort((a, b) => a - b)
    .map((d) => DIAS_SEMANA_LABEL[d])
    .join(", ");
}

function formatarFaixaHorario(p: { horario_inicio: string; horario_fim: string }): string {
  return `${p.horario_inicio.slice(0, 5)}-${p.horario_fim.slice(0, 5)}`;
}

type Props = {
  radialistas: Radialista[];
  programasTodos: ProgramaOpcao[];
  carregandoProgramas: boolean;
  programaId: number | null;
  programaAtivo: boolean;
  gerandoFala: boolean;
  aoVivoAtivo: boolean;
  programaSelecionado: ProgramaOpcao | null;
  radialistaSelecionado: Radialista | null;
  programaSelecionadoNoAr: boolean;
  onSelecionar: (opcao: ProgramaOpcao) => void;
  onIniciar: () => void;
  onPausar: () => void;
  onEditarRadialista: (radialistaId: number) => void;
  onEditarPrograma: (radialistaId: number, programaId: number) => void;
};

export default function ProgramaSelector({
  radialistas,
  programasTodos,
  carregandoProgramas,
  programaId,
  programaAtivo,
  gerandoFala,
  aoVivoAtivo,
  programaSelecionado,
  radialistaSelecionado,
  programaSelecionadoNoAr,
  onSelecionar,
  onIniciar,
  onPausar,
  onEditarRadialista,
  onEditarPrograma,
}: Props) {
  const iniciais = (programaSelecionado?.radialistaNome || "?")
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0])
    .join("")
    .toUpperCase();

  return (
    <section className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-5">
        <div className="flex min-w-0 flex-1 gap-3.5">
          {programaSelecionado && (
            <div className="hidden sm:flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-linear-to-br from-amber to-rust font-display text-base font-bold text-ink">
              {iniciais}
            </div>
          )}
          <div className="min-w-0 flex-1">
            <p className="font-mono text-[10.5px] font-semibold uppercase tracking-wide text-fg/65">
              Programa selecionado
            </p>
            <h2 className="font-display text-lg font-bold text-fg truncate mt-0.5">
              {programaSelecionado ? programaSelecionado.nome : "Nenhum programa selecionado"}
            </h2>
            {programaSelecionado && (
              <p className="text-xs text-fg/65 mt-0.5">
                {programaSelecionado.radialistaNome} · {formatarFaixaHorario(programaSelecionado)}
              </p>
            )}

            <div className="mt-3.5 flex flex-col gap-2 sm:flex-row sm:items-center">
              <select
                aria-label="Selecionar programa"
                className="w-full sm:max-w-sm rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
                value={programaId ?? ""}
                disabled={carregandoProgramas || programaAtivo}
                onChange={(e) => {
                  const valor = e.target.value ? Number(e.target.value) : null;
                  const opcao = programasTodos.find((p) => p.id === valor);
                  if (opcao) onSelecionar(opcao);
                }}
              >
                <option value="">
                  {carregandoProgramas
                    ? "Carregando programas..."
                    : programasTodos.length === 0
                      ? "Nenhum programa cadastrado"
                      : "Selecione um programa"}
                </option>
                {radialistas.map((r) => {
                  const doRadialista = programasTodos.filter((p) => p.radialistaId === r.id);
                  if (doRadialista.length === 0) return null;
                  return (
                    <optgroup key={r.id} label={r.nome_locutor || `Radialista #${r.id}`}>
                      {doRadialista.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.nome} · {formatarFaixaHorario(p)}
                        </option>
                      ))}
                    </optgroup>
                  );
                })}
              </select>

              {!programaAtivo ? (
                <button
                  type="button"
                  onClick={onIniciar}
                  disabled={!programaId || gerandoFala}
                  className="rounded-lg bg-rust px-4 py-2.5 text-sm font-medium text-fg hover:bg-rust/90 disabled:opacity-60 disabled:cursor-not-allowed shrink-0"
                >
                  Comecar transmissao
                </button>
              ) : (
                <button
                  type="button"
                  onClick={onPausar}
                  className="rounded-lg border border-border-strong bg-paper/5 px-4 py-2.5 text-sm font-medium text-fg hover:bg-paper/10 shrink-0"
                >
                  Pausar transmissao
                </button>
              )}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto shrink-0">
          <span
            className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${
              aoVivoAtivo ? "bg-teal/10 text-teal-text" : "bg-amber/10 text-amber-text"
            }`}
          >
            {aoVivoAtivo ? "Agente online" : "Aguardando conexao"}
          </span>
          {programaSelecionado && (
            <span
              className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                programaSelecionadoNoAr ? "bg-teal/10 text-teal-text" : "bg-amber/10 text-amber-text"
              }`}
            >
              {programaSelecionadoNoAr ? "No ar agora" : "Fora do horario"}
            </span>
          )}
        </div>
      </div>

      {programaSelecionado && (
        <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border pt-4">
          <span className="rounded-full bg-paper/5 px-2.5 py-1 font-mono text-xs font-medium text-fg/70">
            Voz: {radialistaSelecionado?.voz_id ? "Personalizada" : "Padrao do servidor"}
          </span>
          <span className="rounded-full bg-paper/5 px-2.5 py-1 font-mono text-xs font-medium text-fg/70">
            Generos:{" "}
            {programaSelecionado.generos_musicais.length > 0
              ? programaSelecionado.generos_musicais.slice(0, 3).join(", ")
              : "livre"}
            {programaSelecionado.generos_musicais.length > 3
              ? ` +${programaSelecionado.generos_musicais.length - 3}`
              : ""}
          </span>
          <span className="rounded-full bg-paper/5 px-2.5 py-1 font-mono text-xs font-medium text-fg/70">
            Dias: {formatarDiasSemana(programaSelecionado.dias_semana, programaSelecionado.data_especifica)}
          </span>

          <div className="ml-auto flex gap-2">
            <button
              type="button"
              onClick={() => onEditarRadialista(programaSelecionado.radialistaId)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-amber/25 bg-amber/10 px-3 py-1.5 text-xs font-semibold text-amber-text hover:bg-amber/20"
            >
              ✎ Editar radialista
            </button>
            <button
              type="button"
              onClick={() => onEditarPrograma(programaSelecionado.radialistaId, programaSelecionado.id)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-amber/25 bg-amber/10 px-3 py-1.5 text-xs font-semibold text-amber-text hover:bg-amber/20"
            >
              ✎ Editar programa
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
