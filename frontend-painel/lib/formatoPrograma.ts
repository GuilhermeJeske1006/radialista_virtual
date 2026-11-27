import { FormatoPrograma, Programa } from "./types";

// Catálogo de formatos radiofônicos (F6). A fonte da verdade é o backend (app/live/formatos.py), lido por
// GET /config/formatos (FormatoPrograma em lib/types.ts). Este módulo guarda só um espelho estrutural dos
// formatos implementados (id, nome, alias, roteiro, relógio sugerido e blocos extras) para a prévia dos
// próximos blocos e a fala local do ao vivo funcionarem antes da rota responder, ou quando ela falha; os
// textos (promessa, conteúdo, condução, unidade, participação) só aparecem quando vêm da rota.
// Teste de sincronia com a cópia da rota: lib/__tests__/formatoPrograma.test.ts.

export const FORMATO_PADRAO = "padrao";
export const FORMATO_MUSICAL = "musical_adulto";
export const FORMATO_POPULAR = "popular_sertanejo";
export const FORMATO_VARIEDADES = "variedades_leves";

// Roteiros com a estrutura de blocos vazia (backend app.live.formatos.<FORMATO>.roteiro_padrao).
export const ROTEIRO_PADRAO = ["musica", "abertura", "comentario", "noticia", "chamada_ouvinte"];
export const ROTEIRO_MUSICAL = ["musica", "musica", "identificacao", "musica", "musica", "retomada"];
export const ROTEIRO_POPULAR = ["musica", "chamada_ouvinte", "musica", "comentario", "musica", "retomada"];
export const ROTEIRO_VARIEDADES = ["musica", "comentario", "musica", "chamada_ouvinte", "musica", "retomada"];

function espelho(
  id: string,
  nome: string,
  roteiro: string[],
  relogio: FormatoPrograma["relogio_padrao"],
  blocosExtras: boolean,
  aliases: string[] = [],
): FormatoPrograma {
  return {
    id,
    nome,
    promessa: "",
    conteudo: "",
    conducao: "",
    unidade_principal: "",
    roteiro_padrao: [...roteiro],
    relogio_padrao: relogio,
    ia_pode_adicionar_blocos: blocosExtras,
    participacao: "",
    temas_revisao: [],
    reorientacao_s: null,
    aliases: [...aliases],
    implementado: true,
    requer: "",
  };
}

export const FORMATOS_ESPELHO: FormatoPrograma[] = [
  espelho(FORMATO_PADRAO, "Livre (sem formato)", ROTEIRO_PADRAO, null, true),
  espelho(FORMATO_MUSICAL, "Musical adulto", ROTEIRO_MUSICAL, "A", false, ["musical_companhia"]),
  espelho(FORMATO_POPULAR, "Popular/sertanejo", ROTEIRO_POPULAR, "A", true),
  espelho(FORMATO_VARIEDADES, "Variedades leves", ROTEIRO_VARIEDADES, "C", true),
  // Ex-"flashback": vale para qualquer programa musical com repertório aprovado; "flashback" segue como alias.
  espelho("musical_curado", "Musical com curadoria", ["musica", "musica", "comentario", "musica", "musica",
    "identificacao", "musica", "musica", "chamada_ouvinte", "musica", "musica"], null, false, ["flashback"]),
];

type ProgramaComFormato = Pick<Programa, "perfil_programacao"> | null | undefined;

/** A lista da rota quando veio (não vazia); senão o espelho. */
export function catalogoFormatos(lista?: FormatoPrograma[] | null): FormatoPrograma[] {
  return Array.isArray(lista) && lista.length > 0 ? lista : FORMATOS_ESPELHO;
}

/** O que o select oferece: só os implementados, com o `padrao` ("Livre") primeiro. */
export function formatosImplementados(lista?: FormatoPrograma[] | null): FormatoPrograma[] {
  const todos = catalogoFormatos(lista).filter((f) => f.implementado);
  return [...todos.filter((f) => f.id === FORMATO_PADRAO), ...todos.filter((f) => f.id !== FORMATO_PADRAO)];
}

/**
 * Definição do formato do programa: resolve o alias (`musical_companhia` → `musical_adulto`) e cai no `padrao`
 * quando o valor está vazio, é desconhecido ou ainda não foi implementado, como o resolvedor do backend
 * (app.live.formatos.resolver_formato). Nunca reescreve o valor do programa.
 */
export function definicaoDoFormato(programa: ProgramaComFormato, lista?: FormatoPrograma[] | null): FormatoPrograma {
  const catalogo = catalogoFormatos(lista);
  const padrao = catalogo.find((f) => f.id === FORMATO_PADRAO) ?? FORMATOS_ESPELHO[0];
  const valor = (programa?.perfil_programacao ?? "").trim();
  if (!valor) return padrao;
  const encontrado = catalogo.find((f) => f.id === valor) ?? catalogo.find((f) => f.aliases.includes(valor));
  return encontrado && encontrado.implementado ? encontrado : padrao;
}

/** Id canônico do formato do programa. */
export function formatoDe(programa: ProgramaComFormato, lista?: FormatoPrograma[] | null): string {
  return definicaoDoFormato(programa, lista).id;
}

/** Ciclo musical (abertura só na largada, roteiro pelo deslocamento n-1): só o musical adulto e seu alias. */
export function ehMusical(programa: ProgramaComFormato, lista?: FormatoPrograma[] | null): boolean {
  return formatoDe(programa, lista) === FORMATO_MUSICAL;
}

/** Roteiro do formato com a estrutura de blocos vazia (cópia). */
export function roteiroDoFormato(programa: ProgramaComFormato, lista?: FormatoPrograma[] | null): string[] {
  return [...definicaoDoFormato(programa, lista).roteiro_padrao];
}

/** Flag do formato (D23): false só no musical; nos outros vale a flag do programa. */
export function blocosExtrasDoFormato(programa: ProgramaComFormato, lista?: FormatoPrograma[] | null): boolean {
  return definicaoDoFormato(programa, lista).ia_pode_adicionar_blocos;
}

/** Prévia do ciclo musical; abertura só na largada, encerramento pelo horário. */
export function tipoMusical(estrutura: string[], total: number, roteiroFormato: string[] = ROTEIRO_MUSICAL): string {
  if (total === 0) return "abertura";
  const personalizado = estrutura.map((t) => t.trim()).filter((t) => {
    const normalizado = t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
    return t && normalizado !== "abertura" && !/^encerramento(?: |$)/.test(normalizado);
  });
  const roteiro = personalizado.length ? personalizado : roteiroFormato;
  return roteiro[(total - 1) % roteiro.length];
}
