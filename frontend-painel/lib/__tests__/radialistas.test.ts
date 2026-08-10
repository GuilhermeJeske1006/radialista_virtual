import { beforeEach, describe, expect, it } from "vitest";
import { getRadialistaAtualId, setRadialistaAtualId } from "../radialistas";

beforeEach(() => {
  window.localStorage.clear();
});

describe("getRadialistaAtualId", () => {
  it("devolve null quando nao ha id salvo", () => {
    expect(getRadialistaAtualId()).toBeNull();
  });

  it("devolve o id salvo como numero", () => {
    setRadialistaAtualId(42);
    expect(getRadialistaAtualId()).toBe(42);
  });
});
