import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import TagInput from "../TagInput";

describe("TagInput", () => {
  it("renderiza as tags existentes", () => {
    render(<TagInput label="Tópicos" tags={["musica", "esportes"]} onChange={() => {}} />);
    expect(screen.getByText("musica")).toBeInTheDocument();
    expect(screen.getByText("esportes")).toBeInTheDocument();
  });

  it("adiciona tag ao pressionar Enter", async () => {
    const onChange = vi.fn();
    render(<TagInput label="Tópicos" tags={[]} onChange={onChange} />);

    const input = screen.getByPlaceholderText("Digite e pressione Enter");
    await userEvent.type(input, "noticias{Enter}");

    expect(onChange).toHaveBeenCalledWith(["noticias"]);
  });

  it("adiciona tag ao clicar em Adicionar", async () => {
    const onChange = vi.fn();
    render(<TagInput label="Tópicos" tags={[]} onChange={onChange} />);

    await userEvent.type(screen.getByPlaceholderText("Digite e pressione Enter"), "esportes");
    await userEvent.click(screen.getByRole("button", { name: "Adicionar" }));

    expect(onChange).toHaveBeenCalledWith(["esportes"]);
  });

  it("nao adiciona tag duplicada", async () => {
    const onChange = vi.fn();
    render(<TagInput label="Tópicos" tags={["musica"]} onChange={onChange} />);

    await userEvent.type(screen.getByPlaceholderText("Digite e pressione Enter"), "musica{Enter}");

    expect(onChange).not.toHaveBeenCalled();
  });

  it("nao adiciona tag vazia", async () => {
    const onChange = vi.fn();
    render(<TagInput label="Tópicos" tags={[]} onChange={onChange} />);

    await userEvent.type(screen.getByPlaceholderText("Digite e pressione Enter"), "   {Enter}");

    expect(onChange).not.toHaveBeenCalled();
  });

  it("remove tag ao clicar no x", async () => {
    const onChange = vi.fn();
    render(<TagInput label="Tópicos" tags={["musica", "esportes"]} onChange={onChange} />);

    const botoesRemover = screen.getAllByText("×");
    await userEvent.click(botoesRemover[0]);

    expect(onChange).toHaveBeenCalledWith(["esportes"]);
  });
});
