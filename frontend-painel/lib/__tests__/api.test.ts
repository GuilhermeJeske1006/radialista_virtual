import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiFetch, apiFetchBlob, apiFetchForm, ApiError } from "../api";

function respostaJson(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("apiFetch", () => {
  it("manda a sessao via cookie (credentials: include), sem Authorization", async () => {
    const fetchMock = vi.fn().mockResolvedValue(respostaJson({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("/algo");

    const [, options] = fetchMock.mock.calls[0];
    expect(options.credentials).toBe("include");
    expect(options.headers["Authorization"]).toBeUndefined();
  });

  it("devolve o corpo json em requisicao com sucesso", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(respostaJson({ nome: "Ze" })));
    const resultado = await apiFetch<{ nome: string }>("/algo");
    expect(resultado.nome).toBe("Ze");
  });

  it("devolve undefined em resposta 204", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    const resultado = await apiFetch("/algo");
    expect(resultado).toBeUndefined();
  });

  it("lanca ApiError com a mensagem do campo detail em erro", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(respostaJson({ detail: "Credenciais invalidas" }, 400)));
    await expect(apiFetch("/algo")).rejects.toMatchObject({ message: "Credenciais invalidas", status: 400 });
  });

  it("lanca ApiError com o texto cru quando o corpo nao e json", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("erro interno", { status: 500 }))
    );
    await expect(apiFetch("/algo")).rejects.toMatchObject({ message: "erro interno", status: 500 });
  });

  it("em 401 lanca ApiError", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 401 })));

    await expect(apiFetch("/algo")).rejects.toBeInstanceOf(ApiError);
  });
});

describe("apiFetchForm", () => {
  it("nao seta content-type manualmente e manda credentials: include", async () => {
    const fetchMock = vi.fn().mockResolvedValue(respostaJson({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    const formData = new FormData();
    formData.append("nome", "Ze");
    await apiFetchForm("/upload", formData);

    const [, options] = fetchMock.mock.calls[0];
    expect(options.headers).toBeUndefined();
    expect(options.credentials).toBe("include");
    expect(options.body).toBe(formData);
  });

  it("usa o metodo informado", async () => {
    const fetchMock = vi.fn().mockResolvedValue(respostaJson({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetchForm("/upload/1", new FormData(), "PUT");
    const [, options] = fetchMock.mock.calls[0];
    expect(options.method).toBe("PUT");
  });
});

describe("apiFetchBlob", () => {
  it("devolve um blob em requisicao com sucesso", async () => {
    const blob = new Blob(["audio-bytes"], { type: "audio/mpeg" });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(blob, { status: 200, headers: { "content-type": "audio/mpeg" } })
      )
    );

    const resultado = await apiFetchBlob("/audio");
    expect(resultado.size).toBeGreaterThan(0);
    expect(resultado.type).toBe("audio/mpeg");
  });

  it("lanca ApiError em falha", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("nao encontrado", { status: 404 })));
    await expect(apiFetchBlob("/audio")).rejects.toBeInstanceOf(ApiError);
  });
});
