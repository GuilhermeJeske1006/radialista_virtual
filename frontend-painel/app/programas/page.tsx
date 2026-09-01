"use client";

import { useEffect, useState } from "react";
import AppShell from "../../components/AppShell";
import ConfirmDialog from "../../components/ConfirmDialog";
import Modal from "../../components/Modal";
import EditarProgramaForm from "../../components/EditarProgramaForm";
import { apiFetch, ApiError } from "../../lib/api";
import { DIAS_SEMANA_LABEL, Programa, Radialista } from "../../lib/types";
import { LocufySpin } from "../../components/LocufyLogo";

type ProgramaComRadialista = Programa & { radialista: Radialista };
type ModalEdicao = { radialistaId: number; programaId: number | null };

function formatarDias(dias: number[], dataEspecifica?: string | null): string {
  if (dataEspecifica) return `Avulso em ${dataEspecifica.split("-").reverse().join("/")}`;
  if (dias.length === 0) return "Todos os dias";
  return dias.map((d) => DIAS_SEMANA_LABEL[d]).join(", ");
}

export default function ProgramasPage() {
  const [radialistas, setRadialistas] = useState<Radialista[]>([]);
  const [programas, setProgramas] = useState<ProgramaComRadialista[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [escolhendoRadialista, setEscolhendoRadialista] = useState(false);
  const [programaParaExcluir, setProgramaParaExcluir] = useState<ProgramaComRadialista | null>(null);
  const [erro, setErro] = useState("");
  const [modal, setModal] = useState<ModalEdicao | null>(null);

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
        const todos = entradas
          .flat()
          .sort((a, b) => a.horario_inicio.localeCompare(b.horario_inicio) || a.nome.localeCompare(b.nome));
        setProgramas(todos);
      })
      .catch((err) => setErro(err instanceof ApiError ? err.message : "Erro ao carregar programas"))
      .finally(() => setCarregando(false));
  }

  useEffect(() => {
    carregar();
  }, []);

  function aoClicarNovoPrograma() {
    if (radialistas.length === 0) return;
    if (radialistas.length === 1) {
      setModal({ radialistaId: radialistas[0].id, programaId: null });
    } else {
      setEscolhendoRadialista(true);
    }
  }

  async function excluirPrograma(programa: ProgramaComRadialista) {
    try {
      await apiFetch(`/config/programas/${programa.id}`, { method: "DELETE" });
      carregar();
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao excluir programa");
    } finally {
      setProgramaParaExcluir(null);
    }
  }

  return (
    <AppShell title="Programas" maxWidthClassName="max-w-4xl">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-5">
        <p className="text-sm text-fg/65">Todos os programas cadastrados, de todos os radialistas.</p>
        <button
          type="button"
          onClick={aoClicarNovoPrograma}
          disabled={radialistas.length === 0}
          className="shrink-0 self-start rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-ink hover:bg-brand-600 disabled:opacity-60 disabled:cursor-not-allowed whitespace-nowrap"
        >
          + Novo programa
        </button>
      </div>

      {erro && <p className="text-sm text-rust-text mb-4">{erro}</p>}

      {carregando ? (
        <p className="flex items-center gap-2 text-sm text-fg/65">
          <LocufySpin size={16} /> Carregando...
        </p>
      ) : programas.length === 0 ? (
        <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6">
          <p className="text-sm text-fg/65">
            {radialistas.length === 0
              ? "Crie um radialista primeiro para poder cadastrar programas."
              : "Nenhum programa cadastrado ainda."}
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {programas.map((p) => (
            <div
              key={p.id}
              className="flex flex-wrap items-center justify-between gap-2 bg-surface rounded-2xl border border-border-strong shadow-theme-xs px-4 py-3"
            >
              <button
                type="button"
                onClick={() => setModal({ radialistaId: p.radialista.id, programaId: p.id })}
                className="min-w-0 text-left"
              >
                <p className={`text-sm font-medium ${p.ativo ? "text-fg" : "text-fg/65"} hover:text-amber-text`}>
                  {p.nome}
                  {!p.ativo && <span className="ml-2 text-xs font-medium text-fg/65">(pausado)</span>}
                </p>
                <p className="text-xs text-fg/65 font-mono">
                  {p.radialista.nome_locutor || `Radialista #${p.radialista.id}`} · {formatarDias(p.dias_semana, p.data_especifica)} ·{" "}
                  {p.horario_inicio.slice(0, 5)} às {p.horario_fim.slice(0, 5)}
                </p>
              </button>
              <div className="flex items-center gap-3 shrink-0">
                <button
                  type="button"
                  onClick={() => setModal({ radialistaId: p.radialista.id, programaId: p.id })}
                  className="text-xs font-medium text-amber-text hover:text-amber-dim"
                >
                  Editar
                </button>
                <button
                  type="button"
                  onClick={() => setProgramaParaExcluir(p)}
                  className="text-xs font-medium text-rust-text hover:text-rust/80"
                >
                  Excluir
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {escolhendoRadialista && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/50 px-4"
          onClick={() => setEscolhendoRadialista(false)}
        >
          <div
            className="w-full max-w-sm rounded-2xl border border-border-strong bg-surface p-6 shadow-theme-xs"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="font-display text-base font-bold text-fg mb-4">Para qual radialista?</h2>
            <div className="space-y-2">
              {radialistas.map((r) => (
                <button
                  key={r.id}
                  type="button"
                  onClick={() => {
                    setEscolhendoRadialista(false);
                    setModal({ radialistaId: r.id, programaId: null });
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
                onClick={() => setEscolhendoRadialista(false)}
                className="rounded-lg px-4 py-2.5 text-sm font-medium text-fg/60 hover:text-fg"
              >
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={programaParaExcluir !== null}
        title="Excluir programa"
        mensagem={`Excluir o programa "${programaParaExcluir?.nome}"? Essa ação não pode ser desfeita.`}
        onConfirmar={() => programaParaExcluir && excluirPrograma(programaParaExcluir)}
        onCancelar={() => setProgramaParaExcluir(null)}
      />

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
            onSalvo={() => carregar()}
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
