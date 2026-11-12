import { describe, expect, it } from "vitest";

import type { DadoFala, LiveProgramResponse } from "../liveTypes";

// F5: `dados` é opcional na resposta do /proxima (painel antigo e respostas sem dado continuam válidos).
describe("LiveProgramResponse.dados", () => {
  it("aceita resposta sem dados e com dados", () => {
    const semDados: LiveProgramResponse = { tipo: "comentario", fala: "Oi." } as LiveProgramResponse;
    const dado: DadoFala = {
      id: "clima:campo-alegre", tipo: "clima", estado: "vencido", atualizado_em: "2026-11-10T15:00:00Z",
      valido_ate: "2026-11-10T16:00:00Z", alertas: ["ultima_leitura"],
    };
    const comDados: LiveProgramResponse = { ...semDados, dados: [dado] };
    expect(semDados.dados).toBeUndefined();
    expect(comDados.dados?.[0].estado).toBe("vencido");
  });
});
