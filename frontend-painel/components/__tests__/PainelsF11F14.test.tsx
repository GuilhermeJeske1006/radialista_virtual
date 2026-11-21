import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

const apiFetch = vi.fn();
vi.mock("../../lib/api", async () => {
  const real = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return { ...real, apiFetch: (...args: unknown[]) => apiFetch(...args) };
});

import { ApiError } from "../../lib/api";
import FalasRevisaoPanel from "../FalasRevisaoPanel";
import CortesProgramaPanel from "../CortesProgramaPanel";
import PecasReservaSection from "../PecasReservaSection";

beforeEach(() => apiFetch.mockReset());
afterEach(() => cleanup());

const FALA = {
  id: 7, categoria: "plantao", texto: "Texto original da fala.", rota: "revisao", motivo: "revisao",
  estado: "aguardando_revisao", criado_em: "2026-08-10T15:00:00Z", prazo_em: "2026-08-10T15:20:00Z",
};

describe("FalasRevisaoPanel (F12)", () => {
  it("lista as falas aguardando e aprova, removendo da lista", async () => {
    apiFetch.mockResolvedValueOnce([FALA]).mockResolvedValueOnce({ id: 7, estado: "aprovada" });
    render(<FalasRevisaoPanel programaId={3} />);
    expect(await screen.findByText("Texto original da fala.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Aprovar" }));
    await waitFor(() => expect(screen.queryByText("Texto original da fala.")).toBeNull());
    expect(apiFetch).toHaveBeenCalledWith("/config/programas/3/falas-revisao/7/aprovar", { method: "POST" });
  });

  it("fora do prazo (409) mostra aviso e recarrega", async () => {
    apiFetch
      .mockResolvedValueOnce([FALA])
      .mockRejectedValueOnce(new ApiError(409, "fora do prazo"))
      .mockResolvedValueOnce([]);
    render(<FalasRevisaoPanel programaId={3} />);
    await screen.findByText("Texto original da fala.");
    fireEvent.click(screen.getByRole("button", { name: "Rejeitar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("passou do prazo");
  });

  it("sem falas mostra o estado vazio", async () => {
    apiFetch.mockResolvedValueOnce([]);
    render(<FalasRevisaoPanel programaId={3} />);
    expect(await screen.findByText("Nenhuma fala aguardando revisão.")).toBeTruthy();
  });
});

describe("CortesProgramaPanel (F14)", () => {
  it("mostra os cortes com a sequência de tipos", async () => {
    apiFetch.mockResolvedValueOnce([{ ordem_inicio: 1, ordem_fim: 3, eventos: 3, tipos: ["fala", "musica", "fala"] }]);
    render(<CortesProgramaPanel programaId={3} />);
    expect(await screen.findByText(/Eventos 1–3 \(3\): fala → musica → fala/)).toBeTruthy();
  });
});

describe("PecasReservaSection (F11 item 3)", () => {
  it("peça não aprovada mostra o botão Aprovar; alterar o texto bloqueia a aprovação até salvar", async () => {
    apiFetch.mockResolvedValueOnce([{ id: 1, tipo: "fonte", texto: "Seguimos sem a fonte.", aprovada: false }]);
    render(<PecasReservaSection programaId={3} />);
    const aprovar = await screen.findByRole("button", { name: "Aprovar" });
    expect((aprovar as HTMLButtonElement).disabled).toBe(false);
    fireEvent.change(screen.getByLabelText("Texto da peça 1"), { target: { value: "Outro texto." } });
    expect((screen.getByRole("button", { name: "Aprovar" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("adiciona uma peça e salva a lista completa", async () => {
    apiFetch
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([{ id: 2, tipo: "estouro", texto: "Já voltamos.", aprovada: false }]);
    render(<PecasReservaSection programaId={3} />);
    await screen.findByText("Peças de reserva");
    fireEvent.change(screen.getByLabelText("Tipo da nova peça"), { target: { value: "estouro" } });
    fireEvent.change(screen.getByLabelText("Texto da nova peça"), { target: { value: "Já voltamos." } });
    fireEvent.click(screen.getByRole("button", { name: "Adicionar peça" }));
    fireEvent.click(screen.getByRole("button", { name: "Salvar peças" }));
    await waitFor(() =>
      expect(apiFetch).toHaveBeenLastCalledWith(
        "/config/programas/3/pecas-reserva",
        expect.objectContaining({ method: "PUT", body: JSON.stringify([{ tipo: "estouro", texto: "Já voltamos." }]) }),
      ),
    );
  });
});
