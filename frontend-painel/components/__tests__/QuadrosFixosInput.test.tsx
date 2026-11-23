import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import QuadrosFixosInput from "../QuadrosFixosInput";
import { ehQuadroNarrativo } from "../../lib/quadroNarrativo";

afterEach(() => cleanup());

describe("ehQuadroNarrativo (espelho do backend)", () => {
  it("reconhece o prefixo sem acento e sem caixa", () => {
    expect(ehQuadroNarrativo("Narrativo: a feira")).toBe(true);
    expect(ehQuadroNarrativo("HISTÓRIA da semana")).toBe(true);
    expect(ehQuadroNarrativo("  historia do bairro")).toBe(true);
    expect(ehQuadroNarrativo("Curiosidade das 10")).toBe(false);
    expect(ehQuadroNarrativo("")).toBe(false);
  });
});

describe("QuadrosFixosInput (F14)", () => {
  it("marca o quadro narrativo e explica como criar um", () => {
    render(
      <QuadrosFixosInput
        quadros={{ "História do bairro": ["a padaria"], "Curiosidade das 10": [] }}
        onChange={vi.fn()}
      />,
    );
    expect(screen.getAllByText(/Narrativo: personagem → situação → mudança → consequência/)).toHaveLength(1);
    expect(screen.getByText(/comece o nome com “Narrativo” ou “História”/)).toBeTruthy();
  });
});
