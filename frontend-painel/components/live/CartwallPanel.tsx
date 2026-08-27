"use client";

import { useRef, useState } from "react";
import { apiFetchBlob, ApiError } from "../../lib/api";
import { BibliotecaAudioItem, formatarDuracao } from "../../lib/bibliotecaAudio";
import { LocufySpin } from "../LocufyLogo";

type Props = {
  itens: BibliotecaAudioItem[];
  duckMusicaFundo: (baixo: boolean) => void;
  programaAtivo: boolean;
  onInserirNaTransmissao: (item: BibliotecaAudioItem) => void;
};

export default function CartwallPanel({ itens, duckMusicaFundo, programaAtivo, onInserirNaTransmissao }: Props) {
  const [tocandoId, setTocandoId] = useState<number | null>(null);
  const [carregandoId, setCarregandoId] = useState<number | null>(null);
  const [erro, setErro] = useState("");
  const audioAtualRef = useRef<HTMLAudioElement | null>(null);

  function pararTudo() {
    if (audioAtualRef.current) {
      audioAtualRef.current.pause();
      audioAtualRef.current = null;
    }
    duckMusicaFundo(false);
    setTocandoId(null);
  }

  async function tocar(item: BibliotecaAudioItem) {
    // com a transmissao no ar, o clique vai direto pro ao vivo -- corta a fala/musica
    // atual e poe esse audio no ar, em vez de so tocar por cima como no preview abaixo.
    if (programaAtivo) {
      onInserirNaTransmissao(item);
      return;
    }

    if (tocandoId === item.id) {
      pararTudo();
      return;
    }
    // sem transmissao ativa: preview isolado, toca "por cima" sem afetar nada.
    if (audioAtualRef.current) audioAtualRef.current.pause();

    setErro("");
    setCarregandoId(item.id);
    try {
      const blob = await apiFetchBlob(`/biblioteca-audio/${item.id}/audio`);
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioAtualRef.current = audio;
      duckMusicaFundo(true);
      setTocandoId(item.id);
      audio.onended = () => {
        URL.revokeObjectURL(url);
        if (audioAtualRef.current === audio) {
          audioAtualRef.current = null;
          duckMusicaFundo(false);
          setTocandoId(null);
        }
      };
      await audio.play();
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao tocar audio");
      duckMusicaFundo(false);
      setTocandoId(null);
    } finally {
      setCarregandoId(null);
    }
  }

  return (
    <section className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-5">
      <div className="flex items-center justify-between mb-1">
        <h2 className="font-display text-base font-bold text-fg">Cartwall</h2>
        {tocandoId !== null && (
          <button type="button" onClick={pararTudo} className="text-xs font-medium text-rust-text hover:text-rust/80">
            Parar
          </button>
        )}
      </div>
      <p className="text-xs text-fg/65 mb-3">Toque manual durante a transmissão.</p>

      {erro && <p className="text-xs text-rust-text mb-3">{erro}</p>}

      {itens.length === 0 ? (
        <p className="text-sm text-fg/65">
          Nenhum áudio ativo na biblioteca ainda. Cadastre em Biblioteca (aqui do lado) ou em /vinhetagem pra eles
          aparecerem aqui como botões.
        </p>
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
          {itens.map((item) => {
            const ativo = tocandoId === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => tocar(item)}
                style={item.cor ? { borderColor: item.cor } : undefined}
                className={`rounded-2xl border p-3 text-left shadow-theme-xs transition-colors ${
                  ativo
                    ? "bg-teal/10 border-teal/50 ring-1 ring-teal/30"
                    : "bg-surface border-border-strong hover:border-amber/40"
                }`}
              >
                <p className="text-sm font-medium text-fg truncate">{item.nome}</p>
                <p className="mt-1 flex items-center gap-1.5 font-mono text-xs text-fg/65">
                  {carregandoId === item.id ? (
                    <LocufySpin size={12} />
                  ) : (
                    <span>{ativo ? "■ tocando" : "▶"}</span>
                  )}
                  {formatarDuracao(item.duracao_segundos)}
                </p>
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}
