import { expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { GraficoBarras } from "../GraficoBarras";

it("datas do eixo ficam fora do SVG esticado (sem deformar nem cortar)", () => {
  const serie = Array.from({ length: 30 }, (_, i) => ({ data: `2026-09-${String(i + 1).padStart(2, "0")}`, total: i }));
  const { container } = render(<GraficoBarras serie={serie} />);
  expect(container.querySelector("svg text")).toBeNull();
  expect(screen.getByText("01/09")).toBeInTheDocument();
  expect(screen.getByText("30/09")).toBeInTheDocument();
});
