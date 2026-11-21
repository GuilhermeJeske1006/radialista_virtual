import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

const apiFetch = vi.fn();
vi.mock("../../lib/api", async () => {
  const real = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return { ...real, apiFetch: (...args: unknown[]) => apiFetch(...args) };
});

import RadialistasProgramaSection from "../RadialistasProgramaSection";

beforeEach(() => apiFetch.mockReset());
afterEach(() => cleanup());

const ROSTER = [
  { radio_config_id: 1, nome_locutor: "Ze", voz_id: null, papel: "Apresentador principal", comportamento: "", e_dono: true, papel_bancada: null },
];

it("escolher papel de bancada salva o campo junto com papel e comportamento", async () => {
  apiFetch
    .mockResolvedValueOnce(ROSTER)
    .mockResolvedValueOnce([{ id: 1, nome_locutor: "Ze", voz_id: null }])
    .mockResolvedValueOnce({ ...ROSTER[0], papel_bancada: "mediador" });
  render(<RadialistasProgramaSection programaId={3} />);
  const select = await screen.findByLabelText("Papel na bancada de Ze");
  fireEvent.change(select, { target: { value: "mediador" } });
  fireEvent.click(screen.getByRole("button", { name: "Salvar papel" }));
  await waitFor(() =>
    expect(apiFetch).toHaveBeenLastCalledWith(
      "/config/programas/3/radialistas/1",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({ papel: "Apresentador principal", comportamento: "", papel_bancada: "mediador" }),
      }),
    ),
  );
});
