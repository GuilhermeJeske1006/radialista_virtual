import { beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ThemeToggle from "../ThemeToggle";

beforeEach(() => {
  window.localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
});

describe("ThemeToggle", () => {
  it("comeca no tema dark por padrao", () => {
    render(<ThemeToggle />);
    expect(screen.getByRole("button")).toHaveAttribute("aria-label", "Mudar para tema claro");
  });

  it("reflete o tema ja aplicado no documento", () => {
    document.documentElement.setAttribute("data-theme", "light");
    render(<ThemeToggle />);
    expect(screen.getByRole("button")).toHaveAttribute("aria-label", "Mudar para tema escuro");
  });

  it("alterna o tema ao clicar e persiste no localStorage", async () => {
    render(<ThemeToggle />);
    const botao = screen.getByRole("button");

    await userEvent.click(botao);
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(window.localStorage.getItem("onda-theme")).toBe("light");

    await userEvent.click(botao);
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(window.localStorage.getItem("onda-theme")).toBe("dark");
  });
});
