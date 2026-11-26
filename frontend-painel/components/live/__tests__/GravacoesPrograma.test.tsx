import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import GravacoesPrograma from "../GravacoesPrograma";

const apiFetch = vi.fn();
const apiFetchDownload = vi.fn();
vi.mock("../../../lib/api", () => ({
  apiFetch: (...args: unknown[]) => apiFetch(...args),
  apiFetchDownload: (...args: unknown[]) => apiFetchDownload(...args),
}));

const gravacao = { id: 7, criado_em: "2026-11-26T15:00:00Z", tamanho_bytes: 25 * 1024 * 1024, escopo: "completo" };

beforeEach(() => {
  apiFetch.mockReset();
  apiFetchDownload.mockReset();
});
afterEach(() => cleanup());

describe("GravacoesPrograma", () => {
  it("não renderiza nem consulta sem programa", () => {
    const { container } = render(<GravacoesPrograma programaId={null} ativo={false} />);
    expect(container).toBeEmptyDOMElement();
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("lista as gravações do programa e baixa pelo endpoint autenticado", async () => {
    apiFetch.mockResolvedValue([gravacao]);
    apiFetchDownload.mockResolvedValue(undefined);
    render(<GravacoesPrograma programaId={3} ativo={false} />);

    const botao = await screen.findByRole("button", { name: /Baixar programa de .*\(25 MB\)/ });
    expect(apiFetch).toHaveBeenCalledWith("/live/programas/3/gravacoes");
    fireEvent.click(botao);
    expect(apiFetchDownload).toHaveBeenCalledWith("/live/programas/3/gravacoes/7/audio", "programa-3-7.mp3");
  });

  it("mostra estado vazio e erro de consulta", async () => {
    apiFetch.mockResolvedValueOnce([]);
    const { unmount } = render(<GravacoesPrograma programaId={3} ativo={false} />);
    expect(await screen.findByText("Nenhuma gravação arquivada.")).toBeInTheDocument();
    unmount();

    apiFetch.mockRejectedValueOnce(new Error("rede"));
    render(<GravacoesPrograma programaId={3} ativo={false} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível consultar as gravações.");
  });

  it("avisa quando o MP3 foi exportado mas a cópia não foi arquivada", async () => {
    apiFetch.mockResolvedValue([]);
    render(<GravacoesPrograma programaId={3} ativo />);
    await screen.findByText("Nenhuma gravação arquivada.");

    act(() => { window.dispatchEvent(new CustomEvent("gravacao-exportada", { detail: { arquivada: false } })); });
    expect(await screen.findByRole("alert")).toHaveTextContent(/não foi possível arquivar a cópia/);
  });

  it("recarrega a lista quando uma exportação é arquivada", async () => {
    apiFetch.mockResolvedValueOnce([]).mockResolvedValueOnce([gravacao]);
    render(<GravacoesPrograma programaId={3} ativo />);
    await screen.findByText("Nenhuma gravação arquivada.");

    act(() => { window.dispatchEvent(new CustomEvent("gravacao-exportada", { detail: { arquivada: true } })); });
    await waitFor(() => expect(screen.getByRole("button", { name: /Baixar programa/ })).toBeInTheDocument());
    expect(apiFetch).toHaveBeenCalledTimes(2);
  });

  it("falha de download vira alerta", async () => {
    apiFetch.mockResolvedValue([gravacao]);
    apiFetchDownload.mockRejectedValue(new Error("403"));
    render(<GravacoesPrograma programaId={3} ativo={false} />);
    fireEvent.click(await screen.findByRole("button", { name: /Baixar programa/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível baixar a gravação.");
  });
});
