import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import PersonaPrograma from "../PersonaPrograma";
import { PERSONA_PADRAO } from "../../lib/types";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("sem persona mostra só o botão de definir e grava o padrão ao clicar", () => {
  const onChange = vi.fn();
  render(<PersonaPrograma persona={null} onChange={onChange} />);
  fireEvent.click(screen.getByRole("button", { name: "Personalizar jeito de falar" }));
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
  fireEvent.click(screen.getByRole("button", { name: "Usar personalidade geral do radialista" }));
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

it("perfil jornalístico combina seriedade e ausência de gírias sem apagar orientações e exemplos", () => {
  const onChange = vi.fn();
  const persona = { ...PERSONA_PADRAO, exemplos: ["Boa tarde."], orientacoes: "Boletins objetivos." };
  render(<PersonaPrograma persona={persona} onChange={onChange} />);
  fireEvent.change(screen.getByLabelText("Perfil de fala"), { target: { value: "jornalistico" } });
  expect(onChange).toHaveBeenCalledWith({ ...persona, formalidade: 5, energia: 2, humor: 1, girias: "evitar" });
});

it("perfil descontraído permite mais gírias", () => {
  const onChange = vi.fn();
  render(<PersonaPrograma persona={{ ...PERSONA_PADRAO }} onChange={onChange} />);
  fireEvent.change(screen.getByLabelText("Perfil de fala"), { target: { value: "descontraido" } });
  expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ formalidade: 1, humor: 4, girias: "frequentes" }));
});

it("ajustar um programa não altera o outro, com rótulos acessíveis independentes", () => {
  const primeiro = vi.fn(), segundo = vi.fn();
  render(<>
    <PersonaPrograma persona={{ ...PERSONA_PADRAO }} onChange={primeiro} />
    <PersonaPrograma persona={{ ...PERSONA_PADRAO, formalidade: 5, humor: 1, girias: "evitar" }} onChange={segundo} />
  </>);
  const [musical, jornal] = screen.getAllByRole("group", { name: "Jeito de falar neste programa" });
  fireEvent.change(within(musical).getByLabelText("Uso de gírias"), { target: { value: "frequentes" } });
  expect(primeiro).toHaveBeenCalledWith(expect.objectContaining({ girias: "frequentes" }));
  expect(segundo).not.toHaveBeenCalled();
  expect(within(jornal).getByLabelText("Uso de gírias")).toHaveValue("evitar");
});

it("aceita dados antigos e permite escrever orientações por programa", () => {
  const onChange = vi.fn();
  const { girias: _, orientacoes: __, ...antiga } = PERSONA_PADRAO;
  render(<PersonaPrograma persona={antiga} onChange={onChange} />);
  expect(screen.getByLabelText("Uso de gírias")).toHaveValue("automatico");
  fireEvent.change(screen.getByLabelText("Orientações para este programa"), { target: { value: "Fale com calma." } });
  expect(onChange).toHaveBeenCalledWith({ ...antiga, orientacoes: "Fale com calma." });
  expect(screen.getByLabelText("Orientações para este programa")).toHaveAttribute("maxlength", "1200");
});
