"use client";

import { useEffect, useRef, useState } from "react";
import ConfirmDialog from "./ConfirmDialog";
import { apiFetch, apiFetchBlob, apiFetchForm, ApiError } from "../lib/api";
import { formatarDuracao, OrigemTrilha, PapelVinheta, Vinheta } from "../lib/bibliotecaAudio";
import { LocufySpin } from "./LocufyLogo";

const PAPEL_LABEL: Record<PapelVinheta, string> = {
  abertura: "Abertura",
  passagem: "Passagem",
  encerramento: "Encerramento",
};

const PAPEL_DICA: Record<PapelVinheta, string> = {
  abertura: "Toca no início do roteiro e a cada volta dele.",
  passagem: "Identificação curta no meio do roteiro.",
  encerramento: "Toca logo depois da fala de encerramento.",
};

const TRILHA_LABEL: Record<OrigemTrilha, string> = {
  ia: "Trilha gerada por IA",
  banco: "Trilha do banco",
  upload: "Trilha própria",
};

const INTERVALO_POLLING_MS = 3000;

const botaoSecundario =
  "rounded-xl border border-border-strong px-3 py-1.5 text-xs font-medium text-fg/80 hover:bg-fg/5 disabled:opacity-60";

// Flag gravada por quem acabou de criar o programa (ver marcarVinhetasCriadas), lida uma vez so'
// aqui pra mostrar o aviso -- sessionStorage pode nao existir (aba privada, preview), dai' so'
// nao mostra o aviso.
const CHAVE_AVISO = (programaId: number) => `locufy:vinhetas-criadas:${programaId}`;

export function marcarVinhetasCriadas(programaId: number) {
  try {
    window.sessionStorage.setItem(CHAVE_AVISO(programaId), "1");
  } catch {
    // sem storage: o aviso so' nao aparece
  }
}

function consumirAvisoVinhetas(programaId: number): boolean {
  try {
    const marcado = window.sessionStorage.getItem(CHAVE_AVISO(programaId)) === "1";
    window.sessionStorage.removeItem(CHAVE_AVISO(programaId));
    return marcado;
  } catch {
    return false;
  }
}

type Props = {
  programaId: number;
  /** Chamado quando a estrutura_blocos do programa mudou no backend (regerar/recolocar). */
  onEstruturaMudou?: () => void;
};

