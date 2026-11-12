export type PerfilEsportivo = {
  nome: string; regiao: string; clubes: string[]; campeonatos: string[]; modalidades: string[];
  fuso: string; estilo: string; identidade_sonora: string; participacao: boolean;
  distribuicao: Record<"regional" | "nacional" | "internacional" | "outras", number>;
};
export type FonteEsportiva = {
  id: number; revisao: number; dominio: string; organizacao: string; temas: string; regiao: string;
  idioma: string; acesso: "manual" | "api_autorizada" | "feed_autorizado" | "pagina_permitida";
  frequencia_permitida: string; prioridade: number; ultima_revisao: string; ativa: boolean; condicoes_uso: string;
};
export type FatoEsportivo = {
  id: string; texto: string; tipo: "noticia" | "agenda" | "resultado" | "escalacao" | "transferencia" | "analise" | "atemporal";
  evento: string; ocorrido_em: string; publicado_em: string; coletado_em: string; valido_ate: string;
  fonte_id: number; fonte_revisao: number; url: string; evidencia: string; origem_comum: string;
  confirmacao: "confirmado" | "provavel" | "negociacao" | "encerrado" | "contestado" | "adiado" | "cancelado";
  oficial: boolean; revisado: boolean; sensivel: boolean; revisao_sensivel: boolean;
  participantes: string[]; competicao: string; placar: number[];
};
export type BlocoEsportivo = {
  id: string; titulo: string; tipo: "abertura" | "noticias" | "agenda" | "analise" | "torcida" | "intervalo" | "encerramento";
  duracao_s: number; responsavel: string; transicao: string; opcional: boolean; reserva: string;
  texto: string; fato_ids: string[];
};
export type ConteudoEsportivo = {
  titulo: string; modelo: "boletim_2" | "boletim_3" | "programa_30"; exibicao_em: string;
  perfil: PerfilEsportivo; fatos: FatoEsportivo[]; blocos: BlocoEsportivo[];
};
export type EdicaoEsportiva = {
  id: number; programa_id: number; revisao: number; conteudo: ConteudoEsportivo; estado: string;
  alertas: string[]; alertas_audio: string[];
  audios: Record<string, { duracao_s: number; assinatura: string; audio_sha256: string }>;
  aprovacao_roteiro: { usuario_id: number; em: string } | null;
  aprovacao_audio: { usuario_id: number; em: string } | null;
  historico: { acao: string; usuario_id: number; em: string; revisao: number }[];
};
export type ResumoEdicao = Pick<EdicaoEsportiva, "id" | "estado"> & { titulo: string; exibicao_em: string };
export const rotuloEstado: Record<string, string> = {
  rascunho: "Rascunho", bloqueado: "Bloqueada", expirado: "Expirada", em_revisao: "Em revisão",
  roteiro_aprovado: "Roteiro aprovado", em_producao: "Áudio em produção", audio_pronto: "Áudio para revisão", aprovado: "Aprovada para exportar",
};
export function tempoEsportivo(segundos: number): string {
  return `${Math.floor(segundos / 60).toString().padStart(2, "0")}:${Math.round(segundos % 60).toString().padStart(2, "0")}`;
}
export function dataNoFuso(iso: string, fuso: string): string {
  const partes = new Intl.DateTimeFormat("sv-SE", { timeZone: fuso, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts(new Date(iso));
  const p = Object.fromEntries(partes.map((parte) => [parte.type, parte.value]));
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
}
// O horário pertence à emissora. Não depende do fuso do computador do operador.
export function isoNoFuso(local: string, fuso: string): string {
  const alvo = Date.parse(`${local}:00Z`);
  if (!Number.isFinite(alvo)) throw new Error("Informe uma data e um horário válidos.");
  let instante = alvo;
  for (let i = 0; i < 4; i++) {
    const visto = Date.parse(`${dataNoFuso(new Date(instante).toISOString(), fuso)}:00Z`);
    const diferenca = alvo - visto;
    if (!diferenca) return new Date(instante).toISOString();
    instante += diferenca;
  }
  throw new Error("Esse horário não existe no fuso da emissora. Escolha outro horário.");
}
export function novaFonte(): Omit<FonteEsportiva, "id" | "revisao"> {
  return { dominio: "", organizacao: "", temas: "Futebol", regiao: "Brasil", idioma: "pt-BR", acesso: "manual", frequencia_permitida: "Consulta editorial manual", prioridade: 1, ultima_revisao: new Date().toISOString().slice(0, 10), ativa: true, condicoes_uso: "" };
}

/** O modelo inicial acompanha a janela já cadastrada em Programas. */
export function modeloEsportivoDoPrograma(programa: { horario_inicio: string; horario_fim: string }): ConteudoEsportivo['modelo'] {
  const minutos = (hora: string) => Number(hora.slice(0, 2)) * 60 + Number(hora.slice(3, 5));
  const duracao = (minutos(programa.horario_fim) - minutos(programa.horario_inicio) + 1440) % 1440 || 1440;
  return duracao <= 2 ? 'boletim_2' : duracao < 30 ? 'boletim_3' : 'programa_30';
}

/** Próximo início na grade, calculado no fuso da emissora (0 = segunda-feira). */
export function proximaExibicaoEsportiva(programa: {
  horario_inicio: string; dias_semana: number[]; data_especifica?: string | null;
}, fuso: string, agora = new Date()): string {
  const dataHoje = dataNoFuso(agora.toISOString(), fuso).slice(0, 10);
  for (let dia = 0; dia < 8; dia++) {
    const data = new Date(`${dataHoje}T12:00:00Z`);
    data.setUTCDate(data.getUTCDate() + dia);
    const candidata = programa.data_especifica || data.toISOString().slice(0, 10);
    const diaSemana = (data.getUTCDay() + 6) % 7;
    if (!programa.data_especifica && programa.dias_semana.length && !programa.dias_semana.includes(diaSemana)) continue;
    const local = `${candidata}T${programa.horario_inicio.slice(0, 5)}`;
    try {
      if (Date.parse(isoNoFuso(local, fuso)) > agora.getTime()) return local;
    } catch {
      // Horário inexistente na virada de horário de verão: tenta a próxima ocorrência da grade.
    }
    if (programa.data_especifica) break;
  }
  return '';
}
