import { expect, it } from "vitest";
import { formatarTarifa, resumirUnidades, rotuloEstadoFatura, rotuloFuncionalidade, rotuloStatusAssinatura } from "../rotulosConsumo";

it("traduz códigos do extrato e mantém desconhecidos visíveis", () => {
  expect(rotuloFuncionalidade("programa_ao_vivo")).toBe("Programa ao vivo");
  expect(rotuloFuncionalidade("novo_codigo")).toBe("novo_codigo");
  expect(rotuloEstadoFatura("pendente")).toBe("Pagamento pendente");
  expect(rotuloStatusAssinatura("inadimplente")).toBe("Pagamento pendente");
});

it("resume unidades sem as zeradas", () => {
  expect(resumirUnidades({ entrada: "1200", saida: "35", cache_write: "0", buscas: "0" }))
    .toBe("1.200 tokens de entrada · 35 tokens de saída");
  expect(resumirUnidades({ entrada: "0" })).toBe("—");
});

it("tarifa na moeda de origem com centavos de dólar", () => {
  expect(formatarTarifa("0.10", "USD")).toMatch(/US\$\s0,10/);
  expect(formatarTarifa("0.000005", "USD")).toMatch(/0,000005/);
});
