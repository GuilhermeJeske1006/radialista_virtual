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
        return respostaJson([{ voz_id: "voz-1", nome: "Rachel", genero: "feminina", descricao: "Calma" }]);
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
    await userEvent.selectOptions(screen.getByRole("combobox"), "voz-1");

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
});
