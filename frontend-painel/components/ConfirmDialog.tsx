"use client";

import Modal from "./Modal";

type ConfirmDialogProps = {
  open: boolean;
  title: string;
  mensagem: string;
  confirmarLabel?: string;
  cancelarLabel?: string;
  onConfirmar: () => void;
  onCancelar: () => void;
};

export default function ConfirmDialog({
  open,
  title,
  mensagem,
  confirmarLabel = "Excluir",
  cancelarLabel = "Cancelar",
  onConfirmar,
  onCancelar,
}: ConfirmDialogProps) {
  return (
    <Modal open={open} onClose={onCancelar} title={title} maxWidthClassName="max-w-sm">
      <p className="text-sm text-fg/70 mb-6">{mensagem}</p>
      <div className="flex justify-end gap-3">
        <button
          type="button"
          onClick={onCancelar}
          className="rounded-lg px-4 py-2.5 text-sm font-medium text-fg/60 hover:text-fg"
        >
          {cancelarLabel}
        </button>
        <button
          type="button"
          onClick={onConfirmar}
          className="rounded-lg bg-rust px-4 py-2.5 text-sm font-medium text-fg hover:bg-rust/90"
        >
          {confirmarLabel}
        </button>
      </div>
    </Modal>
  );
}
