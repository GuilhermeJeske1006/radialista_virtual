import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Modal from "../Modal";

describe("Modal", () => {
  it("nao renderiza nada quando open e false", () => {
    const { container } = render(
      <Modal open={false} onClose={() => {}} title="Titulo">
        conteudo
      </Modal>
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renderiza titulo e conteudo quando open", () => {
    render(
      <Modal open onClose={() => {}} title="Meu Titulo">
        <p>conteudo do modal</p>
      </Modal>
    );
    expect(screen.getByText("Meu Titulo")).toBeInTheDocument();
    expect(screen.getByText("conteudo do modal")).toBeInTheDocument();
  });

  it("chama onClose ao clicar no botao fechar", async () => {
    const onClose = vi.fn();
    render(
      <Modal open onClose={onClose} title="Titulo">
        conteudo
      </Modal>
    );
    await userEvent.click(screen.getByRole("button", { name: "Fechar" }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("chama onClose ao pressionar Escape", async () => {
    const onClose = vi.fn();
    render(
      <Modal open onClose={onClose} title="Titulo">
        conteudo
      </Modal>
    );
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("chama onClose ao clicar no overlay mas nao ao clicar no conteudo", async () => {
    const onClose = vi.fn();
    const { container } = render(
      <Modal open onClose={onClose} title="Titulo">
        <p>conteudo do modal</p>
      </Modal>
    );
    await userEvent.click(screen.getByText("conteudo do modal"));
    expect(onClose).not.toHaveBeenCalled();

    // O overlay e' o proprio elemento raiz renderizado (onClick={onClose}); o wrapper
    // interno faz stopPropagation, entao so' clicar fora dele deve fechar o modal.
    await userEvent.click(container.firstElementChild as Element);
    expect(onClose).toHaveBeenCalled();
  });
});
