import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import VoiceSelect from "../VoiceSelect";

function respostaJson(body: unknown) {
  return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
}

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function mockFetchPadrao({ plano = "starter" }: { plano?: string } = {}) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url.includes("/tts/voices")) {
        return respostaJson([
          { voz_id: "voz-1", nome: "Rachel", genero: "feminina", descricao: "Calma", preview_url: "https://example.com/rachel.mp3" },
        ]);
      }
      if (url.includes("/auth/me")) {
        return respostaJson({ plano });
      }
      if (url.includes("/tts/vozes-clonadas")) {
        return respostaJson([]);
      }
      return respostaJson({});
    })
  );
}

describe("VoiceSelect", () => {
  it("carrega e lista as vozes do catalogo", async () => {
    mockFetchPadrao();
    render(<VoiceSelect value={null} onChange={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText("Rachel — feminina, Calma")).toBeInTheDocument();
    });
  });

  it("chama onChange ao selecionar uma voz", async () => {
    mockFetchPadrao();
    const onChange = vi.fn();
    render(<VoiceSelect value={null} onChange={onChange} />);

    await waitFor(() => screen.getByText("Rachel — feminina, Calma"));
    await userEvent.click(screen.getByRole("radio", { name: /Rachel/ }));

    expect(onChange).toHaveBeenCalledWith("voz-1");
  });

  it("nao mostra link de clonagem pra plano starter", async () => {
    mockFetchPadrao({ plano: "starter" });
    render(<VoiceSelect value={null} onChange={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText(/Clonar sua própria voz/)).toBeInTheDocument();
    });
    expect(screen.queryByText("🎙️ Clonar uma voz")).not.toBeInTheDocument();
  });

  it("mostra botao de clonagem pra plano growth", async () => {
    mockFetchPadrao({ plano: "growth" });
    render(<VoiceSelect value={null} onChange={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText("🎙️ Clonar uma voz")).toBeInTheDocument();
    });
  });

  it("mostra player de amostra pra voz do catalogo com preview_url", async () => {
    mockFetchPadrao();
    const { container } = render(<VoiceSelect value={null} onChange={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText("Rachel — feminina, Calma")).toBeInTheDocument();
    });
    expect(container.querySelector('audio[src="https://example.com/rachel.mp3"]')).toBeInTheDocument();
  });

  it("nao mostra player quando a voz nao tem preview_url", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.includes("/tts/voices")) {
          return respostaJson([{ voz_id: "voz-2", nome: "Adam", genero: "masculina", descricao: "Seria", preview_url: null }]);
        }
        if (url.includes("/auth/me")) return respostaJson({ plano: "starter" });
        if (url.includes("/tts/vozes-clonadas")) return respostaJson([]);
        return respostaJson({});
      })
    );
    const { container } = render(<VoiceSelect value={null} onChange={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText("Adam — masculina, Seria")).toBeInTheDocument();
    });
    expect(container.querySelector("audio")).not.toBeInTheDocument();
  });

  it("lista vozes clonadas da conta num grupo separado", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.includes("/tts/voices")) return respostaJson([]);
        if (url.includes("/auth/me")) return respostaJson({ plano: "growth" });
        if (url.includes("/tts/vozes-clonadas")) {
          return respostaJson([{ id: 1, nome: "Minha Voz", voz_id: "voz-clonada-1" }]);
        }
        return respostaJson({});
      })
    );
    render(<VoiceSelect value={null} onChange={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText("Minha Voz")).toBeInTheDocument();
    });
  });

  it("mostra player de amostra pra voz clonada com preview_url", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.includes("/tts/voices")) return respostaJson([]);
        if (url.includes("/auth/me")) return respostaJson({ plano: "growth" });
        if (url.includes("/tts/vozes-clonadas")) {
          return respostaJson([
            { id: 1, nome: "Minha Voz", voz_id: "voz-clonada-1", preview_url: "https://example.com/minha-voz.mp3" },
          ]);
        }
        return respostaJson({});
      })
    );
    const { container } = render(<VoiceSelect value={null} onChange={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText("Minha Voz")).toBeInTheDocument();
    });
    expect(container.querySelector('audio[src="https://example.com/minha-voz.mp3"]')).toBeInTheDocument();
  });

  it("renomeia uma voz clonada", async () => {
    const fetchMock = vi.fn((url: string, options?: RequestInit) => {
      if (url.includes("/tts/voices")) return respostaJson([]);
      if (url.includes("/auth/me")) return respostaJson({ plano: "growth" });
      if (url.includes("/tts/vozes-clonadas/1") && options?.method === "PATCH") {
        return respostaJson({ id: 1, nome: "Novo Nome", voz_id: "voz-clonada-1", preview_url: null });
      }
      if (url.includes("/tts/vozes-clonadas")) {
        return respostaJson([{ id: 1, nome: "Minha Voz", voz_id: "voz-clonada-1", preview_url: null }]);
      }
      return respostaJson({});
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<VoiceSelect value={null} onChange={() => {}} />);

    await waitFor(() => screen.getByText("Minha Voz"));
    await userEvent.click(screen.getByTitle("Renomear"));
    const input = screen.getByRole("textbox");
    await userEvent.clear(input);
    await userEvent.type(input, "Novo Nome");
    await userEvent.click(screen.getByText("Salvar"));

    await waitFor(() => {
      expect(screen.getByText("Novo Nome")).toBeInTheDocument();
    });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/tts/vozes-clonadas/1"),
      expect.objectContaining({ method: "PATCH", body: JSON.stringify({ nome: "Novo Nome" }) })
    );
  });

  it("exclui uma voz clonada apos confirmacao", async () => {
    vi.stubGlobal("confirm", vi.fn(() => true));
    const fetchMock = vi.fn((url: string, options?: RequestInit) => {
      if (url.includes("/tts/voices")) return respostaJson([]);
      if (url.includes("/auth/me")) return respostaJson({ plano: "growth" });
      if (url.includes("/tts/vozes-clonadas/1") && options?.method === "DELETE") {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      if (url.includes("/tts/vozes-clonadas")) {
        return respostaJson([{ id: 1, nome: "Minha Voz", voz_id: "voz-clonada-1", preview_url: null }]);
      }
      return respostaJson({});
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<VoiceSelect value={null} onChange={() => {}} />);

    await waitFor(() => screen.getByText("Minha Voz"));
    await userEvent.click(screen.getByTitle("Excluir"));

    await waitFor(() => {
      expect(screen.queryByText("Minha Voz")).not.toBeInTheDocument();
    });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/tts/vozes-clonadas/1"),
      expect.objectContaining({ method: "DELETE" })
    );
  });

  it("nao exclui voz clonada se o usuario cancelar a confirmacao", async () => {
    vi.stubGlobal("confirm", vi.fn(() => false));
    const fetchMock = vi.fn((url: string) => {
      if (url.includes("/tts/voices")) return respostaJson([]);
      if (url.includes("/auth/me")) return respostaJson({ plano: "growth" });
      if (url.includes("/tts/vozes-clonadas")) {
        return respostaJson([{ id: 1, nome: "Minha Voz", voz_id: "voz-clonada-1", preview_url: null }]);
      }
      return respostaJson({});
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<VoiceSelect value={null} onChange={() => {}} />);

    await waitFor(() => screen.getByText("Minha Voz"));
    await userEvent.click(screen.getByTitle("Excluir"));

    expect(screen.getByText("Minha Voz")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalledWith(expect.stringContaining("/tts/vozes-clonadas/1"), expect.anything());
  });
});
