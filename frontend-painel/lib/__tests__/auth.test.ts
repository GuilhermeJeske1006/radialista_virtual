import { beforeEach, describe, expect, it } from "vitest";
import { getEmailLembrado, limparEmailLembrado, setEmailLembrado } from "../auth";

beforeEach(() => {
  window.localStorage.clear();
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
