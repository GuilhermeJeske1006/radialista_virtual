import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import InstalarAppAviso from "../InstalarAppAviso";
import { CAPTURA_INSTALACAO_SCRIPT, detectarNavegador } from "../../../lib/instalarApp";

function modoApp(ativo: boolean) {
  vi.stubGlobal("matchMedia", (q: string) => ({ matches: ativo && q.includes("standalone"), media: q }));
}

function eventoInstalacao(outcome: "accepted" | "dismissed") {
  const evento = new Event("beforeinstallprompt") as Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> };
  evento.prompt = vi.fn(() => Promise.resolve());
  evento.userChoice = Promise.resolve({ outcome });
  return evento;
}

beforeEach(() => {
  localStorage.clear();
  window.__locufyInstalar = null;
  modoApp(false);
  // mesmo script que o layout injeta -- captura o evento antes do React montar
  new Function(CAPTURA_INSTALACAO_SCRIPT)();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("InstalarAppAviso", () => {
  it("usa o evento capturado antes da montagem e instala com um clique", async () => {
    const evento = eventoInstalacao("accepted");
    window.dispatchEvent(evento);
    render(<InstalarAppAviso />);

    fireEvent.click(await screen.findByRole("button", { name: "Instalar Locufy" }));
    expect(evento.prompt).toHaveBeenCalledTimes(1);
    expect(await screen.findByRole("status")).toHaveTextContent(/Locufy instalado/);
  });

  it("evento que chega depois da montagem também mostra o botão", async () => {
    render(<InstalarAppAviso />);
    expect(screen.queryByRole("button", { name: "Instalar Locufy" })).toBeNull();

    await act(async () => { window.dispatchEvent(eventoInstalacao("dismissed")); });
    expect(screen.getByRole("button", { name: "Instalar Locufy" })).toBeTruthy();
  });

  it("recusado no prompt: some o botão e mostra o passo a passo manual", async () => {
    window.dispatchEvent(eventoInstalacao("dismissed"));
    vi.spyOn(navigator, "userAgent", "get").mockReturnValue("Mozilla/5.0 Chrome/140.0 Safari/537.36");
    render(<InstalarAppAviso />);

    await act(async () => { fireEvent.click(await screen.findByRole("button", { name: "Instalar Locufy" })); });
    expect(screen.queryByRole("button", { name: "Instalar Locufy" })).toBeNull();
    expect(screen.getByText(/ícone de instalar no fim da barra de endereço/)).toBeTruthy();
  });

  it("aberto como app instalado: não mostra nada", () => {
    modoApp(true);
    const { container } = render(<InstalarAppAviso />);
    expect(container).toBeEmptyDOMElement();
  });

  it("'Agora não' esconde e lembra na próxima visita", async () => {
    const { unmount } = render(<InstalarAppAviso />);
    fireEvent.click(await screen.findByRole("button", { name: "Agora não" }));
    expect(screen.queryByText("Deixe a rádio tocar sozinha")).toBeNull();

    unmount();
    const { container } = render(<InstalarAppAviso />);
    expect(container).toBeEmptyDOMElement();
  });

  it("Firefox sem instalação: ensina a liberar a reprodução automática do site", async () => {
    vi.spyOn(navigator, "userAgent", "get").mockReturnValue("Mozilla/5.0 (Macintosh) Gecko/20100101 Firefox/130.0");
    render(<InstalarAppAviso />);
    expect(await screen.findByText(/Reprodução automática > Permitir áudio e vídeo/)).toBeTruthy();
  });
});

describe("detectarNavegador", () => {
  it.each([
    ["Mozilla/5.0 Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0", "edge"],
    ["Mozilla/5.0 Chrome/140.0.0.0 Safari/537.36", "chrome"],
    ["Mozilla/5.0 Gecko/20100101 Firefox/130.0", "firefox"],
    ["Mozilla/5.0 (Macintosh) Version/18.0 Safari/605.1.15", "safari"],
  ])("%s -> %s", (ua, esperado) => {
    expect(detectarNavegador(ua)).toBe(esperado);
  });
});
