"use client";

import { useEffect, useRef, useState } from "react";

type Props = {
  src: string;
  className?: string;
};

/** Player compacto pra amostras de voz: botão play/pausa + barra de progresso,
 * no lugar do <audio controls> nativo (feio e não segue o tema). */
export default function AudioPreviewButton({ src, className = "" }: Props) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [tocando, setTocando] = useState(false);
  const [progresso, setProgresso] = useState(0);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    function aoAtualizarTempo() {
      if (audio && audio.duration) setProgresso(audio.currentTime / audio.duration);
    }
    function aoTerminar() {
      setTocando(false);
      setProgresso(0);
    }
    audio.addEventListener("timeupdate", aoAtualizarTempo);
    audio.addEventListener("ended", aoTerminar);
    return () => {
      audio.removeEventListener("timeupdate", aoAtualizarTempo);
      audio.removeEventListener("ended", aoTerminar);
    };
  }, []);

  function alternar() {
    const audio = audioRef.current;
    if (!audio) return;
    if (tocando) {
      audio.pause();
      setTocando(false);
    } else {
      audio.play();
      setTocando(true);
    }
  }

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <audio ref={audioRef} src={src} preload="none" className="hidden" />
      <button
        type="button"
        onClick={alternar}
        aria-label={tocando ? "Pausar amostra" : "Tocar amostra"}
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-acento-claro/15 text-acento-claro transition-colors hover:bg-acento-claro/25"
      >
        {tocando ? (
          <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor" aria-hidden="true">
            <rect x="1" y="0.5" width="3.5" height="11" rx="1" />
            <rect x="7" y="0.5" width="3.5" height="11" rx="1" />
          </svg>
        ) : (
          <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor" aria-hidden="true">
            <path d="M1.5 0.7a1 1 0 0 1 1.53-.85l7.5 4.8a1 1 0 0 1 0 1.7l-7.5 4.8A1 1 0 0 1 1.5 10.3V0.7Z" />
          </svg>
        )}
      </button>
      <div className="h-1 w-16 shrink-0 overflow-hidden rounded-full bg-fg/10 sm:w-20">
        <div className="h-full bg-acento-claro transition-[width]" style={{ width: `${progresso * 100}%` }} />
      </div>
    </div>
  );
}
