import { describe, expect, it } from "vitest";
import { consumoMensalEstimado, exibicoesPorMes, horasPorDia, horasPorMes, nomeModelo, reaisPreciso } from "../combinacoes";

const programa = { horario_inicio: "06:00:00", horario_fim: "09:00:00", dias_semana: [], data_especifica: null };
const combinacao = {
  id: "premium", nome: "Premium", descricao: "", limitacoes: "", recomendada: true,
  modelo_texto: "claude-opus-5", modelo_voz: "eleven_v3", preco_hora_brl: 2,
};

describe("estimativa mensal pelo horário do programa", () => {
  it("duração do dia, inclusive atravessando a meia-noite", () => {
    expect(horasPorDia(programa)).toBe(3);
    expect(horasPorDia({ ...programa, horario_inicio: "22:00:00", horario_fim: "02:00:00" })).toBe(4);
    expect(horasPorDia({ ...programa, horario_inicio: "10:30", horario_fim: "11:00" })).toBe(0.5);
  });

  it("nenhum dia marcado = todos os dias; data específica = uma exibição", () => {
    expect(exibicoesPorMes(programa)).toBe(30);
    expect(exibicoesPorMes({ ...programa, dias_semana: [1, 2, 3, 4, 5] })).toBeCloseTo(21.43, 2);
    expect(exibicoesPorMes({ ...programa, dias_semana: [1], data_especifica: "2026-10-01" })).toBe(1);
  });

  it("consumo = preço por hora × horas no mês", () => {
    expect(horasPorMes(programa)).toBe(90);
    expect(consumoMensalEstimado(combinacao, programa)).toBe(180);
  });
});

it("nomes legíveis e valores pequenos com precisão", () => {
  expect(nomeModelo("eleven_flash_v2_5")).toBe("ElevenLabs Flash 2.5");
  expect(nomeModelo("desconhecido")).toBe("desconhecido");
  expect(reaisPreciso(0.0123)).toMatch(/0,0123/);
  expect(reaisPreciso(1.5)).toMatch(/1,50/);
});
