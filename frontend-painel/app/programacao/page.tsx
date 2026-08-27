"use client";

import { useEffect, useState } from "react";
import AppShell from "../../components/AppShell";
import Modal from "../../components/Modal";
import EditarProgramaForm from "../../components/EditarProgramaForm";
import GradeSemanalView, { ProgramaComRadialista } from "../../components/programacao/GradeSemanalView";
import { apiFetch, ApiError } from "../../lib/api";
import { corPorIndice } from "../../lib/gradeSemanal";
import { DIAS_SEMANA_LABEL, Programa, Radialista } from "../../lib/types";
import { LocufySpin } from "../../components/LocufyLogo";

function horarioMaisUmaHora(horario: string): string {
  const [h, m] = horario.split(":").map(Number);
  const total = (h * 60 + m + 60) % MINUTOS_DIA;
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}:00`;
}

const MINUTOS_DIA = 1440;

type ModalEdicao = { radialistaId: number; programaId: number | null; valoresIniciais?: Partial<Programa> };

export default function ProgramacaoPage() {
  const [radialistas, setRadialistas] = useState<Radialista[]>([]);
  const [programas, setProgramas] = useState<ProgramaComRadialista[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");
  const [modal, setModal] = useState<ModalEdicao | null>(null);
  const [escolhaPendente, setEscolhaPendente] = useState<{ dia: number; horario: string } | null>(null);

  function carregar() {
    setCarregando(true);
    setErro("");
    apiFetch<Radialista[]>("/config/radialistas")
      .then(async (lista) => {
        setRadialistas(lista);
        const entradas = await Promise.all(
          lista.map(async (r) => {
            try {
              const progs = await apiFetch<Programa[]>(`/config/radialistas/${r.id}/programas`);
              return progs.map((p) => ({ ...p, radialista: r }));
            } catch {
              return [];
            }
          })
        );
        setProgramas(entradas.flat());
      })
      .catch((err) => setErro(err instanceof ApiError ? err.message : "Erro ao carregar programação"))
      .finally(() => setCarregando(false));
  }

  useEffect(() => {
    carregar();
  }, []);

  const radialistasOrdenados = [...radialistas].sort((a, b) => a.id - b.id);

  function abrirCriacao(radialistaId: number, dia: number, horario: string) {
    setModal({
      radialistaId,
      programaId: null,
      valoresIniciais: { dias_semana: [dia], horario_inicio: horario, horario_fim: horarioMaisUmaHora(horario) },
    });
  }

  function aoClicarSlotVazio(dia: number, horario: string) {
    if (radialistas.length === 0) return;
    if (radialistas.length === 1) {
      abrirCriacao(radialistas[0].id, dia, horario);
    } else {
      setEscolhaPendente({ dia, horario });
    }
  }

  function aoClicarPrograma(programa: ProgramaComRadialista) {
    setModal({ radialistaId: programa.radialista.id, programaId: programa.id });
  }

  return (
    <AppShell title="Grade de Programação" maxWidthClassName="max-w-[1100px]">
      <div className="flex items-start justify-between gap-4 mb-5">
        <p className="text-sm text-fg/65">
          Todos os programas de todos os radialistas, por dia e horário. Clique num programa pra editar, ou num
          espaço vazio pra criar um novo ali.
        </p>
      </div>

      {erro && <p className="text-sm text-rust-text mb-4">{erro}</p>}

      {radialistasOrdenados.length > 0 && (
        <div className="flex flex-wrap gap-3 mb-4">
          {radialistasOrdenados.map((r, i) => {
            const cor = corPorIndice(i);
            return (
              <span key={r.id} className={`inline-flex items-center gap-1.5 text-xs font-medium ${cor.texto}`}>
                <span className={`h-2.5 w-2.5 rounded-full ${cor.fundo} border ${cor.borda}`} />
                {r.nome_locutor || `Radialista #${r.id}`}
              </span>
            );
          })}
        </div>
      )}

      {carregando ? (
        <p className="flex items-center gap-2 text-sm text-fg/65">
          <LocufySpin size={16} /> Carregando...
        </p>
      ) : radialistas.length === 0 ? (
        <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6">
          <p className="text-sm text-fg/65">Crie um radialista primeiro para poder montar a programação.</p>
        </div>
      ) : (
        <GradeSemanalView
          programas={programas}
          radialistasOrdenados={radialistasOrdenados}
          onClickPrograma={aoClicarPrograma}
          onClickSlotVazio={aoClicarSlotVazio}
        />
      )}

      {escolhaPendente && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/50 px-4"
          onClick={() => setEscolhaPendente(null)}
        >
          <div
            className="w-full max-w-sm rounded-2xl border border-border-strong bg-surface p-6 shadow-theme-xs"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="font-display text-base font-bold text-fg mb-1">Para qual radialista?</h2>
            <p className="text-xs text-fg/65 mb-4">
              {DIAS_SEMANA_LABEL[escolhaPendente.dia]} às {escolhaPendente.horario.slice(0, 5)}
            </p>
            <div className="space-y-2">
              {radialistasOrdenados.map((r) => (
                <button
                  key={r.id}
                  type="button"
                  onClick={() => {
                    abrirCriacao(r.id, escolhaPendente.dia, escolhaPendente.horario);
                    setEscolhaPendente(null);
                  }}
                  className="w-full text-left rounded-lg border border-border-strong px-3 py-2.5 text-sm font-medium text-fg hover:border-amber/40"
                >
                  {r.nome_locutor || `Radialista #${r.id}`}
                </button>
              ))}
            </div>
            <div className="flex justify-end mt-4">
              <button
                type="button"
                onClick={() => setEscolhaPendente(null)}
                className="rounded-lg px-4 py-2.5 text-sm font-medium text-fg/60 hover:text-fg"
              >
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}

      <Modal
        open={modal !== null}
        onClose={() => setModal(null)}
        title={modal?.programaId === null ? "Novo programa" : "Editar programa"}
        maxWidthClassName="max-w-4xl"
      >
        {modal !== null && (
          <EditarProgramaForm
            programaId={modal.programaId}
            radioConfigId={modal.radialistaId}
            valoresIniciais={modal.valoresIniciais}
            onSalvo={() => {
              carregar();
            }}
            onExcluido={() => {
              setModal(null);
              carregar();
            }}
          />
        )}
      </Modal>
    </AppShell>
  );
}
