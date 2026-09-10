"use client";

import { useEffect, useRef, useState } from "react";
import { apiFetchForm, ApiError } from "../lib/api";
import { QualidadeVoz, VozClonada } from "../lib/types";
import Modal from "./Modal";

type Props = { onCriada: (voz: VozClonada) => void; onFechar: () => void };

export function formatoGravacao(): MediaRecorderOptions {
  const mimeType = ["audio/webm;codecs=opus", "audio/mp4", "audio/ogg;codecs=opus"]
    .find((tipo) => MediaRecorder.isTypeSupported(tipo));
  return { ...(mimeType ? { mimeType } : {}), audioBitsPerSecond: 192000 };
}

export function arquivoGravado(blob: Blob): File {
  const tipo = blob.type.split(";")[0];
  const extensao = ({ "audio/mp4": "m4a", "audio/webm": "webm", "audio/ogg": "ogg", "audio/wav": "wav" } as Record<string, string>)[tipo];
  if (!extensao) throw new Error("Formato de gravação não suportado. Envie um arquivo MP3, WAV ou M4A.");
  return new File([blob], `gravacao.${extensao}`, { type: blob.type });
}

export default function VozCloneModal({ onCriada, onFechar }: Props) {
  const [nome, setNome] = useState("");
  const [arquivos, setArquivos] = useState<File[]>([]);
  const [previews, setPreviews] = useState<string[]>([]);
  const [gravando, setGravando] = useState(false);
  const [iniciando, setIniciando] = useState(false);
  const [ocupado, setOcupado] = useState<"analisando" | "clonando" | null>(null);
  const [segundos, setSegundos] = useState(0);
  const [nivel, setNivel] = useState(0);
  const [qualidade, setQualidade] = useState<QualidadeVoz | null>(null);
  const [erro, setErro] = useState("");
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const contextRef = useRef<AudioContext | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const montado = useRef(true);

  function liberarMicrofone() {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = null;
    if (contextRef.current) void contextRef.current.close().catch(() => {});
    contextRef.current = null;
  }

  useEffect(() => {
    montado.current = true;
    return () => {
      montado.current = false;
      if (recorderRef.current?.state === "recording") recorderRef.current.stop();
      liberarMicrofone();
    };
  }, []);

  useEffect(() => {
    const urls = arquivos.map((f) => URL.createObjectURL(f));
    setPreviews(urls);
    return () => urls.forEach((url) => URL.revokeObjectURL(url));
  }, [arquivos]);

  function selecionar(novos: File[]) {
    setQualidade(null); setErro("");
    if (novos.length > 5 || novos.reduce((s, f) => s + f.size, 0) > 15 * 1024 * 1024) {
      setArquivos([]); setErro("Selecione até 5 arquivos, somando no máximo 15 MB."); return;
    }
    setArquivos(novos);
  }

  async function iniciarGravacao() {
    setIniciando(true); setErro(""); setQualidade(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: {
        echoCancellation: false, noiseSuppression: false, autoGainControl: false,
      } });
      if (!montado.current) { stream.getTracks().forEach((t) => t.stop()); return; }
      streamRef.current = stream;
      const recorder = new MediaRecorder(stream, formatoGravacao());
      recorderRef.current = recorder;
      const chunks: Blob[] = [];
      let falhou = false;
      recorder.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
      recorder.onstop = () => {
        if (recorderRef.current !== recorder) return;
        recorderRef.current = null;
        liberarMicrofone();
        if (!montado.current) return;
        setGravando(false);
        if (falhou) return;
        try { selecionar([arquivoGravado(new Blob(chunks, { type: recorder.mimeType || chunks[0]?.type }))]); }
        catch (err) { setErro(err instanceof Error ? err.message : "Não foi possível salvar a gravação."); }
      };
      recorder.onerror = () => {
        falhou = true;
        if (recorderRef.current !== recorder) return;
        liberarMicrofone();
        if (montado.current) { setGravando(false); setErro("Falha na gravação. Tente novamente."); }
      };
      // Nível é apenas feedback de captura; fala útil é calculada no servidor.
      let analyser: AnalyserNode | null = null;
      if (typeof AudioContext !== "undefined") {
        try {
          const context = new AudioContext(); contextRef.current = context;
          analyser = context.createAnalyser(); analyser.fftSize = 1024;
          context.createMediaStreamSource(stream).connect(analyser);
        } catch { /* Gravação segue mesmo sem suporte ao medidor. */ }
      }
      const inicio = Date.now(); setSegundos(0);
      recorder.start(250); setGravando(true);
      timerRef.current = setInterval(() => {
        setSegundos(Math.floor((Date.now() - inicio) / 1000));
        if (analyser) {
          const dados = new Float32Array(analyser.fftSize);
          analyser.getFloatTimeDomainData(dados);
          setNivel(Math.min(1, Math.sqrt(dados.reduce((s, x) => s + x * x, 0) / dados.length) * 4));
        }
        if (Date.now() - inicio >= 180000 && recorder.state === "recording") recorder.stop();
      }, 250);
    } catch {
      liberarMicrofone();
      if (montado.current) setErro("Não foi possível gravar. Verifique a permissão do microfone ou envie um arquivo.");
    } finally { if (montado.current) setIniciando(false); }
  }

  function formulario() {
    const dados = new FormData(); arquivos.forEach((f) => dados.append("arquivos", f)); return dados;
  }

  async function analisar() {
    setOcupado("analisando"); setErro(""); setQualidade(null);
    try {
      const resultado = await apiFetchForm<QualidadeVoz>("/tts/analisar-voz", formulario());
      if (montado.current) setQualidade(resultado);
    } catch (err) { if (montado.current) setErro(err instanceof ApiError ? err.message : "Falha ao analisar áudio."); }
    finally { if (montado.current) setOcupado(null); }
  }

  async function enviar() {
    if (!qualidade || gravando || !nome.trim()) return;
    setOcupado("clonando"); setErro("");
    try {
      const dados = formulario(); dados.set("nome", nome.trim());
      const criada = await apiFetchForm<VozClonada>("/tts/vozes-clonadas", dados);
      if (montado.current) onCriada(criada);
    } catch (err) { if (montado.current) setErro(err instanceof ApiError ? err.message : "Erro ao clonar voz."); }
    finally { if (montado.current) setOcupado(null); }
  }

  const bloqueado = !!ocupado || gravando || iniciando;
  return <Modal open onClose={() => { if (!ocupado) onFechar(); }} title="Clonar voz" maxWidthClassName="max-w-xl">
    <div role="dialog" aria-label="Clonar voz" aria-modal="true" className="space-y-4">
      <p className="text-sm text-fg/70">Envie 60–120 segundos de fala do mesmo locutor, em até 5 arquivos. Grave sem música ou eco, a cerca de um palmo do microfone, mantendo distância e volume constantes. Use o jeito de falar que deseja ouvir na rádio.</p>
      <label className="block text-sm">Nome da voz
        <input className="mt-1 w-full rounded-lg border border-border-strong bg-bg p-2" value={nome} onChange={(e) => setNome(e.target.value)} maxLength={100} disabled={!!ocupado} placeholder="Ex.: Minha voz de rádio" />
      </label>
      <label className="block text-sm">Arquivos de voz
        <input className="mt-1 block w-full text-xs" type="file" accept=".mp3,.wav,.m4a,.mp4,.ogg,.webm" multiple disabled={bloqueado} onChange={(e) => selecionar(Array.from(e.target.files ?? []))} />
      </label>
      <p className="text-xs text-fg/65">Até 15 MB e 3 minutos no total. Mínimo de 20 segundos de fala detectada.</p>
      <button type="button" className="rounded-lg border border-border-strong px-3 py-2 text-sm disabled:opacity-50" disabled={!!ocupado || iniciando} onClick={() => gravando ? recorderRef.current?.stop() : iniciarGravacao()}>
        {iniciando ? "Acessando microfone…" : gravando ? "Parar gravação" : "Gravar pelo microfone"}
      </button>
      {gravando && <div className="space-y-1">
        <p className="text-sm">Gravação: {segundos}s · procure completar 60–120s</p>
        <label className="block text-xs">Nível do microfone <meter aria-label="Nível do microfone" min={0} max={1} value={nivel} className="w-full" /></label>
        <p className="text-xs text-fg/65">Se o nível ficar no máximo, afaste o microfone ou reduza o ganho.</p>
      </div>}
      {arquivos.map((f, i) => <div key={`${f.name}-${i}`} className="min-w-0">
        <p className="break-all text-xs text-fg/65">{f.name}</p>
        {previews[i] && <audio controls preload="metadata" src={previews[i]} className="mt-1 h-9 w-full" />}
      </div>)}
      <button type="button" onClick={analisar} disabled={bloqueado || !arquivos.length} className="rounded-lg border border-amber/50 px-3 py-2 text-sm disabled:opacity-50">{ocupado === "analisando" ? "Analisando áudio…" : "Analisar amostras"}</button>
      {qualidade && <div role="status" className="rounded-lg border border-border-strong p-3 text-sm">
        <p>{qualidade.fala_segundos}s de fala detectada em {qualidade.duracao_segundos}s de áudio.</p>
        {qualidade.avisos.map((aviso) => <p key={aviso} className="mt-2 text-amber-text">{aviso}</p>)}
        <p className="mt-2 text-xs text-fg/65">Ouça as amostras: a análise não garante ausência de música, eco ou outras pessoas.</p>
      </div>}
      {erro && <p role="alert" className="text-sm text-rust-text">{erro}</p>}
      <div className="flex justify-end gap-3">
        <button type="button" onClick={onFechar} disabled={!!ocupado} className="px-3 py-2 text-sm disabled:opacity-50">Cancelar</button>
        <button type="button" onClick={enviar} disabled={bloqueado || !nome.trim() || !qualidade} className="rounded-lg bg-amber px-4 py-2 text-sm font-medium text-ink disabled:opacity-50">{ocupado === "clonando" ? "Clonando…" : "Clonar voz"}</button>
      </div>
      <p className="text-xs text-fg/65">Para uma voz profissional, o titular precisa criar e verificar a própria voz na ElevenLabs. A clonagem aqui é instantânea.</p>
    </div>
  </Modal>;
}
