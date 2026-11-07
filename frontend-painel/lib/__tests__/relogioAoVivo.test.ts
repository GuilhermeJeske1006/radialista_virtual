import { describe, expect, it } from "vitest";
import { estimarDuracaoSegmento, inicioAEnviar, medirDesvio, proximoInicioBruto } from "../relogioAoVivo";

describe("horário previsto no ao vivo", () => {
  it("encadeia a cadeia bruta pela pausa e pela duração prevista do backend", () => {
    const inicio = Date.UTC(2026, 10, 10, 15, 0, 0);
    const primeiro = { fala: "Boa tarde", duracao_prevista_s: 28.5, pausa_antes_ms: 0 };
    const segundo = { fala: "", video_id: "v1", duracao_prevista_s: 214, pausa_antes_ms: 350 };
    const depoisDoPrimeiro = proximoInicioBruto(inicio, primeiro);
    expect(depoisDoPrimeiro - inicio).toBe(28_500);
    expect(proximoInicioBruto(depoisDoPrimeiro, segundo) - inicio).toBe(28_500 + 350 + 214_000);
    expect(proximoInicioBruto(inicio, { fala: "x", duracao_prevista_s: 1, pausa_antes_ms: 99_000 }) - inicio).toBe(6_000);
  });

  it("sem duracao_prevista_s (backend antigo ou fala local) estima por palavras e músicas", () => {
    expect(estimarDuracaoSegmento({ fala: "[animado] um dois três quatro cinco" })).toBe(2);
    expect(estimarDuracaoSegmento({
      fala: "um dois três quatro cinco",
      musicas: [{ video_id: "a", titulo: "A", inicio_segundos: 10, fim_segundos: 200 }, { video_id: "b", titulo: "B", duracao_segundos: 180 }],
    })).toBe(2 + 190 + 180);
    expect(estimarDuracaoSegmento({ fala: "", video_id: "v", inicio_segundos: 0, fim_segundos: 150 })).toBe(150);
  });

  it("corrige pelo desvio e nunca manda horário no passado", () => {
    const bruto = 1_000_000;
    expect(inicioAEnviar(bruto, 10_000, 900_000)).toBe(1_010_000);
    expect(inicioAEnviar(bruto, -500_000, 900_000)).toBe(900_000);
    expect(medirDesvio(bruto, bruto + 10_350, 350)).toBe(10_000);
    expect(medirDesvio(undefined, bruto, 0)).toBeNull();
  });
});
