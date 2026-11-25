import { PERSONA_PADRAO, type Persona } from "./types";

export type EscalaPersona = "proximidade" | "formalidade" | "energia" | "humor" | "ritmo";

export const ESTILOS_PROGRAMA: Record<string, {
  nome: string;
  descricao: string;
  valores: Pick<Persona, EscalaPersona | "girias">;
}> = {
  equilibrado: {
    nome: "Equilibrado",
    descricao: "Conversa cordial, energia moderada e linguagem comum.",
    valores: { proximidade: 3, formalidade: 3, energia: 3, humor: 3, ritmo: 3, girias: "automatico" },
  },
  descontraido: {
    nome: "Descontraído",
    descricao: "Mais gírias, energia e humor para programas leves e musicais.",
    valores: { proximidade: 5, formalidade: 1, energia: 4, humor: 4, ritmo: 4, girias: "frequentes" },
  },
  jornalistico: {
    nome: "Jornalístico",
    descricao: "Linguagem sóbria, sem gírias, com precisão e seriedade.",
    valores: { proximidade: 3, formalidade: 5, energia: 2, humor: 1, ritmo: 3, girias: "evitar" },
  },
  acolhedor: {
    nome: "Acolhedor",
    descricao: "Conversa próxima e calma, com gírias leves ocasionais.",
    valores: { proximidade: 4, formalidade: 2, energia: 2, humor: 2, ritmo: 2, girias: "moderadas" },
  },
};

export function estiloSelecionado(persona: Persona): string {
  return Object.entries(ESTILOS_PROGRAMA).find(([, estilo]) =>
    (Object.keys(estilo.valores) as (EscalaPersona | "girias")[]).every((campo) =>
      (persona[campo] ?? PERSONA_PADRAO[campo]) === estilo.valores[campo],
    ),
  )?.[0] ?? "personalizado";
}
