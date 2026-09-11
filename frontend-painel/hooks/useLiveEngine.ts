"use client";

import { confirmarParticipacao } from "../lib/participacoes";
import { esperarTransicao, pausaAntesDoBloco, reproduzirGrupoDeFalas } from "../lib/continuidadeAudio";
import { FilaPreparo } from "../lib/filaPreparo";

import { useEffect, useRef, useState } from "react";
import { apiFetch, apiFetchBlob, apiFetchBlobComTimeout, apiFetchComTimeout, ApiError } from "../lib/api";
import { setRadialistaAtualId } from "../lib/radialistas";
import { Radialista, Programa, RadioConta } from "../lib/types";
import {
  AudioFala,
  EstagioAoVivo,
  LiveProgramResponse,
  MusicaBloco,
  ProgramaOpcao,
  ProgramSegment,
  SegmentoPreparado,
} from "../lib/liveTypes";

declare global {
  interface Window {
    YT: any;
    onYouTubeIframeAPIReady: () => void;
  }
}

const INTERVALO_PROGRAMA_MS = 0;
// Falha inesperada ao preparar um bloco (ver catch em gerarProximaFala) não pode matar a
// transmissão antes do horario_fim -- so' espera um pouco (nao martela o backend quebrado a
// cada tick) e tenta de novo, com a musica de fundo tocando sozinha nesse meio-tempo.
const INTERVALO_RETENTATIVA_FALHA_MS = 5_000;
// Folga pro 1o bloco (busca de noticia + geracao + TTS, ver noticias.py no backend) terminar
// de preparar ANTES do horario_inicio real do programa agendado -- coberta com folga em cima
// do timeout de 75s do proprio fetch (ver apiFetchComTimeout em prepararTexto).
const ANTECEDENCIA_PREPARO_SEGUNDOS = 90;

type HistoricoFonte = { tipo: string; fala: string; musicas?: MusicaBloco[] };
type ContextoPreparo = {
  radialistaId: number;
  programaId: number;
  historicoBase: HistoricoFonte[];
  totalFalas: number;
  ultimaFala: string | null;
};
type TextoPreparado = {
  segmento: Omit<ProgramSegment, "id">;
  audioBase64?: string | null;
  audioStatus?: LiveProgramResponse["audio_status"];
  audioErro?: string | null;
};

const DIAS_SEMANA_ORDEM = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function horarioParaSegundos(horario: string): number {
  const [h, m, s] = horario.split(":").map(Number);
  return h * 3600 + m * 60 + (s || 0);
}

function dentroDaJanela(segundosAgora: number, inicioSeg: number, fimSeg: number): boolean {
  if (inicioSeg <= fimSeg) return segundosAgora >= inicioSeg && segundosAgora <= fimSeg;
  return segundosAgora >= inicioSeg || segundosAgora <= fimSeg;
}

