import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

const apiFetch = vi.fn();
vi.mock("../../lib/api", async () => {
  const real = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return { ...real, apiFetch: (...args: unknown[]) => apiFetch(...args) };
});

import GlossarioPronunciaRadio from "../GlossarioPronunciaRadio";

beforeEach(() => apiFetch.mockReset());
afterEach(() => cleanup());

describe("GlossarioPronunciaRadio (F9)", () => {
  it("edita, adiciona e remove termos; só termo com pronúncia vai para o glossário", () => {
    const onChange = vi.fn();
    render(<GlossarioPronunciaRadio valor={{ Kelly: "Quéli" }} onChange={onChange} />);
    expect((screen.getByLabelText("Pronúncia 1") as HTMLInputElement).value).toBe("Quéli");

    fireEvent.change(screen.getByLabelText("Pronúncia 1"), { target: { value: "Quéli!" } });
    expect(onChange).toHaveBeenLastCalledWith({ Kelly: "Quéli!" });

    fireEvent.click(screen.getByRole("button", { name: "Adicionar termo" }));
    fireEvent.change(screen.getByLabelText("Termo 2"), { target: { value: "AC/DC" } });
    expect(onChange).toHaveBeenLastCalledWith({ Kelly: "Quéli!" });
    fireEvent.change(screen.getByLabelText("Pronúncia 2"), { target: { value: "êi ci di ci" } });
    expect(onChange).toHaveBeenLastCalledWith({ Kelly: "Quéli!", "AC/DC": "êi ci di ci" });

    fireEvent.click(screen.getAllByRole("button", { name: "Remover" })[0]);
    expect(onChange).toHaveBeenLastCalledWith({ "AC/DC": "êi ci di ci" });
  });

  it("sugere termos dos textos da rádio sem repetir os que já estão na lista", async () => {
    apiFetch.mockResolvedValueOnce({ termos: ["kelly", "Kiwi", "FM"] });
    const onChange = vi.fn();
    render(<GlossarioPronunciaRadio valor={{ Kelly: "Quéli" }} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Sugerir termos" }));

    expect(await screen.findByRole("status")).toHaveTextContent("2 termo(s) sugerido(s)");
    expect(apiFetch).toHaveBeenCalledWith("/config/radio/glossario/sugestoes");
    expect((screen.getByLabelText("Termo 2") as HTMLInputElement).value).toBe("Kiwi");
    expect((screen.getByLabelText("Termo 3") as HTMLInputElement).value).toBe("FM");
    expect(screen.queryByLabelText("Termo 4")).toBeNull();
  });

  it("avisa quando não há termo novo", async () => {
    apiFetch.mockResolvedValueOnce({ termos: [] });
    render(<GlossarioPronunciaRadio valor={{}} onChange={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Sugerir termos" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Nenhum termo novo");
  });
});
