import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { useAvisoAlteracoes } from "../useAvisoAlteracoes";

function Tela({ pendente }: { pendente: boolean }) {
  useAvisoAlteracoes(pendente);
  // preventDefault no próprio link só evita o jsdom tentar navegar; o hook age antes, na captura.
  return <a href="/dashboard" onClick={(e) => e.preventDefault()}>Sair</a>;
}

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("pede confirmação ao sair por link com alteração pendente", () => {
  const confirmar = vi.spyOn(window, "confirm").mockReturnValue(false);
  render(<Tela pendente />);
  const evento = new MouseEvent("click", { bubbles: true, cancelable: true, button: 0 });
  screen.getByText("Sair").dispatchEvent(evento);
  expect(confirmar).toHaveBeenCalled();
  expect(evento.defaultPrevented).toBe(true);
});

it("sem alteração pendente navega direto", () => {
  const confirmar = vi.spyOn(window, "confirm");
  render(<Tela pendente={false} />);
  const evento = new MouseEvent("click", { bubbles: true, cancelable: true, button: 0 });
  screen.getByText("Sair").dispatchEvent(evento);
  expect(confirmar).not.toHaveBeenCalled();
});
