import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ConfirmDialog from "../ConfirmDialog";

describe("ConfirmDialog", () => {
  it("nao renderiza quando fechado", () => {
    const { container } = render(
      <ConfirmDialog
        open={false}
        title="Excluir item"
        mensagem="Tem certeza?"
        onConfirmar={() => {}}
        onCancelar={() => {}}
      />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("usa labels padrao", () => {
    render(
      <ConfirmDialog
        open
        title="Excluir item"
        mensagem="Tem certeza?"
        onConfirmar={() => {}}
        onCancelar={() => {}}
      />
    );
    expect(screen.getByRole("button", { name: "Excluir" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancelar" })).toBeInTheDocument();
  });

  it("usa labels customizadas", () => {
    render(
      <ConfirmDialog
        open
        title="Desativar"
        mensagem="Confirma?"
        confirmarLabel="Desativar"
        cancelarLabel="Voltar"
        onConfirmar={() => {}}
        onCancelar={() => {}}
      />
    );
    expect(screen.getByRole("button", { name: "Desativar" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Voltar" })).toBeInTheDocument();
  });

  it("chama onConfirmar ao clicar em confirmar", async () => {
    const onConfirmar = vi.fn();
    render(
      <ConfirmDialog
        open
        title="Excluir item"
        mensagem="Tem certeza?"
        onConfirmar={onConfirmar}
        onCancelar={() => {}}
      />
    );
    await userEvent.click(screen.getByRole("button", { name: "Excluir" }));
    expect(onConfirmar).toHaveBeenCalledOnce();
  });

  it("chama onCancelar ao clicar em cancelar", async () => {
    const onCancelar = vi.fn();
    render(
      <ConfirmDialog
        open
        title="Excluir item"
        mensagem="Tem certeza?"
        onConfirmar={() => {}}
        onCancelar={onCancelar}
      />
    );
    await userEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(onCancelar).toHaveBeenCalledOnce();
  });
});
