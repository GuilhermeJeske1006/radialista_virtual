import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import PersonaPrograma from "../PersonaPrograma";
import { PERSONA_PADRAO } from "../../lib/types";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("sem persona mostra só o botão de definir e grava o padrão ao clicar", () => {
  const onChange = vi.fn();
  render(<PersonaPrograma persona={null} onChange={onChange} />);
  fireEvent.click(screen.getByRole("button", { name: "Definir persona da rádio" }));
  expect(onChange).toHaveBeenCalledWith(PERSONA_PADRAO);
});

it("com persona, trocar a energia grava a escala como número", () => {
  const onChange = vi.fn();
  render(<PersonaPrograma persona={{ ...PERSONA_PADRAO }} onChange={onChange} />);
  fireEvent.change(screen.getByLabelText("Energia"), { target: { value: "5" } });
  expect(onChange).toHaveBeenCalledWith({ ...PERSONA_PADRAO, energia: 5 });
});

it("remover persona grava null", () => {
  const onChange = vi.fn();
  render(<PersonaPrograma persona={{ ...PERSONA_PADRAO }} onChange={onChange} />);
  fireEvent.click(screen.getByRole("button", { name: /Remover persona/ }));
  expect(onChange).toHaveBeenCalledWith(null);
});

it("exemplos: uma linha por exemplo, linhas vazias descartadas e Enter não some ao digitar", () => {
  const onChange = vi.fn();
  render(<PersonaPrograma persona={{ ...PERSONA_PADRAO }} onChange={onChange} />);
  const area = screen.getByLabelText(/Exemplos de fala aprovados/);
  fireEvent.change(area, { target: { value: "Bom dia\n\n  Boa tarde  \n" } });
  expect(onChange).toHaveBeenLastCalledWith({ ...PERSONA_PADRAO, exemplos: ["Bom dia", "Boa tarde"] });
  expect((area as HTMLTextAreaElement).value).toBe("Bom dia\n\n  Boa tarde  \n");
});

it("avisa quando passa de 5 exemplos", () => {
  const onChange = vi.fn();
  render(<PersonaPrograma persona={{ ...PERSONA_PADRAO }} onChange={onChange} />);
  const seis = ["a", "b", "c", "d", "e", "f"].join("\n");
  fireEvent.change(screen.getByLabelText(/Exemplos de fala aprovados/), { target: { value: seis } });
  expect(screen.getByRole("alert").textContent).toContain("no máximo 5");
});
