import { beforeEach, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import TarifasModelos from "../TarifasModelos";

const api = vi.hoisted(() => vi.fn());
vi.mock("../../lib/api", () => ({ apiFetch: api }));
vi.mock("../VoiceSelect", () => ({
  default: ({ onChange }: { onChange: (v: string) => void }) => <button type="button" onClick={() => onChange("voz-1")}>Escolher voz</button>,
}));

const tarifa = { moeda: "USD", cambio: "5.5", acrescimo: "100", descricao: "Voz expressiva", limitacoes: "", exemplos: [] };
const catalogo = [
  { ...tarifa, id: "t1", tipo: "llm", modelo: "claude-opus-5", unidades: { entrada: { preco: "5", divisor: "1000000" } } },
  { ...tarifa, id: "t2", tipo: "tts", modelo: "eleven_v3", unidades: { caracteres: { preco: "0.10", divisor: "1000" } } },
];

beforeEach(() => {
  api.mockReset();
  api.mockImplementation((path: string) => {
    if (path === "/billing/catalogo-modelos") return Promise.resolve(catalogo);
    if (path === "/billing/amostras/estimar") return Promise.resolve({ limite_brl: 0.0123, autorizacao: "jwt" });
    return Promise.reject(new Error("inesperado " + path));
  });
});

it("mostra nomes e tarifas legíveis, sem ids técnicos", async () => {
  render(<TarifasModelos />);
  const card = (await screen.findByRole("heading", { name: "ElevenLabs v3" })).closest("article")!;
  expect(within(card).getByText(/US\$\s0,10 por 1\.000 caracteres/)).toBeInTheDocument();
  expect(screen.queryByText("eleven_v3")).not.toBeInTheDocument();
});

it("amostra de voz usa o seletor de vozes em vez de ID digitado", async () => {
  render(<TarifasModelos />);
  await userEvent.selectOptions(await screen.findByRole("combobox", { name: "Modelo da amostra" }), "t2");
  expect(screen.getByRole("button", { name: "Consultar estimativa" })).toBeDisabled();
  await userEvent.type(screen.getByRole("textbox", { name: "Texto a ser locutado" }), "Bom dia");
  await userEvent.click(screen.getByRole("button", { name: "Escolher voz" }));
  await userEvent.click(screen.getByRole("button", { name: "Consultar estimativa" }));
  await waitFor(() => expect(api).toHaveBeenCalledWith("/billing/amostras/estimar", {
    method: "POST", body: JSON.stringify({ tipo: "tts", modelo: "eleven_v3", texto: "Bom dia", voz_id: "voz-1" }) }));
  expect(await screen.findByText(/0,0123/)).toBeInTheDocument();
});

it("catálogo vazio explica quando as tarifas serão liberadas", async () => {
  api.mockResolvedValue([]);
  render(<TarifasModelos />);
  expect(await screen.findByText(/liberado após a confirmação das tarifas/)).toBeInTheDocument();
  expect(screen.queryByRole("combobox", { name: "Modelo da amostra" })).not.toBeInTheDocument();
});
