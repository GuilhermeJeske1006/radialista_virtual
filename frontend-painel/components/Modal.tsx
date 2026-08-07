"use client";

import { useEffect } from "react";

type ModalProps = {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  maxWidthClassName?: string;
};

export default function Modal({ open, onClose, title, children, maxWidthClassName = "max-w-2xl" }: ModalProps) {
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
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/60 p-4 sm:p-8"
      onClick={onClose}
    >
      <div
        className={`my-auto w-full ${maxWidthClassName} rounded-2xl border border-border-strong bg-surface shadow-theme-xs`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <h2 className="font-display text-base font-bold text-fg">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Fechar"
            className="rounded-lg p-1 text-fg/55 hover:bg-paper/10 hover:text-fg"
          >
            ✕
          </button>
        </div>
        <div className="max-h-[calc(100vh-9rem)] overflow-y-auto p-6">{children}</div>
      </div>
    </div>
  );
}
