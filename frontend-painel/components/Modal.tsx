"use client";

import { useEffect } from "react";

type ModalProps = {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  maxWidthClassName?: string;
  // Ações fixas abaixo do conteúdo rolável (conteúdo longo não esconde os botões).
  footer?: React.ReactNode;
};

export default function Modal({ open, onClose, title, children, maxWidthClassName = "max-w-2xl", footer }: ModalProps) {
  useEffect(() => {
    if (!open) return;

    function aoTeclar(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }

    window.addEventListener("keydown", aoTeclar);
    const overflowOriginal = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", aoTeclar);
      document.body.style.overflow = overflowOriginal;
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-azul/70 p-4 backdrop-blur-sm sm:p-8"
      onClick={onClose}
    >
      <div
        className={`my-auto w-full ${maxWidthClassName} overflow-hidden rounded-3xl border border-border-strong bg-surface shadow-theme-sm ${
          footer ? "flex max-h-[calc(100dvh-2rem)] flex-col sm:max-h-[calc(100dvh-4rem)]" : ""
        }`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex shrink-0 items-center justify-between gap-4 px-6 pt-5 pb-4">
          <h2 className="font-display text-lg font-semibold text-fg">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Fechar"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-fg/50 hover:bg-fg/5 hover:text-fg transition-colors"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" className="h-4 w-4">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        </div>
        <div className={`${footer ? "min-h-0 flex-1" : "max-h-[calc(100vh-9rem)]"} overflow-y-auto px-6 pb-6`}>{children}</div>
        {footer && <div className="shrink-0 border-t border-border-strong px-6 py-4">{footer}</div>}
      </div>
    </div>
  );
}
