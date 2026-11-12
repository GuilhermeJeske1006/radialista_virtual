import { beforeEach, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PautaDoDiaSection from "../PautaDoDiaSection";
import type { AssuntoPauta } from "../../lib/types";

const api = vi.hoisted(() => vi.fn());
vi.mock("../../lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/api")>()),
  apiFetch: api,
}));

function assuntos(quantidade: number): AssuntoPauta[] {
  return Array.from({ length: quantidade }, (_, i) => ({
    id: i + 1,
    assunto_id: i + 1,
    titulo: `Assunto ${i + 1}`,
    gancho: `Gancho ${i + 1}`,
    fatos: [],
    tags: [],
    origem: "noticia",
    score: quantidade - i,
    ponte: "",
    eixos_sugeridos: [],
    validade_ate: null,
  }));
}

beforeEach(() => api.mockReset());

it("navega por cinco assuntos por página sem buscar a pauta novamente", async () => {
  api.mockResolvedValue(assuntos(11));
  render(<PautaDoDiaSection programaId={7} />);

  const nav = await screen.findByRole("navigation", { name: "Páginas da pauta do dia" });
  expect(nav).toHaveTextContent("Página 1 de 3");
  expect(screen.getAllByRole("button", { name: "Fixar" })).toHaveLength(5);
  expect(screen.getByRole("button", { name: "‹ Anterior" })).toBeDisabled();
  expect(screen.queryByText("Assunto 6")).not.toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: "Próxima ›" }));
  expect(nav).toHaveTextContent("Página 2 de 3");
  expect(screen.getByText("Assunto 6")).toBeInTheDocument();
  expect(screen.queryByText("Assunto 1")).not.toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: "Próxima ›" }));
  expect(nav).toHaveTextContent("Página 3 de 3");
  expect(screen.getAllByRole("button", { name: "Fixar" })).toHaveLength(1);
  expect(screen.getByRole("button", { name: "Próxima ›" })).toBeDisabled();

  await userEvent.click(screen.getByRole("button", { name: "‹ Anterior" }));
  expect(nav).toHaveTextContent("Página 2 de 3");
  expect(api).toHaveBeenCalledTimes(1);
});

it("volta à página anterior ao descartar o único assunto da última página", async () => {
  api.mockResolvedValueOnce(assuntos(6)).mockResolvedValueOnce(undefined);
  render(<PautaDoDiaSection programaId={7} />);
  await screen.findByRole("navigation");
  await userEvent.click(screen.getByRole("button", { name: "Próxima ›" }));
  await userEvent.click(screen.getByRole("button", { name: "Descartar" }));

  await waitFor(() => expect(screen.queryByText("Assunto 6")).not.toBeInTheDocument());
  expect(api).toHaveBeenCalledWith("/topics/programas/7/pauta/6", { method: "DELETE" });
  expect(screen.getByText("Assunto 1")).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: "Fixar" })).toHaveLength(5);
  expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
});

it("mantém a prioridade ao fixar um assunto de outra página", async () => {
  const pauta = assuntos(6);
  api.mockResolvedValueOnce(pauta).mockResolvedValueOnce({ ...pauta[5], score: 101 });
  render(<PautaDoDiaSection programaId={7} />);
  await screen.findByRole("navigation");
  await userEvent.click(screen.getByRole("button", { name: "Próxima ›" }));
  await userEvent.click(screen.getByRole("button", { name: "Fixar" }));

  await waitFor(() => expect(screen.queryByText("Assunto 6")).not.toBeInTheDocument());
  expect(api).toHaveBeenCalledWith("/topics/programas/7/pauta/6/fixar", { method: "POST" });
  await userEvent.click(screen.getByRole("button", { name: "‹ Anterior" }));
  expect(screen.getByText("Assunto 6")).toBeInTheDocument();
  expect(screen.getByText("score 101.0")).toBeInTheDocument();
});

it("começa na primeira página ao trocar de programa", async () => {
  api.mockResolvedValue(assuntos(6));
  const { rerender } = render(<PautaDoDiaSection programaId={7} />);
  await screen.findByRole("navigation");
  await userEvent.click(screen.getByRole("button", { name: "Próxima ›" }));

  rerender(<PautaDoDiaSection programaId={8} />);
  expect(await screen.findByRole("navigation")).toHaveTextContent("Página 1 de 2");
  expect(screen.getByText("Assunto 1")).toBeInTheDocument();
  expect(api).toHaveBeenCalledWith("/topics/programas/8/pauta");
});
