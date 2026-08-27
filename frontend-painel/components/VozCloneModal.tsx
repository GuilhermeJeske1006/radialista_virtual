"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { apiFetchForm, ApiError } from "../lib/api";
import { VozClonada } from "../lib/types";

type Props = {
  onCriada: (voz: VozClonada) => void;
  onFechar: () => void;
};

export default function VozCloneModal({ onCriada, onFechar }: Props) {
  const [nome, setNome] = useState("");
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [gravando, setGravando] = useState(false);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState("");

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach((t) => t.stop());
      if (audioUrl) URL.revokeObjectURL(audioUrl);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function iniciarGravacao() {
    setErro("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];
      const recorder = new MediaRecorder(stream);
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        setAudioBlob(blob);
        setArquivo(null);
        setAudioUrl((atual) => {
          if (atual) URL.revokeObjectURL(atual);
          return URL.createObjectURL(blob);
        });
        stream.getTracks().forEach((t) => t.stop());
      };
      mediaRecorderRef.current = recorder;
      recorder.start();
      setGravando(true);
    } catch {
      setErro("Nao foi possivel acessar o microfone. Verifique a permissao do navegador.");
    }
  }

  function pararGravacao() {
    mediaRecorderRef.current?.stop();
    setGravando(false);
  }

  function selecionarArquivo(arquivoSelecionado: File | null) {
    setArquivo(arquivoSelecionado);
    setAudioBlob(null);
    setAudioUrl((atual) => {
      if (atual) URL.revokeObjectURL(atual);
      return arquivoSelecionado ? URL.createObjectURL(arquivoSelecionado) : null;
    });
  }

  async function enviar() {
    if (!nome.trim() || (!arquivo && !audioBlob)) return;
    setEnviando(true);
    setErro("");
    try {
      const dados = new FormData();
      dados.set("nome", nome.trim());
      dados.set("arquivo", arquivo ?? new File([audioBlob as Blob], "gravacao.webm", { type: "audio/webm" }));
      const criada = await apiFetchForm<VozClonada>("/tts/vozes-clonadas", dados, "POST");
      onCriada(criada);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao clonar voz");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/50 px-4" onClick={onFechar}>
      <div
        className="w-full max-w-md rounded-2xl border border-border-strong bg-surface p-6 shadow-theme-xs"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="font-display text-base font-bold text-fg mb-2">Clonar voz</h2>
        <p className="text-sm text-fg/70 mb-4">
          Grave (ou envie) uns 60 segundos de fala limpa, sem musica nem ruido de fundo. A voz clonada fica
          disponivel so pra sua conta.
        </p>

        <div className="mb-4">
          <label className="block text-sm font-medium text-fg/80 mb-1.5">Nome da voz</label>
          <input
            className="w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg placeholder:text-fg/65 focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
            value={nome}
            onChange={(e) => setNome(e.target.value)}
            placeholder="Ex: Voz do Zé"
            disabled={enviando}
          />
        </div>

        <div className="mb-4 space-y-3">
          <div className="flex items-center gap-3">
            {!gravando ? (
              <button
                type="button"
                onClick={iniciarGravacao}
                disabled={enviando}
                className="rounded-lg border border-border-strong px-3 py-2 text-sm font-medium text-fg hover:border-amber/50 disabled:opacity-60"
              >
                🎙️ Gravar
              </button>
            ) : (
              <button
                type="button"
                onClick={pararGravacao}
                className="rounded-lg bg-rust px-3 py-2 text-sm font-medium text-white animate-pulse"
              >
                ⏹ Parar
              </button>
            )}
            <span className="text-sm text-fg/65">ou</span>
            <label className="rounded-lg border border-border-strong px-3 py-2 text-sm font-medium text-fg hover:border-amber/50 cursor-pointer">
              Enviar arquivo
              <input
                type="file"
                accept="audio/*"
                className="hidden"
                disabled={enviando}
                onChange={(e) => selecionarArquivo(e.target.files?.[0] ?? null)}
              />
            </label>
          </div>

          {arquivo && <p className="text-xs text-fg/65">Arquivo: {arquivo.name}</p>}
          {audioUrl && (
            <audio controls src={audioUrl} className="w-full h-9">
              Seu navegador nao suporta audio.
            </audio>
          )}
        </div>

        {erro && <p className="text-sm text-rust-text mb-3">{erro}</p>}

        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={onFechar}
            disabled={enviando}
            className="rounded-lg px-4 py-2.5 text-sm font-medium text-fg/60 hover:text-fg disabled:opacity-60"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={enviar}
            disabled={enviando || !nome.trim() || (!arquivo && !audioBlob)}
            className="rounded-lg bg-amber px-4 py-2.5 text-sm font-medium text-ink hover:bg-amber/90 disabled:opacity-60"
          >
            {enviando ? "Clonando..." : "Clonar voz"}
          </button>
        </div>

        <p className="text-xs text-fg/65 mt-3">
          Recurso do plano Growth em diante.{" "}
          <Link href="/billing" className="text-amber-text hover:underline">
            Ver planos
          </Link>
        </p>
      </div>
    </div>
  );
}