// Vinhetas geradas automaticamente pro programa (abertura, passagem, encerramento) -- voz sobre
// trilha, mixadas no backend (ver backend app/vinhetas/). Status "pendente"/"gerando" = o job de
// audio ainda esta rodando: polling ate' todas saírem desse estado.
export default function VinhetasProgramaSection({ programaId, onEstruturaMudou }: Props) {
  const [vinhetas, setVinhetas] = useState<Vinheta[] | null>(null);
  const [erro, setErro] = useState("");
  const [aviso, setAviso] = useState(false);
  const [ocupado, setOcupado] = useState<string | null>(null);
  const [tocandoId, setTocandoId] = useState<number | null>(null);
  const [textos, setTextos] = useState<Record<number, string>>({});
  const [volumes, setVolumes] = useState<Record<number, number>>({});
  const [bancoDisponivel, setBancoDisponivel] = useState(false);
  const [confirmandoRegerar, setConfirmandoRegerar] = useState(false);
  const [confirmandoUpload, setConfirmandoUpload] = useState(false);
  const inputUploadRef = useRef<HTMLInputElement | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  function aplicar(lista: Vinheta[]) {
    setVinhetas(lista);
    setTextos((atual) => {
      const novo = { ...atual };
      for (const v of lista) if (novo[v.id] === undefined) novo[v.id] = v.texto ?? "";
      return novo;
    });
    setVolumes((atual) => {
      const novo = { ...atual };
      for (const v of lista) if (novo[v.id] === undefined) novo[v.id] = v.volume_trilha_db;
      return novo;
    });
  }

  function carregar() {
    return apiFetch<Vinheta[]>(`/vinhetas?programa_id=${programaId}`)
      .then((lista) => aplicar(lista.filter((v) => v.origem === "auto")))
      .catch((err) => setErro(err instanceof ApiError ? err.message : "Erro ao carregar vinhetas"));
  }

  useEffect(() => {
    setAviso(consumirAvisoVinhetas(programaId));
    carregar();
    apiFetch<Record<string, number>>("/trilhas/estilos")
      .then((estilos) => setBancoDisponivel(Object.values(estilos).some((n) => n > 0)))
      .catch(() => setBancoDisponivel(false));
    return () => audioRef.current?.pause();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [programaId]);

  const processando = (vinhetas ?? []).some((v) => v.status === "pendente" || v.status === "gerando");

  useEffect(() => {
    if (!processando) return;
    const id = window.setInterval(carregar, INTERVALO_POLLING_MS);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [processando, programaId]);

  function substituir(atualizada: Vinheta) {
    setVinhetas((atual) => (atual ?? []).map((v) => (v.id === atualizada.id ? atualizada : v)));
  }

  async function executar(chave: string, acao: () => Promise<void>) {
    setOcupado(chave);
    setErro("");
    try {
      await acao();
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Não foi possível concluir agora");
    } finally {
      setOcupado(null);
    }
  }

  async function tocar(vinheta: Vinheta) {
    if (tocandoId === vinheta.id) {
      audioRef.current?.pause();
      setTocandoId(null);
      return;
    }
    await executar(`tocar-${vinheta.id}`, async () => {
      audioRef.current?.pause();
      const blob = await apiFetchBlob(`/vinhetas/${vinheta.id}/audio`);
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onended = () => {
        setTocandoId((atual) => (atual === vinheta.id ? null : atual));
        URL.revokeObjectURL(url);
      };
      setTocandoId(vinheta.id);
      await audio.play();
    });
  }

  function salvarTexto(vinheta: Vinheta) {
    return executar(`texto-${vinheta.id}`, async () => {
      substituir(
        await apiFetch<Vinheta>(`/vinhetas/${vinheta.id}`, {
          method: "PUT",
          body: JSON.stringify({ texto: textos[vinheta.id] ?? "" }),
        })
      );
    });
  }

  function remixar(vinheta: Vinheta, corpo: { volume_trilha_db?: number; usar_trilha?: boolean }) {
    return executar(`remix-${vinheta.id}`, async () => {
      substituir(
        await apiFetch<Vinheta>(`/vinhetas/${vinheta.id}/remixar`, { method: "POST", body: JSON.stringify(corpo) })
      );
    });
  }

  function acaoPrograma(chave: string, caminho: string, corpo?: object) {
    return executar(chave, async () => {
      aplicar(
        await apiFetch<Vinheta[]>(caminho, { method: "POST", body: corpo ? JSON.stringify(corpo) : undefined })
      );
    });
  }

  function regerar() {
    setConfirmandoRegerar(false);
    return executar("regerar", async () => {
      const novas = await apiFetch<Vinheta[]>(`/programas/${programaId}/vinhetas/regerar`, { method: "POST" });
      setTextos({});
      setVolumes({});
      aplicar(novas);
      onEstruturaMudou?.();
    });
  }

  function recolocarNaProgramacao() {
    return executar("inserir", async () => {
      await apiFetch<string[]>(`/programas/${programaId}/vinhetas/inserir`, { method: "POST" });
      onEstruturaMudou?.();
    });
  }

  function enviarTrilha(arquivo: File) {
    return executar("upload", async () => {
      const dados = new FormData();
      dados.append("arquivo", arquivo);
      aplicar(await apiFetchForm<Vinheta[]>(`/programas/${programaId}/trilha/upload`, dados));
    });
  }

  if (vinhetas === null) {
    return (
      <p className="flex items-center gap-2 text-sm text-fg/65">
        <LocufySpin size={16} /> Carregando vinhetas...
      </p>
    );
  }

  const origemTrilha = vinhetas.find((v) => v.trilha_origem)?.trilha_origem ?? null;

  return (
    <div className="space-y-4">
      {aviso && (
        <p className="rounded-xl border border-ciano/30 bg-ciano/10 px-3 py-2 text-sm text-ciano">
          Criamos 3 vinhetas com trilha para este programa e colocamos na programação.
        </p>
      )}

      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-fg/65">
          Voz do radialista sobre uma trilha instrumental, mixada e masterizada. Enquanto uma vinheta não fica
          pronta, o ao vivo fala o texto dela na hora, sem trilha.
        </p>
        {origemTrilha && (
          <span className="rounded-full border border-border-strong px-2 py-0.5 text-[10px] uppercase tracking-wide text-fg/60">
            {TRILHA_LABEL[origemTrilha]}
          </span>
        )}
      </div>

      {erro && <p className="text-sm text-laranja">{erro}</p>}

      {vinhetas.length === 0 && (
        <p className="text-sm text-fg/65">Este programa ainda não tem vinhetas geradas.</p>
      )}

      <div className="space-y-3">
        {vinhetas.map((v) => {
          const papel = v.papel ?? "passagem";
          const emAndamento = v.status === "pendente" || v.status === "gerando";
          const textoAlterado = (textos[v.id] ?? "") !== (v.texto ?? "");
          return (
            <div key={v.id} className="rounded-xl border border-border-strong p-3 space-y-2" data-testid={`vinheta-${v.id}`}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="min-w-0">
                  <span className="text-sm font-medium text-fg">{PAPEL_LABEL[papel]}</span>
                  <span className="ml-2 text-xs text-fg/50">{PAPEL_DICA[papel]}</span>
                </div>
                {emAndamento ? (
                  <span className="flex items-center gap-1.5 text-xs text-fg/65">
                    <LocufySpin size={14} /> Gerando trilha e mixando...
                  </span>
                ) : v.tem_audio ? (
                  <button
                    type="button"
                    onClick={() => tocar(v)}
                    disabled={ocupado === `tocar-${v.id}`}
                    className={botaoSecundario}
                  >
                    {tocandoId === v.id ? "Parar" : `Ouvir (${formatarDuracao(v.duracao_segundos)})`}
                  </button>
                ) : null}
              </div>

              {v.status === "erro" && v.erro_msg && <p className="text-xs text-laranja">{v.erro_msg}</p>}

              <textarea
                className="w-full rounded-xl border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-acento-claro/50"
                rows={2}
                maxLength={300}
                value={textos[v.id] ?? ""}
                onChange={(e) => setTextos({ ...textos, [v.id]: e.target.value })}
                aria-label={`Texto da vinheta de ${PAPEL_LABEL[papel].toLowerCase()}`}
              />
              {textoAlterado && (
                <button
                  type="button"
                  onClick={() => salvarTexto(v)}
                  disabled={ocupado === `texto-${v.id}` || !(textos[v.id] ?? "").trim()}
                  className="text-xs font-medium text-acento-claro hover:text-acento-dim disabled:opacity-60"
                >
                  Salvar texto e gerar a voz de novo
                </button>
              )}

              <div className="flex flex-wrap items-center gap-4 pt-1">
                <label className="inline-flex items-center gap-2 text-xs text-fg/80">
                  <input
                    type="checkbox"
                    checked={v.usar_trilha}
                    disabled={emAndamento || !v.tem_audio || ocupado === `remix-${v.id}`}
                    onChange={(e) => remixar(v, { usar_trilha: e.target.checked })}
                    className="h-4 w-4 rounded border-border-strong bg-bg text-acento-claro"
                  />
                  Usar trilha
                </label>
                <label className="flex flex-1 min-w-[12rem] items-center gap-2 text-xs text-fg/80">
                  Volume da trilha
                  <input
                    type="range"
                    min={-24}
                    max={-6}
                    step={1}
                    value={volumes[v.id] ?? v.volume_trilha_db}
                    disabled={emAndamento || !v.tem_audio || !v.usar_trilha || ocupado === `remix-${v.id}`}
                    onChange={(e) => setVolumes({ ...volumes, [v.id]: Number(e.target.value) })}
                    onPointerUp={() => {
                      if (volumes[v.id] !== undefined && volumes[v.id] !== v.volume_trilha_db) {
                        remixar(v, { volume_trilha_db: volumes[v.id] });
                      }
                    }}
                    onKeyUp={() => {
                      if (volumes[v.id] !== undefined && volumes[v.id] !== v.volume_trilha_db) {
                        remixar(v, { volume_trilha_db: volumes[v.id] });
                      }
                    }}
                    className="flex-1 accent-acento-claro"
                  />
                  <span className="w-12 text-right tabular-nums">{volumes[v.id] ?? v.volume_trilha_db} dB</span>
                </label>
                {ocupado === `remix-${v.id}` && (
                  <span className="flex items-center gap-1.5 text-xs text-fg/65">
                    <LocufySpin size={14} /> Remixando...
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={() => setConfirmandoRegerar(true)} disabled={!!ocupado} className={botaoSecundario}>
          Gerar de novo
        </button>
        {vinhetas.length > 0 && (
          <>
            <button
              type="button"
              onClick={() => acaoPrograma("trilha-ia", `/programas/${programaId}/trilha/gerar`)}
              disabled={!!ocupado || processando}
              className={botaoSecundario}
            >
              Gerar outra trilha
            </button>
            <button
              type="button"
              onClick={() => acaoPrograma("trilha-banco", `/programas/${programaId}/trilha/banco`, {})}
              disabled={!!ocupado || processando || !bancoDisponivel}
              title={bancoDisponivel ? undefined : "O banco de trilhas ainda está vazio"}
              className={botaoSecundario}
            >
              Escolher do banco
            </button>
            <button
              type="button"
              onClick={() => setConfirmandoUpload(true)}
              disabled={!!ocupado || processando}
              className={botaoSecundario}
            >
              Enviar trilha própria
            </button>
            <button type="button" onClick={recolocarNaProgramacao} disabled={!!ocupado} className={botaoSecundario}>
              Colocar na programação
            </button>
          </>
        )}
        {(ocupado === "trilha-banco" || ocupado === "upload" || ocupado === "regerar") && (
          <span className="flex items-center gap-1.5 text-xs text-fg/65">
            <LocufySpin size={14} /> Aguarde...
          </span>
        )}
      </div>

      <input
        ref={inputUploadRef}
        type="file"
        accept=".mp3,.wav,audio/mpeg,audio/wav"
        className="hidden"
        onChange={(e) => {
          const arquivo = e.target.files?.[0];
          e.target.value = "";
          if (arquivo) enviarTrilha(arquivo);
        }}
      />

      <ConfirmDialog
        open={confirmandoRegerar}
        title="Gerar as vinhetas de novo?"
        mensagem="O texto das 3 vinhetas é reescrito e a voz é gerada de novo. A trilha atual é mantida."
        confirmarLabel="Gerar de novo"
        onConfirmar={regerar}
        onCancelar={() => setConfirmandoRegerar(false)}
      />
      <ConfirmDialog
        open={confirmandoUpload}
        title="Enviar trilha própria"
        mensagem="MP3 ou WAV de até 15 MB. Você é responsável por ter o direito de uso dessa trilha na rádio."
        confirmarLabel="Escolher arquivo"
        onConfirmar={() => {
          setConfirmandoUpload(false);
          inputUploadRef.current?.click();
        }}
        onCancelar={() => setConfirmandoUpload(false)}
      />
    </div>
  );
}
