import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import VozConfigModal from "../VozConfigModal";
import { apiFetch } from "../../lib/api";
vi.mock("../../lib/api", async (original) => ({ ...await original<typeof import("../../lib/api")>(), apiFetch: vi.fn() }));
const config = { modelo: null, perfil: "atual", formato: "mp3_44100_128", pronuncias: {}, categoria: "professional", idioma: "pt", sotaque: null, requer_verificacao: false };
beforeEach(() => { vi.clearAllMocks(); vi.mocked(apiFetch).mockResolvedValue(config); });
it("salva modelo, interpretação e aliases para a voz selecionada", async () => {
  const close = vi.fn();
  render(<VozConfigModal vozId={null} onFechar={close} onAtualizada={vi.fn()} />);
  await screen.findByText(/Tipo: profissional/);
  await userEvent.selectOptions(screen.getByLabelText("Modelo de voz"), "eleven_v3");
  await userEvent.selectOptions(screen.getByLabelText("Interpretação"), "natural");
  await userEvent.type(screen.getByLabelText("Pronúncias de nomes e marcas"), "Locufy = Locufai");
  await userEvent.click(screen.getByText("Salvar ajustes"));
  await waitFor(() => expect(close).toHaveBeenCalled());
  expect(apiFetch).toHaveBeenCalledWith("/tts/configuracao-voz/padrao", { method: "PATCH", body: JSON.stringify({ modelo: "eleven_v3", perfil: "natural", formato: "mp3_44100_128", pronuncias: { Locufy: "Locufai" } }) });
});
it("recusa alias inválido antes de enviar", async () => {
  render(<VozConfigModal vozId="minha-voz" onFechar={vi.fn()} onAtualizada={vi.fn()} />);
  await screen.findByText(/Tipo: profissional/);
  await userEvent.type(screen.getByLabelText("Pronúncias de nomes e marcas"), "linha inválida");
  await userEvent.click(screen.getByText("Salvar ajustes"));
  expect(screen.getByRole("alert")).toHaveTextContent("termo = pronúncia");
  expect(apiFetch).toHaveBeenCalledTimes(1);
});
