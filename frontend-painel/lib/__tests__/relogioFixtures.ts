import { PresetRelogio, RelogioHora } from "../types";

// Espelho do preset A do backend (backend/app/live/relogios/A_musical_companhia.json).
const EVENTOS_A: [string, number, string, "obrigatorio" | "ajustavel", boolean][] = [
  ["abertura", 40, "Identidade e abertura", "obrigatorio", true],
  ["musica", 680, "Sequência musical A", "ajustavel", false],
  ["link", 35, "Link com um assunto", "ajustavel", false],
  ["musica", 685, "Sequência musical B", "ajustavel", false],
  ["intervalo", 180, "Intervalo", "obrigatorio", true],
  ["retorno", 60, "Retorno e participação", "ajustavel", false],
  ["musica", 720, "Sequência musical C", "ajustavel", false],
  ["curadoria", 60, "Agenda ou curadoria", "ajustavel", false],
  ["musica", 720, "Sequência musical D", "ajustavel", false],
  ["intervalo", 180, "Intervalo", "obrigatorio", true],
  ["musica", 210, "Música de fechamento", "ajustavel", false],
  ["passagem", 30, "Passagem de hora", "obrigatorio", true],
];

export function relogioA(): RelogioHora {
  let inicio = 0;
  return {
    versao: 1,
    preset: "A",
    em_feriado: "mesmo",
    eventos: EVENTOS_A.map(([tipo, duracao_s, rotulo, natureza, hard_time]) => {
      const evento = { inicio_s: inicio, duracao_s, tipo, rotulo, natureza, hard_time };
      inicio += duracao_s;
      return evento;
    }),
  };
}

export function presetsFixture(): PresetRelogio[] {
  const a = relogioA();
  const b: RelogioHora = { ...relogioA(), preset: "B" };
  const c: RelogioHora = { ...relogioA(), preset: "C" };
  const totais = { musica_s: 3015, fala_s: 225, intervalo_s: 360 };
  return [
    { id: "A", nome: "Musical com companhia", descricao: "", fonte: "", relogio: a, totais },
    { id: "B", nome: "Jornal/revista informativa", descricao: "", fonte: "", relogio: b, totais },
    { id: "C", nome: "Morning/variedades", descricao: "", fonte: "", relogio: c, totais },
  ];
}
