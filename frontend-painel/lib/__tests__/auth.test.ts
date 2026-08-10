import { beforeEach, describe, expect, it } from "vitest";
import {
  clearToken,
  getEmailLembrado,
  getToken,
  limparEmailLembrado,
  setEmailLembrado,
  setToken,
} from "../auth";

beforeEach(() => {
  window.localStorage.clear();
});

describe("token", () => {
  it("devolve null quando nao ha token salvo", () => {
    expect(getToken()).toBeNull();
  });

  it("salva e le o token", () => {
    setToken("meu-token-jwt");
    expect(getToken()).toBe("meu-token-jwt");
  });

  it("limpa o token", () => {
    setToken("meu-token-jwt");
    clearToken();
    expect(getToken()).toBeNull();
  });
});

describe("email lembrado", () => {
  it("devolve null quando nao ha email salvo", () => {
    expect(getEmailLembrado()).toBeNull();
  });

  it("salva e le o email lembrado", () => {
    setEmailLembrado("user@example.com");
    expect(getEmailLembrado()).toBe("user@example.com");
  });

  it("limpa o email lembrado", () => {
    setEmailLembrado("user@example.com");
    limparEmailLembrado();
    expect(getEmailLembrado()).toBeNull();
  });
});
