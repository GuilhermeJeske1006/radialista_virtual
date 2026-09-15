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
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancelar}
          className="rounded-full px-4 py-2.5 text-sm font-semibold text-fg/60 hover:bg-fg/5 hover:text-fg transition-colors"
        >
          {cancelarLabel}
        </button>
        {/* A paleta não tem vermelho. Destrutivo usa o Laranja Vibração Humana
            com texto grafite — é o sinal mais alto do manual. */}
        <button
          type="button"
          onClick={onConfirmar}
          className="rounded-full bg-laranja px-4 py-2.5 text-sm font-semibold text-grafite hover:opacity-90 transition-opacity"
        >
          {confirmarLabel}
        </button>
      </div>
    </Modal>
  );
}
