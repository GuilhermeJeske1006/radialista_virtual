import { cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAoVivoUnico } from "../aoVivoUnico";

// Canal em memoria: BroadcastChannel entrega pras OUTRAS instancias do mesmo nome, nunca pra
// quem postou -- e' esse comportamento que a regra "app tem prioridade" usa.
class CanalTeste {
  static abertos: CanalTeste[] = [];
  onmessage: ((e: { data: unknown }) => void) | null = null;
  constructor(public nome: string) { CanalTeste.abertos.push(this); }
  postMessage(data: unknown) {
    CanalTeste.abertos.filter((c) => c !== this && c.nome === this.nome).forEach((c) => c.onmessage?.({ data }));
  }
  close() { CanalTeste.abertos = CanalTeste.abertos.filter((c) => c !== this); }
}

function modoApp(ativo: boolean) {
  vi.stubGlobal("matchMedia", (q: string) => ({ matches: ativo && q.includes("standalone"), media: q }));
}

beforeEach(() => {
  CanalTeste.abertos = [];
  vi.stubGlobal("BroadcastChannel", CanalTeste);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("useAoVivoUnico", () => {
  it("aba do navegador cede quando o app instalado abre", () => {
    modoApp(false);
    const cederAba = vi.fn();
    renderHook(() => useAoVivoUnico(cederAba));

    modoApp(true);
    const cederApp = vi.fn();
    renderHook(() => useAoVivoUnico(cederApp));

    expect(cederAba).toHaveBeenCalledTimes(1);
    expect(cederApp).not.toHaveBeenCalled();
  });

  it("aba aberta com o app já no ar pergunta e cede", () => {
    modoApp(true);
    renderHook(() => useAoVivoUnico(vi.fn()));

    modoApp(false);
    const cederAba = vi.fn();
    renderHook(() => useAoVivoUnico(cederAba));
    expect(cederAba).toHaveBeenCalledTimes(1);
  });

  it("app instalado a partir desta aba: cede na hora (o navegador abre o app em seguida)", () => {
    modoApp(false);
    const cederAba = vi.fn();
    renderHook(() => useAoVivoUnico(cederAba));

    window.dispatchEvent(new Event("appinstalled"));
    expect(cederAba).toHaveBeenCalledTimes(1);
  });

  it("duas abas de navegador sem app: nenhuma cede", () => {
    modoApp(false);
    const a = vi.fn();
    const b = vi.fn();
    renderHook(() => useAoVivoUnico(a));
    renderHook(() => useAoVivoUnico(b));
    expect(a).not.toHaveBeenCalled();
    expect(b).not.toHaveBeenCalled();
  });
});
