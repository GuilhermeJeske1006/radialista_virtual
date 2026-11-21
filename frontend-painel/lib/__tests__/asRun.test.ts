import { beforeEach, describe, expect, it, vi } from "vitest";

const apiFetch = vi.fn();
vi.mock("../api", () => ({ apiFetch: (...args: unknown[]) => apiFetch(...args) }));

import { relatarAsRun } from "../asRun";

describe("relatarAsRun (F11 item 1)", () => {
  beforeEach(() => apiFetch.mockReset().mockResolvedValue({ id: 7, status: "confirmado" }));

  it("envia confirmado para o evento do programa", async () => {
    await relatarAsRun(3, 5, 7, "confirmado");
    expect(apiFetch).toHaveBeenCalledWith(
      "/live/3/programas/5/as-run/7",
      { method: "POST", body: JSON.stringify({ status: "confirmado" }) },
    );
  });

  it("sem id de evento não chama a API (resposta antiga, sem as-run)", async () => {
    expect(await relatarAsRun(3, 5, null, "confirmado")).toBeNull();
    expect(apiFetch).not.toHaveBeenCalled();
  });
});