function agoraNoFuso(timezone: string): { diaSemana: number; dataIso: string; segundosDoDia: number } {
  const partes = new Intl.DateTimeFormat("en-US", {
    timeZone: timezone,
    weekday: "short",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).formatToParts(new Date());
  const obter = (tipo: string) => partes.find((p) => p.type === tipo)?.value ?? "";
  const diaSemana = DIAS_SEMANA_ORDEM.indexOf(obter("weekday"));
  const dataIso = `${obter("year")}-${obter("month")}-${obter("day")}`;
  const hora = Number(obter("hour")) % 24;
  const minuto = Number(obter("minute"));
  const segundo = Number(obter("second"));
  return { diaSemana, dataIso, segundosDoDia: hora * 3600 + minuto * 60 + segundo };
}

// espelha app/guardrails/schedule.py (programa_no_ar / encontrar_programa_atual) do backend
export function programaNoAr(programa: Programa, timezone: string): boolean {
  if (!programa.ativo) return false;
  const { diaSemana, dataIso, segundosDoDia } = agoraNoFuso(timezone);
  if (programa.data_especifica) {
    if (programa.data_especifica !== dataIso) return false;
  } else if (programa.dias_semana.length > 0 && !programa.dias_semana.includes(diaSemana)) {
    return false;
  }
  return dentroDaJanela(segundosDoDia, horarioParaSegundos(programa.horario_inicio), horarioParaSegundos(programa.horario_fim));
}

// Quanto falta (em segundos) pro horario_inicio de hoje, ou null se o programa nao entra
// no ar hoje (inativo, dia da semana/data especifica nao bate) ou o horario ja passou --
// so' cobre o "hoje" do proprio fuso do programa de proposito (ver ANTECEDENCIA_PREPARO_SEGUNDOS
// abaixo): programa que comeca logo depois da meia-noite nao pre-aquece na virada do dia
// anterior, mesma limitacao que o disparo automatico (verificarHorarioAgendado) sempre teve.
export function segundosParaInicio(programa: Programa, timezone: string): number | null {
  if (!programa.ativo) return null;
  const { diaSemana, dataIso, segundosDoDia } = agoraNoFuso(timezone);
  if (programa.data_especifica) {
    if (programa.data_especifica !== dataIso) return null;
  } else if (programa.dias_semana.length > 0 && !programa.dias_semana.includes(diaSemana)) {
    return null;
  }
  const restante = horarioParaSegundos(programa.horario_inicio) - segundosDoDia;
  return restante > 0 ? restante : null;
}

function escolher(lista: string[], fallback: string) {
  return lista.length > 0 ? lista[Math.floor(Math.random() * lista.length)] : fallback;
}

function _semAcento(texto: string): string {
  return texto.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

// roteiro de EMERGENCIA (TTS/LLM indisponivel), usado so' quando POST /live/.../proxima falha.
// Atencao: essa ordem e' DIFERENTE do _ROTEIRO_PADRAO real do motor (backend/app/live/router.py),
// que comeca por "musica" -- nao usar como referencia pra preview de proximos blocos.
function gerarFalaLocal(
  radialista: Radialista,
  programa: Programa,
  totalFalas: number
): Omit<ProgramSegment, "id" | "criado_em" | "origem"> {
  if (programa.perfil_programacao === "musical_companhia") {
    return { tipo: "identificacao", fala: `Você está no ${programa.nome}. Obrigado pela companhia.` };
  }
  const nome = radialista.nome_locutor || "Locutor";
  const roteiroPadrao = ["abertura", "musica", "comentario", "noticia", "chamada_ouvinte"];
  // "encerramento" fica de fora do round-robin de propósito -- esse fallback local nao
  // sabe quanto tempo falta pro horario_fim (isso e' calculado no backend, ver perto_do_fim
  // em gerar_proxima_fala), entao deixar cair aqui por coincidencia do modulo faz o programa
  // encerrar cedo demais (tipo "encerramento" para o loop inteiro, ver gerarProximaFala abaixo).
  // Corte pontual no horario real continua garantido pelo watchdog verificarFimPontual.
  const roteiroCustom = programa.estrutura_blocos
    .map((b) => b.trim())
    .filter((b) => b && _semAcento(b.toLowerCase()) !== "encerramento");
  const roteiro = roteiroCustom.length > 0 ? roteiroCustom : roteiroPadrao;
  const tipo = roteiro[totalFalas % roteiro.length];
  const genero = escolher(programa.generos_musicais, "os sucessos da nossa programacao");
  const musica = escolher(programa.musicas_permitidas, genero);
  const assunto = escolher(
    programa.assuntos_ao_vivo.length ? programa.assuntos_ao_vivo : programa.topicos_permitidos,
    "a rotina da cidade"
  );
  const noticia = escolher(programa.tipos_noticias, "informacoes locais");

  const falas: Record<string, string> = {
    abertura: `Muito bem, aqui e ${nome} no ${programa.nome}. Bora de ${assunto} e boa musica ate o fim do bloco.`,
    musica: `Toca ai ${musica}. Ja volto com mais.`,
    comentario: `Sobre ${assunto}: quem tiver passando por isso, manda mensagem no WhatsApp que eu leio aqui.`,
    noticia: `${noticia}. Sem numero nem nome cravado agora, mas assim que a fonte confirmar eu trago certinho.`,
    chamada_ouvinte: `Bora, manda seu recado ou pede sua musica no WhatsApp.`,
  };

  const falaGenerica = `Seguimos com o bloco de ${tipo.replace(/_/g, " ")} aqui no ${programa.nome}, fica comigo.`;
  return { tipo, fala: falas[tipo] ?? falaGenerica };
}

export function useLiveEngine() {
  const [radialistas, setRadialistas] = useState<Radialista[]>([]);
  const [radialistaId, setRadialistaId] = useState<number | null>(null);
  const [radioConta, setRadioConta] = useState<RadioConta | null>(null);
  const [programasTodos, setProgramasTodos] = useState<ProgramaOpcao[]>([]);
  const [carregandoProgramas, setCarregandoProgramas] = useState(true);
  const [programaId, setProgramaId] = useState<number | null>(null);
  const [programaAtivo, setProgramaAtivo] = useState(false);
  const [gerandoFala, setGerandoFala] = useState(false);
  const [falasPrograma, setFalasPrograma] = useState<ProgramSegment[]>([]);
  const [erro, setErro] = useState("");
  // conta falhas de audio (embutido + fallback /tts, ou patrocinador/vinheta) em sequencia --
  // reseta a cada sucesso. `erro` acima e' um toast que a proxima fala sobrescreve, entao uma
  // falha isolada e uma queda prolongada da ElevenLabs pareciam identicas pro operador (o
  // programa ia silenciosamente virando "so musica" sem nenhum alerta que sobrevivesse mais
  // que um ciclo). Ver ALERTA_FALHA_AUDIO_CONSECUTIVAS abaixo pro limiar que vira alerta persistente.
  const [falhasAudioConsecutivas, setFalhasAudioConsecutivas] = useState(0);
  const [avisoGravacao, setAvisoGravacao] = useState("");
  const [abaEmSegundoPlano, setAbaEmSegundoPlano] = useState(false);
  const [musicaAtual, setMusicaAtual] = useState<string | null>(null);
  // fim_segundos do corte calculado pelo backend (ver app/live/audio_analysis.py) pra faixa
  // atual -- quando null, a musica toca ate o fim real do video. Usado pro transport calcular
  // "restante" sem precisar esperar o proprio video carregar metadata.
  const [musicaFimSegundos, setMusicaFimSegundos] = useState<number | null>(null);
  const [estagioAtual, setEstagioAtual] = useState<EstagioAoVivo>("idle");
  // espelho de totalFalasRef so' pra re-renderizar quem depende dele (ex.: ProximosBlocosPanel)
  // -- a contagem real que o motor usa pra decidir a posicao no roteiro continua no ref abaixo.
  const [totalFalas, setTotalFalas] = useState(0);

  const ultimoIdRef = useRef<number | null>(null);
  const radialistaIdRef = useRef<number | null>(null);
  const programaIdRef = useRef<number | null>(null);
  const programaAtivoRef = useRef(false);
  const gerandoFalaRef = useRef(false);
  const falasProgramaRef = useRef<ProgramSegment[]>([]);
  // contagem real de falas geradas na transmissao -- falasProgramaRef fica limitado
  // a 20 itens (so pra exibir/mandar historico), entao nao serve pra achar a posicao
  // no roteiro depois que passa desse teto.
  const totalFalasRef = useRef(0);
  const programaTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const transicaoRef = useRef<AbortController | null>(null);
  const ultimoDisparoAutomaticoRef = useRef<string | null>(null);
  // chave (programaId-data) do programa agendado ja pre-aquecido (ver ANTECEDENCIA_PREPARO_SEGUNDOS
  // abaixo) -- evita rechamar preencher() a cada tick de 15s do watchdog pro mesmo programa.
  const preAquecidoAgendadoRef = useRef<string | null>(null);
  // true so' quando a transmissao atual foi disparada pelo watchdog de horario agendado
  // (verificarHorarioAgendado), nao pelo clique manual em "Comecar transmissao" -- usado pra
  // limitar o watchdog de corte pontual (verificarFimPontual) a esse caso. Sem essa distincao,
  // uma transmissao manual fora do horario configurado do programa (teste, demo, plantao fora
  // da grade normal) se autopausava sozinha ~1s depois de iniciada, porque o unico sinal que o
  // watchdog de corte olhava era "esta dentro do horario configurado agora", nao "foi a propria
  // grade que ligou isso".
  const iniciadoPeloAgendamentoRef = useRef(false);
  const ytApiPromiseRef = useRef<Promise<void> | null>(null);
  const musicPlayerRef = useRef<any>(null);
  const musicStopRef = useRef<(() => void) | null>(null);
  const audioFalaRef = useRef<HTMLAudioElement | null>(null);
  const bgPlayerRef = useRef<any>(null);
  const bgProntoRef = useRef(false);
  const bgIntervaloFimRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const bgFadeIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const musicFadeIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // true depois que o player de fundo/musica desmuta pela 1a vez (ver onStateChange PLAYING
  // em iniciarMusicaFundo/tocarMusica) -- sem essa guarda, cada PLAYING subsequente (ex.: apos
  // o seekTo de loop) chamaria unMute()/fade de novo, sobrescrevendo o volume que o ducking
  // ja tiver ajustado nesse meio tempo.
  const bgDesmutadoRef = useRef(false);
  const musicDesmutadoRef = useRef(false);
  // A fila pertence à transmissão, não à execução de um player. Trocar de bloco
  // não invalida a escrita/síntese que ainda está em andamento para os seguintes.
  const filaPreparoRef = useRef<FilaPreparo<ContextoPreparo, TextoPreparado, SegmentoPreparado> | null>(null);
  const gravacaoBlobsRef = useRef<Blob[]>([]);
  // incrementado a cada chamada de gerarProximaFala -- pularFala usa isso pra
  // "aposentar" a execucao em andamento (a que estava tocando quando o usuario
  // clicou em "Proxima fala") depois que ela acorda do pararFala/musicStopRef,
  // pra ela nao concorrer com a nova execucao nem re-agendar o timer do loop.
  const execucaoAtualRef = useRef(0);

  useEffect(() => {
    if (typeof window === "undefined") return;

    if (window.YT && window.YT.Player) {
      ytApiPromiseRef.current = Promise.resolve();
      return;
    }

    ytApiPromiseRef.current = new Promise((resolve) => {
      const anterior = window.onYouTubeIframeAPIReady;
      window.onYouTubeIframeAPIReady = () => {
        anterior?.();
        resolve();
      };
    });

    if (!document.getElementById("youtube-iframe-api")) {
      const script = document.createElement("script");
      script.id = "youtube-iframe-api";
      script.src = "https://www.youtube.com/iframe_api";
      document.body.appendChild(script);
    }
  }, []);

  // o "ao vivo" e' um loop client-side (setTimeout recursivo em gerarProximaFala) --
  // sem processo no servidor sustentando ele. Aba em segundo plano ou minimizada leva
  // o navegador a throttlar/pausar esse timer (principalmente mobile), e o locutor
  // simplesmente para de falar sem erro nenhum pra investigar. Avisa na hora.
  useEffect(() => {
    if (typeof document === "undefined") return;

    function verificarVisibilidade() {
      setAbaEmSegundoPlano(document.hidden && programaAtivoRef.current);
    }

    document.addEventListener("visibilitychange", verificarVisibilidade);
    return () => document.removeEventListener("visibilitychange", verificarVisibilidade);
  }, []);

  async function carregarRadialistasEProgramas() {
    try {
      const lista = await apiFetch<Radialista[]>("/config/radialistas");
      setRadialistas(lista);
      try {
        const listasDeProgramas = await Promise.all(
          lista.map((r) =>
            apiFetch<Programa[]>(`/config/radialistas/${r.id}/programas`).catch(() => [] as Programa[])
          )
        );
        const combinado: ProgramaOpcao[] = lista.flatMap((r, i) =>
          listasDeProgramas[i].map((p) => ({
            ...p,
            radialistaId: r.id,
            radialistaNome: r.nome_locutor || `Radialista #${r.id}`,
          }))
        );
        setProgramasTodos(combinado);
      } finally {
        setCarregandoProgramas(false);
      }
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao carregar radialistas");
      setCarregandoProgramas(false);
    }
  }

  useEffect(() => {
    carregarRadialistasEProgramas();
    apiFetch<RadioConta>("/config/radio")
      .then(setRadioConta)
      .catch(() => setRadioConta(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // selecionar um programa carrega junto todos os dados vinculados a ele
  // (radialista dono, repertorio, assuntos, voz etc.)
  function selecionarPrograma(opcao: ProgramaOpcao, iniciarAutomaticamente = false) {
    const radialista = radialistas.find((r) => r.id === opcao.radialistaId);
    if (!radialista) return;

    // Mesmo programa/radialista ja em pre-aquecimento (ver ANTECEDENCIA_PREPARO_SEGUNDOS no
    // watchdog de agendamento abaixo): NAO reseta nem descarta a fila, senao o 1o bloco que
    // ja estava sendo preparado (busca de noticia + geracao + TTS, pode levar dezenas de
    // segundos) e jogado fora bem na hora que o programa entraria no ar com ele pronto.
    const jaPreAquecendoEsteMesmo =
      programaIdRef.current === opcao.id && radialistaIdRef.current === radialista.id && filaPreparoRef.current !== null;

    if (!jaPreAquecendoEsteMesmo) {
      pausarPrograma();
      falasProgramaRef.current = [];
      setFalasPrograma([]);
      totalFalasRef.current = 0;
      setTotalFalas(0);
      ultimoIdRef.current = null;

      radialistaIdRef.current = radialista.id;
      setRadialistaId(radialista.id);
      setRadialistaAtualId(radialista.id);

      programaIdRef.current = opcao.id;
      setProgramaId(opcao.id);
    }

    // Comeca a preparar o 1o bloco (texto + audio) desde ja, mesmo antes de "Comecar
    // transmissao": quando o operador clicar (ou o horario agendado disparar), o locutor
    // ja sobe no ar sabendo o que falar em vez de ficar mudo enquanto o bloco e' gerado.
    obterFilaPreparo().preencher();

    if (iniciarAutomaticamente) iniciarPrograma(true);
  }

  function limparTimerPrograma() {
    transicaoRef.current?.abort();
    transicaoRef.current = null;
    if (programaTimerRef.current) {
      clearTimeout(programaTimerRef.current);
      programaTimerRef.current = null;
    }
  }

  function pararFala() {
    if (audioFalaRef.current) {
      const audio = audioFalaRef.current;
      audioFalaRef.current = null;
      audio.pause();
      // pause() nao dispara "ended" -- resolve na mao a promise que
      // reproduzirAudioPreparado esta esperando, senao ela fica pendurada.
      audio.onended?.(new Event("ended"));
    }
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
  }

  // toca um audio ja sintetizado (preparado com antecedencia por prepararSegmento);
  // sem audio pronto, preserva a cama musical e pula a fala: uma voz generica do navegador
  // quebra mais a credibilidade da radio que uma contingencia curta e identificada no painel.
  // Devolve quanto tempo (segundos, medido no relogio de parede) o audio ficou
  // realmente no ar -- e' a duracao REAL da fala, nao uma estimativa (ver
  // atualizarDuracaoFala, que soma isso por bloco).
  // Frente K.6 (alternativa): cada bloco de fala e' uma chamada de sintese isolada (ElevenLabs
  // nao suporta request stitching no eleven_v3 -- previous_text/previous_request_ids da erro
  // nesse modelo, ver texto_anterior em app.tts.client), entao a PROSODIA de um clipe pro outro
  // nao tem como continuar de verdade via API. Isso aqui NAO resolve isso -- so' declica a borda
  // de cada clipe (fade curto de entrada/saida) pra sumir com o "clique"/corte digital abrupto
  // no início e no fim de cada mp3 isolado, que e' um problema separado (defeito de edicao, nao
  // de entonacao) e esse sim da pra corrigir do lado do audio.
  const FADE_BORDA_FALA_MS = 80;

  function fadeVolumeAudioElemento(audio: HTMLAudioElement, duracaoMs: number, alvo: number) {
    const inicio = audio.volume;
    const delta = alvo - inicio;
    if (Math.abs(delta) < 0.01 || duracaoMs <= 0) {
      audio.volume = alvo;
      return;
    }
    const inicioMs = performance.now();
    const passo = () => {
      const progresso = Math.min(1, (performance.now() - inicioMs) / duracaoMs);
      audio.volume = Math.max(0, Math.min(1, inicio + delta * progresso));
      if (progresso < 1 && audioFalaRef.current === audio) {
        requestAnimationFrame(passo);
      }
    };
    requestAnimationFrame(passo);
  }

  async function reproduzirAudioPreparado(audioUrl: string | null, _texto: string, aoConcluir?: () => void, gerenciarFundo = true): Promise<number> {
    const inicio = Date.now();
    if (!audioUrl) {
      setEstagioAtual("idle");
      return 0;
    }
    if (gerenciarFundo) duckMusicaFundo(true);
    setEstagioAtual("fala");
    try {
      if (audioUrl) {
        const audio = new Audio(audioUrl);
        audio.volume = 0;
        audioFalaRef.current = audio;
        let fadeSaidaTimeout: ReturnType<typeof setTimeout> | null = null;
        const limparFadeSaida = () => {
          if (fadeSaidaTimeout) {
            clearTimeout(fadeSaidaTimeout);
            fadeSaidaTimeout = null;
          }
        };
        audio.addEventListener(
          "loadedmetadata",
          () => {
            if (!Number.isFinite(audio.duration) || audio.duration <= 0) return;
            const atrasoMs = Math.max(0, audio.duration * 1000 - FADE_BORDA_FALA_MS);
            fadeSaidaTimeout = setTimeout(() => fadeVolumeAudioElemento(audio, FADE_BORDA_FALA_MS, 0), atrasoMs);
          },
          { once: true }
        );
        await new Promise<void>((resolve) => {
          audio.onended = () => {
            if (audio.ended) aoConcluir?.();
            limparFadeSaida();
            resolve();
          };
          audio.onerror = () => {
            limparFadeSaida();
            resolve();
          };
          audio
            .play()
            .then(() => fadeVolumeAudioElemento(audio, FADE_BORDA_FALA_MS, 1))
            .catch(() => {
              limparFadeSaida();
              resolve();
            });
        });
        URL.revokeObjectURL(audioUrl);
        if (audioFalaRef.current === audio) {
          audioFalaRef.current = null;
        }
        return (Date.now() - inicio) / 1000;
      }
      return 0;
    } finally {
      if (gerenciarFundo) duckMusicaFundo(false);
      setEstagioAtual("idle");
    }
  }

  const VOLUME_FUNDO_NORMAL = 18;
  const VOLUME_FUNDO_BAIXO = 6;
  const FADE_DUCK_MS = 900;
  const FADE_DUCK_ENTRADA_MS = 150;
  const FADE_MUSICA_MS = 1500;
  const FADE_MUSICA_SAIDA_S = FADE_MUSICA_MS / 1000;

  // Rampa o volume de um player do YouTube ate' `alvo` em vez do salto instantaneo de setVolume --
  // sem isso toda transicao (fala->fundo, fundo->musica, musica->fim) soa cortada, tipo audio colado
  // em vez de uma mixagem de estudio de verdade (reclamacao do usuario sobre abertura/fechamento de
  // bloco de musica soando estranho). `intervalRef` guarda o timer em andamento pra essa rampa
  // especifica ser cancelada se uma nova comecar antes de terminar (troca de bloco rapida, por ex.).
  function fadeVolumeYoutube(
    player: any,
    intervalRef: { current: ReturnType<typeof setInterval> | null },
    alvo: number,
    duracaoMs: number,
    passos = 12,
    inicioForcado?: number
  ) {
    if (!player) return;
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    let inicio = alvo;
    // getVolume() logo depois de um setVolume() nosso (ex.: reset pra 0 antes do fade-in) devolve
    // valor requente (medido: volta 100 mesmo com setVolume(0) acabado de chamar -- o setVolume e'
    // assincrono/postMessage pro iframe, getVolume nao reflete na hora) -- quando o chamador ja sabe
    // o volume de partida (porque acabou de defini-lo), inicioForcado evita essa leitura ruim, que
    // antes zerava o delta e colapsava o fade inteiro num salto instantaneo.
    if (typeof inicioForcado === "number") {
      inicio = inicioForcado;
    } else {
      try {
        if (typeof player.getVolume === "function") inicio = player.getVolume();
      } catch {
        // player pode nao estar pronto ainda -- fica com inicio = alvo (sem rampa, so' aplica direto)
      }
    }
    const delta = alvo - inicio;
    if (Math.abs(delta) < 1) {
      try {
        player.setVolume(alvo);
      } catch {
        // ignora falha ao ajustar volume
      }
      return;
    }
    let passo = 0;
    intervalRef.current = setInterval(() => {
      passo += 1;
      try {
        player.setVolume(Math.max(0, Math.min(100, Math.round(inicio + delta * (passo / passos)))));
      } catch {
        // player pode ja ter sido destruido no meio da rampa
      }
      if (passo >= passos && intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }, duracaoMs / passos);
  }

  function duckMusicaFundo(baixo: boolean) {
    if (!bgProntoRef.current || !bgPlayerRef.current) return;
    fadeVolumeYoutube(bgPlayerRef.current, bgFadeIntervalRef, baixo ? VOLUME_FUNDO_BAIXO : VOLUME_FUNDO_NORMAL, baixo ? FADE_DUCK_ENTRADA_MS : FADE_DUCK_MS);
  }

  function pararMusicaFundo() {
    bgProntoRef.current = false;
    if (bgIntervaloFimRef.current) {
      clearInterval(bgIntervaloFimRef.current);
      bgIntervaloFimRef.current = null;
    }
    if (bgPlayerRef.current) {
      try {
        bgPlayerRef.current.destroy();
      } catch {
        // ignora falha ao parar musica de fundo
      }
      bgPlayerRef.current = null;
    }
  }

  async function iniciarMusicaFundo() {
    if (!radialistaIdRef.current || !programaIdRef.current || !ytApiPromiseRef.current) return;

    let videoId: string;
    let inicioSegundos = 0;
    let fimSegundos: number | null = null;
    try {
      const musica = await apiFetch<{
        video_id: string;
        titulo: string;
        inicio_segundos?: number;
        fim_segundos?: number | null;
      }>(`/live/${radialistaIdRef.current}/programas/${programaIdRef.current}/musica-fundo`);
      videoId = musica.video_id;
      inicioSegundos = musica.inicio_segundos ?? 0;
      fimSegundos = musica.fim_segundos ?? null;
    } catch {
      return; // sem musica de fundo disponivel (sem chave do YouTube, etc.) -- segue so com as falas
    }

    try {
      await ytApiPromiseRef.current;
    } catch {
      return;
    }
    if (!window.YT || !window.YT.Player || !programaAtivoRef.current) return;

    pararMusicaFundo();
    bgPlayerRef.current = new window.YT.Player("yt-bg-player", {
      height: "0",
      width: "0",
      videoId,
      // mute:1 e' o que deixa o autoplay passar: o iframe tenta tocar assim que carrega, e
      // sem isso a tentativa e' com som sem gesto do usuario (ver auto-inicio por horario
      // agendado em verificarHorarioAgendado, que dispara via setInterval, sem clique nenhum)
      // -- Chrome bloqueia na hora. Mudo e' sempre permitido.
      playerVars: { autoplay: 1, controls: 0, loop: 1, playlist: videoId, start: inicioSegundos, mute: 1 },
      events: {
        onReady: (evento: any) => {
          bgProntoRef.current = true;
          evento.target.playVideo();
          bgDesmutadoRef.current = false;
          // fundo toca em loop -- sem ENDED natural (playlist/loop), entao o corte antes
          // de silencio/fala no final precisa voltar pro inicio na marca, nao esperar o fim.
          if (fimSegundos != null) {
            bgIntervaloFimRef.current = setInterval(() => {
              const atual = bgPlayerRef.current?.getCurrentTime?.();
              if (typeof atual === "number" && atual >= fimSegundos!) {
                bgPlayerRef.current?.seekTo(inicioSegundos, true);
              }
            }, 500);
          }
        },
        onStateChange: (evento: any) => {
          if (evento.data === window.YT.PlayerState.ENDED) evento.target.playVideo();
          // so' desmuta quando a reproducao muda de verdade pra PLAYING (nao logo apos
          // playVideo(), que so' inicia o buffer) -- chamar unMute() cedo demais, antes do
          // autoplay mudo ter realmente "pegado", faz o Chrome tratar como troca pra audio
          // com som sem gesto do usuario e cancela a reproducao de volta pra UNSTARTED (-1),
          // travando o player mudo pra sempre (bug relatado: ducking "nao sobe/desce na
          // pratica" -- na real nem tinha audio nenhum rodando pra ouvir a mudanca).
          if (evento.data === window.YT.PlayerState.PLAYING && !bgDesmutadoRef.current) {
            bgDesmutadoRef.current = true;
            evento.target.unMute();
            evento.target.setVolume(VOLUME_FUNDO_NORMAL);
          }
        },
      },
    });
  }

  // Toca uma faixa e devolve quanto tempo (segundos, relogio de parede) ela ficou
  // realmente no ar -- duracao REAL, igual reproduzirAudioPreparado, pra somar por
  // bloco (ver atualizarDuracaoFala).
  function tocarMusica(
    videoId: string,
    titulo: string,
    inicioSegundos = 0,
    fimSegundos: number | null = null,
    aoConcluir?: () => void
  ): Promise<number> {
    const TIMEOUT_SEGURANCA_MS = 6 * 60 * 1000;
    const POLL_FIM_MS = 500;
    const inicio = Date.now();

    return new Promise((resolvePromise) => {
      async function iniciar() {
        if (typeof window === "undefined" || !ytApiPromiseRef.current) {
          resolvePromise(0);
          return;
        }

        try {
          await ytApiPromiseRef.current;
        } catch {
          resolvePromise(0);
          return;
        }

        if (!window.YT || !window.YT.Player) {
          resolvePromise(0);
          return;
        }

        setMusicaAtual(titulo || "Musica ao vivo");
        setMusicaFimSegundos(fimSegundos);
        setEstagioAtual("musica");

        let finalizado = false;
        let timeoutId: ReturnType<typeof setTimeout>;
        let intervaloFimId: ReturnType<typeof setInterval> | undefined;
        const finalizar = (concluiu = false) => {
          if (finalizado) return;
          if (concluiu && musicDesmutadoRef.current) aoConcluir?.();
          finalizado = true;
          clearTimeout(timeoutId);
          if (intervaloFimId) clearInterval(intervaloFimId);
          musicStopRef.current = null;
          try {
            musicPlayerRef.current?.stopVideo?.();
          } catch {
            // ignora falha ao parar o player
          }
          // rampa de volta ao normal mesmo quando chega aqui sem passar pelo fade antecipado do
          // poll abaixo (ENDED natural, erro, timeout de seguranca) -- melhor uma rampa curta que
          // um salto instantaneo de volume nesses casos tambem.
          if (bgProntoRef.current) fadeVolumeYoutube(bgPlayerRef.current, bgFadeIntervalRef, VOLUME_FUNDO_NORMAL, FADE_DUCK_MS);
          setMusicaAtual(null);
          setMusicaFimSegundos(null);
          setEstagioAtual("idle");
          resolvePromise((Date.now() - inicio) / 1000);
        };
        timeoutId = setTimeout(finalizar, TIMEOUT_SEGURANCA_MS);
        musicStopRef.current = finalizar;

        if (musicPlayerRef.current) {
          try {
            musicPlayerRef.current.destroy();
          } catch {
            // ignora falha ao destruir player anterior
          }
          musicPlayerRef.current = null;
        }

        musicPlayerRef.current = new window.YT.Player("yt-live-player", {
          height: "0",
          width: "0",
          videoId,
          // mute:1 e' o que deixa o autoplay passar (ver bg player acima) -- tentativa de tocar
          // com som sem gesto do usuario e' bloqueada na hora pelo Chrome.
          playerVars: { autoplay: 1, controls: 0, start: inicioSegundos, mute: 1 },
          events: {
            onReady: (evento: any) => {
              musicDesmutadoRef.current = false;
              evento.target.playVideo();

              // corta antes de silencio longo/fala no final da faixa (analisado no backend, ver
              // app/live/audio_analysis.py) -- sem isso tocaria ate o fim real do video, que pode
              // ter trecho falado ou vazio. O fade de saida comeca um pouco antes do corte (em vez
              // de cortar em volume cheio e so' depois subir o fundo) pra soar como um segue de
              // estudio, nao um corte seco.
              if (fimSegundos != null) {
                let fadeIniciado = fimSegundos - FADE_MUSICA_SAIDA_S <= inicioSegundos;
                intervaloFimId = setInterval(() => {
                  const atual = musicPlayerRef.current?.getCurrentTime?.();
                  if (typeof atual !== "number") return;
                  if (!fadeIniciado && atual >= fimSegundos - FADE_MUSICA_SAIDA_S) {
                    fadeIniciado = true;
                    fadeVolumeYoutube(musicPlayerRef.current, musicFadeIntervalRef, 0, FADE_MUSICA_MS);
                    if (bgProntoRef.current) fadeVolumeYoutube(bgPlayerRef.current, bgFadeIntervalRef, VOLUME_FUNDO_NORMAL, FADE_MUSICA_MS);
                  }
                  if (atual >= fimSegundos) finalizar(true);
                }, POLL_FIM_MS);
              }
            },
            onStateChange: (evento: any) => {
              if (evento.data === window.YT.PlayerState.ENDED) finalizar(true);
              // so' desmuta/inicia o fade cruzado quando a musica realmente comecar a tocar --
              // ver o mesmo cuidado no player de fundo (iniciarMusicaFundo) sobre por que
              // desmutar cedo demais cancela o autoplay de volta pra UNSTARTED.
              if (evento.data === window.YT.PlayerState.PLAYING && !musicDesmutadoRef.current) {
                musicDesmutadoRef.current = true;
                evento.target.unMute();
                // fade cruzado: musica sobe de silencio enquanto o fundo desce pro lugar dela, em
                // vez do salto instantaneo de antes (fundo mudo + musica em volume cheio na mesma
                // batida) -- e' o que soava "colado"/artificial na abertura do bloco.
                evento.target.setVolume(0);
                fadeVolumeYoutube(evento.target, musicFadeIntervalRef, 100, FADE_MUSICA_MS, 12, 0);
                if (bgProntoRef.current) fadeVolumeYoutube(bgPlayerRef.current, bgFadeIntervalRef, 0, FADE_MUSICA_MS);
              }
            },
            // codigos do player: 2 parametro invalido, 5 erro de HTML5, 100 video removido/privado,
            // 101/150 dono do video bloqueou embed -- sem log aqui a musica so' "nao tocava", sem
            // pista nenhuma de qual desses era (ver post-mortem que motivou isso)
            onError: (evento: any) => {
              console.error("Erro ao tocar musica no player do YouTube:", videoId, titulo, evento?.data);
              finalizar();
            },
          },
        });
      }

      iniciar();
    });
  }

  // Sufixo com titulo+canal de cada musica do bloco, pro historico mandado ao backend --
  // o locutor so anuncia a 1a faixa quando emenda [BLOCO_MUSICAS:N] (ver gerarProximaFala),
  // entao sem isso a IA nunca sabe o que emendou depois dela pra poder comentar assim que
  // a sequencia acabar (ver instrucao correspondente em app.live.router).
  function linhaMusicasHistorico(fala: { musicas?: MusicaBloco[] }): string {
    if (!fala.musicas || fala.musicas.length === 0) return "";
    const lista = fala.musicas.map((m) => (m.canal ? `${m.titulo} - ${m.canal}` : m.titulo)).join(", ");
    return ` [Música(s) tocada(s) nesse bloco: ${lista}]`;
  }

  function adicionarFala(segmento: Omit<ProgramSegment, "id">) {
    const novaFala: ProgramSegment = { ...segmento, id: Date.now() };
    const atualizadas = [novaFala, ...falasProgramaRef.current].slice(0, 20);
    falasProgramaRef.current = atualizadas;
    setFalasPrograma(atualizadas);
    totalFalasRef.current += 1;
    setTotalFalas(totalFalasRef.current);
    return novaFala;
  }

  // Grava a duracao REAL de um bloco ja tocado (soma do tempo de ar de cada musica +
  // cada fala que o compoe, medida em gerarProximaFala/inserirNaTransmissao) no item de
  // historico correspondente -- so' preenchido depois que o bloco termina de tocar,
  // porque antes disso a duracao real ainda nao existe.
  function atualizarDuracaoFala(id: number, duracaoSegundos: number) {
    const atualizadas = falasProgramaRef.current.map((f) =>
      f.id === id ? { ...f, duracao_segundos: Math.round(duracaoSegundos) } : f
    );
    falasProgramaRef.current = atualizadas;
    setFalasPrograma(atualizadas);
  }

  // Entrega o texto antes do TTS para liberar a escrita do próximo bloco.
  async function prepararTexto(contexto: ContextoPreparo, ativa: () => boolean): Promise<TextoPreparado> {
    const { historicoBase, totalFalas: totalFalasAtual, ultimaFala: ultimaFalaAtual } = contexto;
    let segmento: Omit<ProgramSegment, "id">;
    // audio ja sintetizado dentro de /proxima (ver Plano B.3) -- so' preenchido quando o backend
    // conseguiu; guardado fora de `segmento` pra nao carregar mp3 em base64 dentro do historico
    // de falas (falasProgramaRef guarda os ultimos 20 blocos).
    let audioBase64: string | null | undefined;
    let audioStatus: LiveProgramResponse["audio_status"];
    let audioErro: string | null | undefined;
    try {
      const { audio_base64, audio_status, audio_erro, ...resposta } = await apiFetchComTimeout<LiveProgramResponse>(
        `/live/${contexto.radialistaId}/programas/${contexto.programaId}/proxima`,
        {
          method: "POST",
          body: JSON.stringify({
            incluir_audio: false,
            historico: historicoBase
              .slice(0, 8)
              .reverse()
              .map((fala) => `${fala.tipo}: ${fala.fala}${linhaMusicasHistorico(fala)}`),
            total_falas: totalFalasAtual,
            perfil_pos_producao: "radio_fm",
            ultima_fala: ultimaFalaAtual,
          }),
        },
        // Inclui apuração jornalística antes da locução; o áudio segue preparado em paralelo.
        75_000
      );
      audioBase64 = audio_base64;
      audioStatus = audio_status;
      audioErro = audio_erro;
      segmento = { ...resposta, origem: "ia" };
      if (ativa()) setErro("");
    } catch (err) {
      const radialistaAtual = radialistas.find((r) => r.id === contexto.radialistaId);
      const programaAtual = programasTodos.find((p) => p.id === contexto.programaId);
      if (radialistaAtual && programaAtual) {
        const local = gerarFalaLocal(radialistaAtual, programaAtual, totalFalasAtual);
        segmento = { ...local, criado_em: new Date().toISOString(), origem: "local" };
        if (ativa()) setErro(err instanceof ApiError ? `${err.message}. Usando fala local.` : "IA indisponivel. Usando fala local.");
      } else {
        segmento = {
          tipo: "comentario",
          fala: "Seguimos no ar, ja volto com mais uma novidade.",
          criado_em: new Date().toISOString(),
          origem: "local",
        };
        if (ativa()) setErro(err instanceof ApiError ? err.message : "IA indisponivel");
      }
    }
    return { segmento, audioBase64, audioStatus, audioErro };
  }

  // Só fica pronto após baixar a voz ou vinheta e concluir o tratamento Rádio FM.
  async function prepararAudio(texto: TextoPreparado, contexto: ContextoPreparo, ativa: () => boolean): Promise<SegmentoPreparado> {
    const { segmento, audioBase64, audioStatus, audioErro } = texto;
    const ultimaFalaAtual = contexto.ultimaFala;

    // dialogo multi-voz (mais de um radialista no programa): busca um audio por linha,
    // cada uma com a voz do radialista que falou -- em vez de um audio unico pro bloco.
    if (segmento.falas && segmento.falas.length > 0) {
      // previous_text pra ElevenLabs (ver texto_anterior em LiveTtsRequest): dentro de um dialogo
      // multi-voz, cada linha continua a linha anterior do mesmo bloco; a primeira linha continua
      // a ultima fala do bloco anterior (falasProgramaRef, mais recente primeiro).
      const audiosFalas = await Promise.all(
        segmento.falas.map(async (linha, indice): Promise<AudioFala> => {
          const textoAnterior = indice > 0 ? segmento.falas![indice - 1].texto : ultimaFalaAtual;
          try {
            const blob = await apiFetchBlobComTimeout(`/live/${contexto.radialistaId}/tts`, {
              method: "POST",
              body: JSON.stringify({
                perfil_pos_producao: "radio_fm",
                texto: linha.texto,
                tipo: segmento.tipo,
                voz_id: linha.voz_id,
                texto_anterior: textoAnterior,
                programa_id: contexto.programaId,
              }),
            }, 60_000);
            return { url: URL.createObjectURL(blob), blob };
          } catch (err) {
            console.error("Falha ao gerar audio TTS (dialogo multi-voz), mantendo cama musical", err);
            if (ativa()) setErro(err instanceof ApiError ? `${err.message}. Linha pulada; cama musical mantida.` : "Voz IA indisponivel. Linha pulada; cama musical mantida.");
            return { url: null, blob: null };
          }
        })
      );
      return { segmento, audioUrl: null, audioBlob: null, audiosFalas };
    }

    // Sequências musicais sem locução não devem chamar TTS com texto vazio.
    if (!segmento.fala.trim() && !segmento.vinheta_id && !segmento.patrocinador_audio) {
      return { segmento, audioUrl: null, audioBlob: null, audiosFalas: null };
    }

    let audioUrl: string | null = null;
    let audioBlob: Blob | null = null;
    try {
      // audio ja veio pronto no proprio /proxima (ver Plano B.3) -- poupa o round-trip
      // separado de /tts. So' vem preenchido quando o backend conseguiu sintetizar;
      // qualquer outro caso cai nos ramos de sempre (patrocinador/vinheta/POST /tts).
      if (audioBase64) {
        const bytes = Uint8Array.from(atob(audioBase64), (c) => c.charCodeAt(0));
        audioBlob = new Blob([bytes], { type: "audio/mpeg" });
      } else {
        // audioStatus "indisponivel" = TTS nem esta habilitado pra este radialista (ver
        // tts_habilitado no backend) -- cair pro /tts abaixo bateria na mesma checagem e falharia
        // igual, sem motivo pra tentar de novo.
        if (audioStatus === "indisponivel") {
          throw new Error(`Audio IA indisponivel: ${audioErro ?? "sem detalhe"}`);
        }
        // Se a sintese embutida falhar, tenta /tts com o mesmo perfil Rádio FM.
        // O processamento aguarda o audio completo; o timeout inclui essa etapa.
        // patrocinador com audio pre-gravado ou vinheta: toca o arquivo direto, sem TTS
        audioBlob =
          segmento.tipo === "patrocinador" && segmento.patrocinador_audio && segmento.patrocinador_id
            ? await apiFetchBlob(`/patrocinadores/${segmento.patrocinador_id}/audio`)
            : segmento.tipo === "vinheta" && segmento.vinheta_id
              ? await apiFetchBlob(`/biblioteca-audio/${segmento.vinheta_id}/audio`)
              : await apiFetchBlobComTimeout(`/live/${contexto.radialistaId}/tts`, {
                  method: "POST",
                  body: JSON.stringify({
                    perfil_pos_producao: "radio_fm",
                    texto: segmento.fala,
                    tipo: segmento.tipo,
                    tom: segmento.tom ?? null,
                    voz_id: segmento.patrocinador_voz_id ?? null,
                    texto_anterior: ultimaFalaAtual,
                    programa_id: contexto.programaId,
                }),
              }, 60_000);
      }
      audioUrl = URL.createObjectURL(audioBlob);
      if (ativa()) setFalhasAudioConsecutivas(0);
    } catch (err) {
      // engolir aqui sem log/aviso fazia a fala cair calada pra voz robotica do navegador (ver
      // falarComVozNavegador) sem nenhum indicio de que o TTS/audio do backend falhou.
      console.error("Falha ao gerar audio (TTS/patrocinador/vinheta), mantendo cama musical", err);
      if (ativa()) {
        setErro(err instanceof ApiError ? `${err.message}. Fala pulada; cama musical mantida.` : "Voz IA indisponivel. Fala pulada; cama musical mantida.");
        setFalhasAudioConsecutivas((n) => n + 1);
      }
      audioUrl = null;
      audioBlob = null;
    }

    return { segmento, audioUrl, audioBlob, audiosFalas: null };
  }

  function descartarPreparo() {
    filaPreparoRef.current?.cancelar();
    filaPreparoRef.current = null;
  }

  function obterFilaPreparo(): FilaPreparo<ContextoPreparo, TextoPreparado, SegmentoPreparado> {
    if (!filaPreparoRef.current) {
      const fila: FilaPreparo<ContextoPreparo, TextoPreparado, SegmentoPreparado> = new FilaPreparo<ContextoPreparo, TextoPreparado, SegmentoPreparado>({
        radialistaId: radialistaIdRef.current!,
        programaId: programaIdRef.current!,
        historicoBase: [...falasProgramaRef.current],
        totalFalas: totalFalasRef.current,
        ultimaFala: falasProgramaRef.current[0]?.fala ?? null,
      }, {
        gerarTexto: (contexto) => prepararTexto(contexto, () => fila.ativa),
        prepararAudio: (texto, contexto) => prepararAudio(texto, contexto, () => fila.ativa),
        contaNaAntecedencia: ({ segmento }) => segmento.tipo !== "vinheta",
        avancar: (contexto, { segmento }) => segmento.tipo === "encerramento" ? null : ({
          ...contexto,
          historicoBase: [segmento, ...contexto.historicoBase].slice(0, 20),
          totalFalas: contexto.totalFalas + 1,
          ultimaFala: segmento.fala,
        }),
        descartar: (preparado) => {
          if (preparado.audioUrl) URL.revokeObjectURL(preparado.audioUrl);
          preparado.audiosFalas?.forEach((audio) => audio.url && URL.revokeObjectURL(audio.url));
        },
      });
      filaPreparoRef.current = fila;
    }
    return filaPreparoRef.current;
  }

  async function gerarProximaFala(forcar = false) {
    if (
      gerandoFalaRef.current ||
      (!programaAtivoRef.current && !forcar) ||
      !radialistaIdRef.current ||
      !programaIdRef.current
    )
      return;

    const minhaExecucao = ++execucaoAtualRef.current;

    gerandoFalaRef.current = true;
    setGerandoFala(true);
    setErro("");

    let preparado: SegmentoPreparado | null;
    try {
      preparado = await obterFilaPreparo().retirar();
    } catch {
      // Fila quebrou (excecao inesperada, nao os fallbacks normais de texto/audio, que ja nao
      // chegam aqui -- ver prepararTexto/prepararAudio). NAO chama pausarPrograma(): isso
      // pararia a musica de fundo e encerraria a transmissao antes do horario_fim. Descarta a
      // fila (poisoned, ver FilaPreparo.contexto) e tenta de novo daqui a pouco, com a cama
      // musical tocando sozinha nesse meio-tempo -- so' o watchdog de horario_fim ou uma pausa
      // manual devem de fato terminar a transmissao mais cedo.
      if (execucaoAtualRef.current === minhaExecucao) {
        gerandoFalaRef.current = false;
        setGerandoFala(false);
        descartarPreparo();
        setErro("Não foi possível preparar o próximo bloco. Mantendo música de fundo; tentando novamente.");
        if (programaAtivoRef.current) {
          programaTimerRef.current = setTimeout(() => gerarProximaFala(), INTERVALO_RETENTATIVA_FALHA_MS);
        }
      }
      return;
    }

    // usuario clicou "Pausar transmissao" enquanto essa fala/audio ainda estava sendo
    // preparada (busca no backend nao e' cancelavel) -- descarta em vez de por no ar,
    // senao a transmissao "pausada" segue falando/tocando musica mesmo assim.
    if (!preparado || !programaAtivoRef.current || execucaoAtualRef.current !== minhaExecucao) {
      if (preparado?.audioUrl) URL.revokeObjectURL(preparado.audioUrl);
      preparado?.audiosFalas?.forEach((a) => a.url && URL.revokeObjectURL(a.url));
      if (execucaoAtualRef.current === minhaExecucao) {
        gerandoFalaRef.current = false;
        setGerandoFala(false);
      }
      return;
    }

    const novaFala = adicionarFala(preparado.segmento);
    limparTimerPrograma();

    // retirar() já repôs duas entradas na fila enquanto esta voz era finalizada.

    gerandoFalaRef.current = false;
    setGerandoFala(false);

    const transicao = new AbortController();
    transicaoRef.current = transicao;
    const podeTocar = await esperarTransicao(pausaAntesDoBloco(novaFala.pausa_antes_ms), transicao.signal);
    if (transicaoRef.current === transicao) transicaoRef.current = null;
    if (!podeTocar || !programaAtivoRef.current || execucaoAtualRef.current !== minhaExecucao) {
      if (preparado.audioUrl) URL.revokeObjectURL(preparado.audioUrl);
      preparado.audiosFalas?.forEach((a) => a.url && URL.revokeObjectURL(a.url));
      atualizarDuracaoFala(novaFala.id, 0);
      if (novaFala.pedido_id && novaFala.pedido_token && novaFala.pedido_programa_id) {
        try {
          await confirmarParticipacao(novaFala, "interrompido");
        } catch {
          setErro("Não foi possível confirmar a interrupção da participação. Confira o pedido na fila.");
        }
      }
      return;
    }

    if (preparado.audioBlob) gravacaoBlobsRef.current.push(preparado.audioBlob);
    preparado.audiosFalas?.forEach((a) => a.blob && gravacaoBlobsRef.current.push(a.blob));

    // Duracao REAL do bloco inteiro: soma o tempo de ar de cada musica + cada fala que
    // compoe ele (medido no relogio de parede por reproduzirAudioPreparado/tocarMusica),
    // em vez de uma estimativa -- grava no historico ao final (ver atualizarDuracaoFala).
    let duracaoBlocoSegundos = 0;
    let participacaoConcluida = false;
    let linhasConcluidas = 0;

    if (novaFala.video_id) {
      try {
        duracaoBlocoSegundos += await reproduzirAudioPreparado(preparado.audioUrl, novaFala.fala);
        // bloco pode ter mais de uma musica (o agente decidiu emendar) --
        // toca todas seguidas, sem nova fala entre elas, pra manter o embalo
        const bloco =
          novaFala.musicas && novaFala.musicas.length > 0
            ? novaFala.musicas
            : [
                {
                  video_id: novaFala.video_id,
                  titulo: novaFala.titulo_musica ?? "",
                  inicio_segundos: novaFala.inicio_segundos ?? 0,
                  fim_segundos: novaFala.fim_segundos ?? null,
                },
              ];
        for (const musica of bloco) {
          if (!programaAtivoRef.current || execucaoAtualRef.current !== minhaExecucao) break;
          duracaoBlocoSegundos += await tocarMusica(
            musica.video_id,
            musica.titulo,
            musica.inicio_segundos ?? 0,
            musica.fim_segundos ?? null,
            () => { if (musica.video_id === novaFala.video_id) participacaoConcluida = true; }
          );
        }
      } catch (err) {
        // segue o programa mesmo se a musica falhar ao tocar -- loga pra dar pra
        // diagnosticar depois (sem isso o bloco so' pulava direto, sem pista nenhuma)
        console.error("Falha ao tocar bloco de musica:", err);
      }
    } else if (preparado.audiosFalas && preparado.audiosFalas.length > 0) {
      // dialogo multi-voz: toca uma linha de cada vez, na voz de quem falou
      duracaoBlocoSegundos += await reproduzirGrupoDeFalas(
        preparado.audiosFalas,
        () => programaAtivoRef.current && execucaoAtualRef.current === minhaExecucao,
        (audio, i) => reproduzirAudioPreparado(
          audio.url, novaFala.falas?.[i]?.texto ?? novaFala.fala, () => { linhasConcluidas++; }, false,
        ),
        duckMusicaFundo,
      );
    } else {
      duracaoBlocoSegundos += await reproduzirAudioPreparado(preparado.audioUrl, novaFala.fala, () => { participacaoConcluida = true; });
    }
    if (preparado.audiosFalas?.length && !novaFala.video_id) {
      participacaoConcluida = linhasConcluidas === preparado.audiosFalas.length;
    }
    if (novaFala.pedido_id && novaFala.pedido_token && novaFala.pedido_programa_id) {
      const interrompido = execucaoAtualRef.current !== minhaExecucao || !programaAtivoRef.current;
      try {
        await confirmarParticipacao(novaFala, participacaoConcluida ? "executado" : interrompido ? "interrompido" : "falhou");
      } catch {
        setErro("Não foi possível confirmar o resultado da participação. Confira o pedido na fila antes de reenfileirar.");
      }
    }

    atualizarDuracaoFala(novaFala.id, duracaoBlocoSegundos);

    // execucao foi "pulada" (pularFala disparou uma nova) enquanto essa tocava --
    // quem continua o loop a partir daqui e' a execucao nova, nao essa
    if (execucaoAtualRef.current !== minhaExecucao) return;

    if (novaFala.tipo === "encerramento") {
      // roteiro chegou perto do horario_fim do programa -- a fala de despedida
      // ja foi ao ar, para a transmissao em vez de continuar o loop
      pausarPrograma();
      return;
    }

    if (programaAtivoRef.current) {
      // O próximo conteúdo já recebe sua própria pausa_antes_ms. Não somar outra espera aqui.
      programaTimerRef.current = setTimeout(() => gerarProximaFala(), INTERVALO_PROGRAMA_MS);
    }
  }

  // corta a fala/musica atual na hora e vai pro proximo bloco (botao "Proxima
  // fala") -- diferente de deixar o loop normal seguir sozinho ate o fim do audio.
  function pularFala() {
    if (!programaAtivoRef.current || gerandoFalaRef.current) return;
    limparTimerPrograma();
    pararFala();
    musicStopRef.current?.();
    gerarProximaFala(true);
  }

  // clique num item do Cartwall/Biblioteca durante a transmissao: corta a fala/musica
  // atual na hora e poe esse audio no ar (em vez de so tocar "por cima", ducking, como
  // o preview isolado desses paineis faz) -- depois volta pro loop normal sozinho.
  async function inserirNaTransmissao(item: { id: number; nome: string }) {
    if (!programaAtivoRef.current || !radialistaIdRef.current || !programaIdRef.current) return;

    const minhaExecucao = ++execucaoAtualRef.current;
    limparTimerPrograma();
    pararFala();
    musicStopRef.current?.();
    descartarPreparo();

    gerandoFalaRef.current = true;
    setGerandoFala(true);
    setErro("");

    let audioUrl: string | null = null;
    let audioBlob: Blob | null = null;
    try {
      audioBlob = await apiFetchBlob(`/biblioteca-audio/${item.id}/audio`);
      audioUrl = URL.createObjectURL(audioBlob);
    } catch (err) {
      if (execucaoAtualRef.current === minhaExecucao) setErro(err instanceof ApiError ? err.message : "Erro ao tocar audio");
    }

    if (!programaAtivoRef.current || execucaoAtualRef.current !== minhaExecucao) {
      if (audioUrl) URL.revokeObjectURL(audioUrl);
      return;
    }
    gerandoFalaRef.current = false;
    setGerandoFala(false);

    const novaFala = adicionarFala({
      tipo: "vinheta",
      fala: item.nome,
      criado_em: new Date().toISOString(),
      origem: "manual",
      vinheta_id: item.id,
    });

    if (audioBlob) gravacaoBlobsRef.current.push(audioBlob);

    // A inserção manual muda o contexto. Refaz a fila durante a vinheta.
    if (programaAtivoRef.current) {
      obterFilaPreparo().preencher();
    }

    const duracaoSegundos = await reproduzirAudioPreparado(audioUrl, novaFala.fala);
    atualizarDuracaoFala(novaFala.id, duracaoSegundos);

    if (execucaoAtualRef.current !== minhaExecucao) return;

    if (programaAtivoRef.current) {
      programaTimerRef.current = setTimeout(() => gerarProximaFala(), INTERVALO_PROGRAMA_MS);
    }
  }

  function iniciarPrograma(peloAgendamento = false) {
    if (programaAtivoRef.current) return;
    if (!radialistaIdRef.current || !programaIdRef.current) {
      setErro("Selecione um programa antes de iniciar.");
      return;
    }
    limparTimerPrograma();
    // "=== true" de proposito, nao so' truthy: se algum dia esta funcao voltar a ser usada
    // direto como handler de evento (ex.: onIniciar={engine.iniciarPrograma} num onClick, sem
    // arrow function no meio), o SyntheticEvent do React cai aqui como primeiro argumento --
    // um objeto e' sempre truthy, e uma transmissao manual seria tratada como se o watchdog de
    // horario agendado tivesse ligado ela (ver verificarFimPontual/iniciadoPeloAgendamentoRef),
    // pausando sozinha ~1s depois fora do horario configurado do programa. So' o literal `true`
    // (passado explicitamente por selecionarPrograma) deve contar como "foi o agendamento".
    iniciadoPeloAgendamentoRef.current = peloAgendamento === true;
    programaAtivoRef.current = true;
    setProgramaAtivo(true);
    gravacaoBlobsRef.current = [];
    setAvisoGravacao("");
    iniciarMusicaFundo();
    gerarProximaFala(true);
  }

  // junta as falas do locutor gravadas durante a transmissao (audio TTS, na ordem
  // em que foram ao ar) num unico mp3 e dispara o download no navegador
  function exportarGravacao() {
    const blocos = gravacaoBlobsRef.current;
    gravacaoBlobsRef.current = [];
    if (blocos.length === 0) return;

    const programaAtual = programasTodos.find((p) => p.id === programaIdRef.current);
    const carimbo = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
    const nomeArquivo = `${(programaAtual?.nome || "programa").replace(/[^a-zA-Z0-9-_]+/g, "_")}-${carimbo}.mp3`;

    const audioFinal = new Blob(blocos, { type: "audio/mpeg" });
    const url = URL.createObjectURL(audioFinal);
    const link = document.createElement("a");
    link.href = url;
    link.download = nomeArquivo;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    setAvisoGravacao(`Gravacao exportada: ${nomeArquivo}`);
    setTimeout(() => setAvisoGravacao(""), 6000);
  }

  function pausarPrograma(exportar = false) {
    limparTimerPrograma();
    execucaoAtualRef.current += 1;
    gerandoFalaRef.current = false;
    setGerandoFala(false);
    programaAtivoRef.current = false;
    iniciadoPeloAgendamentoRef.current = false;
    setProgramaAtivo(false);
    setAbaEmSegundoPlano(false);
    setFalhasAudioConsecutivas(0);
    pararFala();
    musicStopRef.current?.();
    pararMusicaFundo();
    descartarPreparo();

    if (exportar) exportarGravacao();

    // marca a ocorrencia atual como "ja tratada" pra pausa manual nao ser
    // reiniciada de imediato pelo checador de horario agendado
    const selecionado = programasTodos.find((p) => p.id === programaIdRef.current);
    const radialistaDoSelecionado = radialistas.find((r) => r.id === selecionado?.radialistaId);
    if (selecionado && radialistaDoSelecionado && programaNoAr(selecionado, radialistaDoSelecionado.timezone)) {
      ultimoDisparoAutomaticoRef.current = `${selecionado.id}-${new Date().toDateString()}`;
    }
  }

  useEffect(() => {
    return () => {
      programaAtivoRef.current = false;
      limparTimerPrograma();
      pararFala();
      musicStopRef.current?.();
      pararMusicaFundo();
      descartarPreparo();
    };
  }, []);

  // radialista/programa selecionado foi excluido (via modal de edicao) -- para a transmissao
  // e limpa a selecao pra nao ficar referenciando um id que nao existe mais.
  function limparRadialistaEPrograma() {
    pausarPrograma();
    radialistaIdRef.current = null;
    programaIdRef.current = null;
    setRadialistaId(null);
    setProgramaId(null);
  }

  function limparPrograma() {
    pausarPrograma();
    programaIdRef.current = null;
    setProgramaId(null);
  }

  // so inicia o programa sozinho quando o horario agendado de algum
  // programa cadastrado (de qualquer radialista) comecar; inicio manual
  // exige selecionar o programa e clicar em "Comecar transmissao"
  useEffect(() => {
    if (carregandoProgramas || programasTodos.length === 0) return;

    function verificarHorarioAgendado() {
      if (programaAtivoRef.current) return;

      const atual = programasTodos.find((p) => {
        const radialista = radialistas.find((r) => r.id === p.radialistaId);
        return radialista ? programaNoAr(p, radialista.timezone) : false;
      });
      if (atual) {
        const chave = `${atual.id}-${new Date().toDateString()}`;
        if (ultimoDisparoAutomaticoRef.current === chave) return;

        ultimoDisparoAutomaticoRef.current = chave;
        selecionarPrograma(atual, true);
        return;
      }

      // Nenhum programa no ar ainda: pre-aquece o proximo a entrar dentro de
      // ANTECEDENCIA_PREPARO_SEGUNDOS, pra quando o horario chegar (bloco acima) o 1o bloco
      // ja estar pronto (ver preencher()/jaPreAquecendoEsteMesmo em selecionarPrograma).
      const proximo = programasTodos.find((p) => {
        const radialista = radialistas.find((r) => r.id === p.radialistaId);
        if (!radialista) return false;
        const restante = segundosParaInicio(p, radialista.timezone);
        return restante !== null && restante <= ANTECEDENCIA_PREPARO_SEGUNDOS;
      });
      if (!proximo) return;

      const chaveProximo = `${proximo.id}-${new Date().toDateString()}`;
      if (preAquecidoAgendadoRef.current === chaveProximo) return;

      preAquecidoAgendadoRef.current = chaveProximo;
      selecionarPrograma(proximo);
    }

    verificarHorarioAgendado();
    const intervalo = setInterval(verificarHorarioAgendado, 15000);
    return () => clearInterval(intervalo);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [carregandoProgramas, programasTodos, radialistas]);

  // corte pontual no horario_fim: a fala de "encerramento" (ver gerarProximaFala) e' so'
  // um aviso gerado perto do fim, mas espera a musica/fala atual acabar de tocar antes de
  // ir ao ar -- sem isso o programa podia passar do horario com uma musica ainda rolando.
  // Esse watchdog roda em paralelo e corta na hora (pausarPrograma para musica e fala em
  // andamento), independente do que estiver no ar.
  //
  // So' se aplica a transmissao que o PROPRIO watchdog de horario agendado ligou (ver
  // verificarHorarioAgendado/iniciadoPeloAgendamentoRef) -- pra essa, "saiu do horario
  // configurado" so' pode significar "passou do horario_fim de hoje", entao cortar faz
  // sentido. Transmissao iniciada manualmente (clique em "Comecar transmissao") pode ser
  // fora do horario configurado do programa de proposito (teste, demo, plantao fora da
  // grade normal) -- programaNoAr() dava falso desde o primeiro segundo nesse caso, e o
  // watchdog pausava a transmissao sozinha ~1s depois de comecar, sem aviso nenhum pro
  // operador (so' descobria lendo o codigo). Transmissao manual so' para quando o operador
  // clicar em pausar.
  useEffect(() => {
    if (!programaAtivo || !iniciadoPeloAgendamentoRef.current) return;

    function verificarFimPontual() {
      const selecionado = programasTodos.find((p) => p.id === programaIdRef.current);
      const radialistaDoSelecionado = radialistas.find((r) => r.id === selecionado?.radialistaId);
      if (!selecionado || !radialistaDoSelecionado) return;
      if (!programaNoAr(selecionado, radialistaDoSelecionado.timezone)) {
        pausarPrograma();
      }
    }

    const intervalo = setInterval(verificarFimPontual, 1000);
    return () => clearInterval(intervalo);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [programaAtivo, programasTodos, radialistas]);

  const programaSelecionado = programasTodos.find((p) => p.id === programaId) ?? null;
  const radialistaSelecionado = programaSelecionado
    ? radialistas.find((r) => r.id === programaSelecionado.radialistaId) ?? null
    : null;
  const aoVivoAtivo = radialistaSelecionado?.ativo !== false && Boolean(radioConta?.wuzapi_token);
  const programaSelecionadoNoAr =
    programaSelecionado !== null &&
    radialistaSelecionado !== null &&
    programaNoAr(programaSelecionado, radialistaSelecionado.timezone);

  return {
    // estado pra renderizacao
    radialistas,
    radialistaId,
    programasTodos,
    carregandoProgramas,
    programaId,
    programaAtivo,
    gerandoFala,
    falasPrograma,
    erro,
    falhasAudioConsecutivas,
    avisoGravacao,
    abaEmSegundoPlano,
    musicaAtual,
    musicaFimSegundos,
    estagioAtual,
    totalFalas,
    programaSelecionado,
    radialistaSelecionado,
    programaSelecionadoNoAr,
    aoVivoAtivo,

    // acoes
    carregarRadialistasEProgramas,
    selecionarPrograma,
    iniciarPrograma,
    pausarPrograma,
    gerarProximaFala,
    pularFala,
    inserirNaTransmissao,
    limparRadialistaEPrograma,
    limparPrograma,

    // pra cartwall/transport reaproveitarem sem reimplementar
    duckMusicaFundo,
    musicPlayerRef,
    audioFalaRef,
    bgPlayerRef,
  };
}
