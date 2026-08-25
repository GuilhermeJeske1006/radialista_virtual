import { Programa } from "./types";

export const MINUTOS_DIA = 1440;

export function horarioParaMinutos(horario: string): number {
  const [h, m] = horario.split(":").map(Number);
  return h * 60 + m;
}

// "YYYY-MM-DD" -> indice 0=Seg..6=Dom, mesmo indice de DIAS_SEMANA_LABEL/Programa.dias_semana
// (que ja bate com datetime.weekday() do Python). new Date(y,m-1,d) usa o fuso local do
// navegador de proposito -- evita o offset de 1 dia que "YYYY-MM-DD" direto no Date() causaria
// (interpretado como UTC meia-noite). getDay() e' 0=Dom..6=Sab, por isso o (+6)%7.
export function dataEspecificaParaDiaSemana(data: string): number {
  const [ano, mes, dia] = data.split("-").map(Number);
  const diaJs = new Date(ano, mes - 1, dia).getDay();
  return (diaJs + 6) % 7;
}

export type SegmentoGrade = { diaSemana: number; inicioMin: number; fimMin: number };

function segmentosDoDia(diaSemana: number, inicioMin: number, fimMin: number): SegmentoGrade[] {
  if (inicioMin <= fimMin) {
    return [{ diaSemana, inicioMin, fimMin }];
  }
  // overnight (ex.: 22:00-06:00) -- aproximacao visual de template semanal: o resto da
  // faixa cai no dia seguinte da grade, nao numa data real (a tela nao e' um calendario
  // com datas, e' uma grade recorrente).
  return [
    { diaSemana, inicioMin, fimMin: MINUTOS_DIA },
    { diaSemana: (diaSemana + 1) % 7, inicioMin: 0, fimMin },
  ];
}

// Em quais colunas (dias) e faixas de minutos desenhar o programa na grade semanal.
export function segmentosDoPrograma(programa: Programa): SegmentoGrade[] {
  const inicioMin = horarioParaMinutos(programa.horario_inicio);
  const fimMin = horarioParaMinutos(programa.horario_fim);

  if (programa.data_especifica) {
    return segmentosDoDia(dataEspecificaParaDiaSemana(programa.data_especifica), inicioMin, fimMin);
  }

  const dias = programa.dias_semana.length > 0 ? programa.dias_semana : [0, 1, 2, 3, 4, 5, 6];
  return dias.flatMap((dia) => segmentosDoDia(dia, inicioMin, fimMin));
}

export type CorGrade = { borda: string; fundo: string; texto: string };

// Unicos accent colors definidos em app/globals.css. Cobre ate 5 radialistas (limite do
// plano mais caro, PLANOS["professional"].agentes = 5, ver backend/app/planos.py).
const PALETA: CorGrade[] = [
  { borda: "border-amber/50", fundo: "bg-amber/15", texto: "text-amber" },
  { borda: "border-teal/50", fundo: "bg-teal/15", texto: "text-teal" },
  { borda: "border-rust/50", fundo: "bg-rust/15", texto: "text-rust" },
  { borda: "border-amber-dim/50", fundo: "bg-amber-dim/15", texto: "text-amber-dim" },
  { borda: "border-paper/50", fundo: "bg-paper/15", texto: "text-paper" },
];

export function corPorIndice(indice: number): CorGrade {
  return PALETA[indice % PALETA.length];
}
