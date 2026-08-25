import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import EstruturaBlocosInput from "../EstruturaBlocosInput";

describe("EstruturaBlocosInput", () => {
  it("adiciona bloco preset ao clicar", async () => {
    const onChange = vi.fn();
    render(<EstruturaBlocosInput blocos={[]} onChange={onChange} />);

    await userEvent.click(screen.getByRole("button", { name: "+ Abertura" }));
    expect(onChange).toHaveBeenCalledWith(["abertura"]);
  });

  it("permite repetir o mesmo bloco preset", async () => {
    const onChange = vi.fn();
    render(<EstruturaBlocosInput blocos={["abertura"]} onChange={onChange} />);

    await userEvent.click(screen.getByRole("button", { name: "+ Abertura" }));
    expect(onChange).toHaveBeenCalledWith(["abertura", "abertura"]);
  });

  it("adiciona bloco customizado via texto livre", async () => {
    const onChange = vi.fn();
    render(<EstruturaBlocosInput blocos={[]} onChange={onChange} />);

    await userEvent.type(
      screen.getByPlaceholderText("Bloco personalizado e pressione Enter"),
      "Musica Vaneira{Enter}"
    );
    expect(onChange).toHaveBeenCalledWith(["Musica Vaneira"]);
  });

  it("remove bloco ao clicar no x", async () => {
    const onChange = vi.fn();
    render(<EstruturaBlocosInput blocos={["abertura", "musica"]} onChange={onChange} />);

    const removerBotoes = screen.getAllByTitle("Remover");
    await userEvent.click(removerBotoes[0]);
    expect(onChange).toHaveBeenCalledWith(["musica"]);
  });

  it("move bloco para a direita", async () => {
    const onChange = vi.fn();
    render(<EstruturaBlocosInput blocos={["abertura", "musica"]} onChange={onChange} />);

    await userEvent.click(screen.getAllByTitle("Mover pra direita")[0]);
    expect(onChange).toHaveBeenCalledWith(["musica", "abertura"]);
  });

  it("desabilita mover pra esquerda no primeiro item", () => {
    render(<EstruturaBlocosInput blocos={["abertura", "musica"]} onChange={() => {}} />);
    expect(screen.getAllByTitle("Mover pra esquerda")[0]).toBeDisabled();
  });

  it("mostra select de patrocinadores so quando ha patrocinador ativo", () => {
    const { rerender } = render(<EstruturaBlocosInput blocos={[]} onChange={() => {}} patrocinadores={[]} />);
    expect(screen.queryByText("+ Patrocinador")).not.toBeInTheDocument();

    rerender(
      <EstruturaBlocosInput
        blocos={[]}
        onChange={() => {}}
        patrocinadores={[{ id: 1, nome: "Loja X", categoria_id: null, tipo_conteudo: "texto", ativo: true }]}
      />
    );
    expect(screen.getByText("+ Patrocinador")).toBeInTheDocument();
  });

  it("adiciona bloco de patrocinador ao selecionar no dropdown", async () => {
    const onChange = vi.fn();
    render(
      <EstruturaBlocosInput
        blocos={[]}
        onChange={onChange}
        patrocinadores={[{ id: 7, nome: "Loja X", categoria_id: null, tipo_conteudo: "texto", ativo: true }]}
      />
    );

    await userEvent.selectOptions(screen.getByDisplayValue("+ Patrocinador"), "7");
    expect(onChange).toHaveBeenCalledWith(["patrocinador:7"]);
  });

  it("renderiza o rotulo do patrocinador na lista de blocos", () => {
    render(
      <EstruturaBlocosInput
        blocos={["patrocinador:7"]}
        onChange={() => {}}
        patrocinadores={[{ id: 7, nome: "Loja X", categoria_id: null, tipo_conteudo: "texto", ativo: true }]}
      />
    );
    expect(screen.getByText("Patrocinador: Loja X")).toBeInTheDocument();
  });
});
