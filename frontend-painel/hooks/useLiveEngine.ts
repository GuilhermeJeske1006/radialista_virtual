"use client";

import { useEffect, useRef, useState } from "react";
import { apiFetch, apiFetchBlob, ApiError } from "../lib/api";
import { setRadialistaAtualId } from "../lib/radialistas";
import { Radialista, Programa, RadioConta } from "../lib/types";
import {
  AudioFala,
  EstagioAoVivo,
  LiveProgramResponse,
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

const INTERVALO_PROGRAMA_MS = 2200;

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

function escolher(lista: string[], fallback: string) {
  return lista.length > 0 ? lista[Math.floor(Math.random() * lista.length)] : fallback;
}

// roteiro de EMERGENCIA (TTS/LLM indisponivel), usado so' quando POST /live/.../proxima falha.
// Atencao: essa ordem e' DIFERENTE do _ROTEIRO_PADRAO real do motor (backend/app/live/router.py),
// que comeca por "musica" -- nao usar como referencia pra preview de proximos blocos.
function gerarFalaLocal(
  radialista: Radialista,
  programa: Programa,
  totalFalas: number
): Omit<ProgramSegment, "id" | "criado_em" | "origem"> {
  const nome = radialista.nome_locutor || "Locutor";
  const roteiroPadrao = ["abertura", "musica", "comentario", "noticia", "chamada_ouvinte"];
  const roteiroCustom = programa.estrutura_blocos.map((b) => b.trim()).filter(Boolean);
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
    abertura: `Muito bem, aqui e ${nome} chegando junto no ${programa.nome}. A partir de agora a gente segue com ${assunto}, boa musica e aquele clima de radio perto do ouvinte.`,
    musica: `Na sequencia eu vou puxar o clima para ${musica}. Fica comigo porque a ideia e manter o ritmo gostoso, sem sair do perfil da radio.`,
    comentario: `Falando rapidinho sobre ${assunto}, vale acompanhar o movimento e sentir o pulso do que esta acontecendo por ai. Me chama no WhatsApp que eu trago sua mensagem para a conversa.`,
    noticia: `Espaco para ${noticia} por aqui, sempre com cuidado e sem inventar informacao recente. Quando a pesquisa estiver liberada, eu busco nas fontes configuradas antes de cravar qualquer detalhe.`,
    chamada_ouvinte: `Agora eu quero ouvir quem esta do outro lado. Manda seu recado, pede sua musica dentro do nosso repertorio e ajuda o programa a ganhar cara de ao vivo.`,
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
  const ultimoDisparoAutomaticoRef = useRef<string | null>(null);
  const ytApiPromiseRef = useRef<Promise<void> | null>(null);
  const musicPlayerRef = useRef<any>(null);
  const musicStopRef = useRef<(() => void) | null>(null);
  const audioFalaRef = useRef<HTMLAudioElement | null>(null);
  const bgPlayerRef = useRef<any>(null);
  const bgProntoRef = useRef(false);
  const bgIntervaloFimRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const proximoPreparoRef = useRef<Promise<SegmentoPreparado> | null>(null);
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

    if (iniciarAutomaticamente) iniciarPrograma();
  }

  function limparTimerPrograma() {
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

  function falarComVozNavegador(texto: string): Promise<void> {
    return new Promise((resolve) => {
      if (typeof window === "undefined" || !("speechSynthesis" in window)) {
        resolve();
        return;
      }

      // Chrome as vezes engasga o speechSynthesis com a aba em segundo plano/minimizada:
      // nem onend nem onerror disparam, e a promise fica pendurada pra sempre -- travando
      // o loop inteiro do ao vivo (gerarProximaFala fica esperando ela). Timeout de seguranca
      // resolve mesmo se o evento nunca vier, baseado no tamanho do texto (fala mais longa
      // demora mais).
      let resolvida = false;
      const encerrar = () => {
        if (resolvida) return;
        resolvida = true;
        resolve();
      };
      const timeoutMs = Math.max(8000, texto.length * 150);
      const timeoutId = window.setTimeout(encerrar, timeoutMs);

      const fala = new SpeechSynthesisUtterance(texto);
      fala.lang = "pt-BR";
      fala.rate = 0.96;
      fala.pitch = 1;
      fala.onend = () => {
        window.clearTimeout(timeoutId);
        encerrar();
      };
      fala.onerror = () => {
        window.clearTimeout(timeoutId);
        encerrar();
      };
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(fala);
    });
  }

  // toca um audio ja sintetizado (preparado com antecedencia por prepararSegmento);
  // se nao tiver audio pronto (TTS indisponivel), cai pra voz do navegador.
  // Devolve quanto tempo (segundos, medido no relogio de parede) o audio ficou
  // realmente no ar -- e' a duracao REAL da fala, nao uma estimativa (ver
  // atualizarDuracaoFala, que soma isso por bloco).
  async function reproduzirAudioPreparado(audioUrl: string | null, texto: string): Promise<number> {
    const inicio = Date.now();
    duckMusicaFundo(true);
    setEstagioAtual("fala");
    try {
      if (audioUrl) {
        const audio = new Audio(audioUrl);
        audioFalaRef.current = audio;
        await new Promise<void>((resolve) => {
          audio.onended = () => resolve();
          audio.onerror = () => resolve();
          audio.play().catch(() => resolve());
        });
        URL.revokeObjectURL(audioUrl);
        if (audioFalaRef.current === audio) {
          audioFalaRef.current = null;
        }
        return (Date.now() - inicio) / 1000;
      }
      await falarComVozNavegador(texto);
      return (Date.now() - inicio) / 1000;
    } finally {
      duckMusicaFundo(false);
      setEstagioAtual("idle");
    }
  }

  const VOLUME_FUNDO_NORMAL = 18;
  const VOLUME_FUNDO_BAIXO = 6;

  function duckMusicaFundo(baixo: boolean) {
    if (!bgProntoRef.current || !bgPlayerRef.current) return;
    try {
      bgPlayerRef.current.setVolume(baixo ? VOLUME_FUNDO_BAIXO : VOLUME_FUNDO_NORMAL);
    } catch {
      // ignora falha ao ajustar volume da musica de fundo
    }
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
      playerVars: { autoplay: 1, controls: 0, loop: 1, playlist: videoId, start: inicioSegundos },
      events: {
        onReady: (evento: any) => {
          bgProntoRef.current = true;
          evento.target.setVolume(VOLUME_FUNDO_NORMAL);
          evento.target.playVideo();
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
    fimSegundos: number | null = null
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
        if (bgProntoRef.current) bgPlayerRef.current?.setVolume(0); // pedido do ouvinte toca sozinho, sem o fundo

        let finalizado = false;
        let timeoutId: ReturnType<typeof setTimeout>;
        let intervaloFimId: ReturnType<typeof setInterval> | undefined;
        const finalizar = () => {
          if (finalizado) return;
          finalizado = true;
          clearTimeout(timeoutId);
          if (intervaloFimId) clearInterval(intervaloFimId);
          musicStopRef.current = null;
          try {
            musicPlayerRef.current?.stopVideo?.();
          } catch {
            // ignora falha ao parar o player
          }
          if (bgProntoRef.current) bgPlayerRef.current?.setVolume(VOLUME_FUNDO_NORMAL);
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
          playerVars: { autoplay: 1, controls: 0, start: inicioSegundos },
          events: {
            onReady: (evento: any) => {
              evento.target.playVideo();
              // corta antes de silencio longo/fala no final da faixa (analisado no
              // backend, ver app/live/audio_analysis.py) -- sem isso tocaria ate o
              // fim real do video, que pode ter trecho falado ou vazio.
              if (fimSegundos != null) {
                intervaloFimId = setInterval(() => {
                  const atual = musicPlayerRef.current?.getCurrentTime?.();
                  if (typeof atual === "number" && atual >= fimSegundos) finalizar();
                }, POLL_FIM_MS);
              }
            },
            onStateChange: (evento: any) => {
              if (evento.data === window.YT.PlayerState.ENDED) finalizar();
            },
            onError: () => finalizar(),
          },
        });
      }

      iniciar();
    });
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

  // gera o texto e ja sintetiza o audio do proximo bloco, sem tocar --
  // chamado com antecedencia (enquanto o bloco atual esta no ar) pra nao
  // ter vazio entre uma fala e outra
  async function prepararSegmento(): Promise<SegmentoPreparado> {
    let segmento: Omit<ProgramSegment, "id">;
    try {
      const resposta = await apiFetch<LiveProgramResponse>(
        `/live/${radialistaIdRef.current}/programas/${programaIdRef.current}/proxima`,
        {
          method: "POST",
          body: JSON.stringify({
            historico: falasProgramaRef.current
              .slice(0, 8)
              .reverse()
              .map((fala) => `${fala.tipo}: ${fala.fala}`),
            total_falas: totalFalasRef.current,
          }),
        }
      );
      segmento = { ...resposta, origem: "ia" };
      setErro("");
    } catch (err) {
      const radialistaAtual = radialistas.find((r) => r.id === radialistaIdRef.current);
      const programaAtual = programasTodos.find((p) => p.id === programaIdRef.current);
      if (radialistaAtual && programaAtual) {
        const local = gerarFalaLocal(radialistaAtual, programaAtual, totalFalasRef.current);
        segmento = { ...local, criado_em: new Date().toISOString(), origem: "local" };
        setErro(err instanceof ApiError ? `${err.message}. Usando fala local.` : "IA indisponivel. Usando fala local.");
      } else {
        segmento = {
          tipo: "comentario",
          fala: "Seguimos no ar, ja volto com mais uma novidade.",
          criado_em: new Date().toISOString(),
          origem: "local",
        };
        setErro(err instanceof ApiError ? err.message : "IA indisponivel");
      }
    }

    // dialogo multi-voz (mais de um radialista no programa): busca um audio por linha,
    // cada uma com a voz do radialista que falou -- em vez de um audio unico pro bloco.
    if (segmento.falas && segmento.falas.length > 0 && radialistaIdRef.current) {
      const audiosFalas = await Promise.all(
        segmento.falas.map(async (linha): Promise<AudioFala> => {
          try {
            const blob = await apiFetchBlob(`/live/${radialistaIdRef.current}/tts`, {
              method: "POST",
              body: JSON.stringify({ texto: linha.texto, tipo: segmento.tipo, voz_id: linha.voz_id }),
            });
            return { url: URL.createObjectURL(blob), blob };
          } catch {
            return { url: null, blob: null };
          }
        })
      );
      return { segmento, audioUrl: null, audioBlob: null, audiosFalas };
    }

    let audioUrl: string | null = null;
    let audioBlob: Blob | null = null;
    try {
      if (!radialistaIdRef.current) throw new Error("sem radialista selecionado");
      // patrocinador com audio pre-gravado ou vinheta: toca o arquivo direto, sem TTS
      audioBlob =
        segmento.tipo === "patrocinador" && segmento.patrocinador_audio && segmento.patrocinador_id
          ? await apiFetchBlob(`/patrocinadores/${segmento.patrocinador_id}/audio`)
          : segmento.tipo === "vinheta" && segmento.vinheta_id
            ? await apiFetchBlob(`/biblioteca-audio/${segmento.vinheta_id}/audio`)
            : await apiFetchBlob(`/live/${radialistaIdRef.current}/tts`, {
                method: "POST",
                body: JSON.stringify({
                  texto: segmento.fala,
                  tipo: segmento.tipo,
                  voz_id: segmento.patrocinador_voz_id ?? null,
                }),
              });
      audioUrl = URL.createObjectURL(audioBlob);
    } catch {
      audioUrl = null; // backend TTS/audio indisponivel -- cai pra voz do navegador na hora de tocar
      audioBlob = null;
    }

    return { segmento, audioUrl, audioBlob, audiosFalas: null };
  }

  function descartarPreparo() {
    proximoPreparoRef.current
      ?.then((preparado) => {
        if (preparado.audioUrl) URL.revokeObjectURL(preparado.audioUrl);
        preparado.audiosFalas?.forEach((a) => a.url && URL.revokeObjectURL(a.url));
      })
      .catch(() => {});
    proximoPreparoRef.current = null;
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

    const preparado = await (proximoPreparoRef.current ?? prepararSegmento());
    proximoPreparoRef.current = null;

    // usuario clicou "Pausar transmissao" enquanto essa fala/audio ainda estava sendo
    // preparada (busca no backend nao e' cancelavel) -- descarta em vez de por no ar,
    // senao a transmissao "pausada" segue falando/tocando musica mesmo assim.
    if (!programaAtivoRef.current) {
      if (preparado.audioUrl) URL.revokeObjectURL(preparado.audioUrl);
      preparado.audiosFalas?.forEach((a) => a.url && URL.revokeObjectURL(a.url));
      gerandoFalaRef.current = false;
      setGerandoFala(false);
      return;
    }

    if (preparado.audioBlob) {
      gravacaoBlobsRef.current.push(preparado.audioBlob);
    }
    preparado.audiosFalas?.forEach((a) => a.blob && gravacaoBlobsRef.current.push(a.blob));

    const novaFala = adicionarFala(preparado.segmento);
    limparTimerPrograma();

    // ja dispara a preparacao do proximo bloco em paralelo com a fala atual
    // no ar -- e o que deixa as falas coladas, sem vazio entre elas
    if (programaAtivoRef.current) {
      proximoPreparoRef.current = prepararSegmento();
    }

    gerandoFalaRef.current = false;
    setGerandoFala(false);

    // Duracao REAL do bloco inteiro: soma o tempo de ar de cada musica + cada fala que
    // compoe ele (medido no relogio de parede por reproduzirAudioPreparado/tocarMusica),
    // em vez de uma estimativa -- grava no historico ao final (ver atualizarDuracaoFala).
    let duracaoBlocoSegundos = 0;

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
            musica.fim_segundos ?? null
          );
        }
      } catch {
        // segue o programa mesmo se a musica falhar ao tocar
      }
    } else if (preparado.audiosFalas && preparado.audiosFalas.length > 0) {
      // dialogo multi-voz: toca uma linha de cada vez, na voz de quem falou
      for (let i = 0; i < preparado.audiosFalas.length; i++) {
        if (!programaAtivoRef.current || execucaoAtualRef.current !== minhaExecucao) break;
        const textoLinha = novaFala.falas?.[i]?.texto ?? novaFala.fala;
        duracaoBlocoSegundos += await reproduzirAudioPreparado(preparado.audiosFalas[i].url, textoLinha);
      }
    } else {
      duracaoBlocoSegundos += await reproduzirAudioPreparado(preparado.audioUrl, novaFala.fala);
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
      setErro(err instanceof ApiError ? err.message : "Erro ao tocar audio");
    }

    gerandoFalaRef.current = false;
    setGerandoFala(false);

    if (execucaoAtualRef.current !== minhaExecucao) {
      if (audioUrl) URL.revokeObjectURL(audioUrl);
      return;
    }

    const novaFala = adicionarFala({
      tipo: "vinheta",
      fala: item.nome,
      criado_em: new Date().toISOString(),
      origem: "manual",
      vinheta_id: item.id,
    });

    if (audioBlob) gravacaoBlobsRef.current.push(audioBlob);

    // dispara o proximo bloco normal do roteiro em paralelo -- descartarPreparo() acima
    // jogou fora o que estava preparado antes, entao precisa regerar
    if (programaAtivoRef.current) {
      proximoPreparoRef.current = prepararSegmento();
    }

    const duracaoSegundos = await reproduzirAudioPreparado(audioUrl, novaFala.fala);
    atualizarDuracaoFala(novaFala.id, duracaoSegundos);

    if (execucaoAtualRef.current !== minhaExecucao) return;

    if (programaAtivoRef.current) {
      programaTimerRef.current = setTimeout(() => gerarProximaFala(), INTERVALO_PROGRAMA_MS);
    }
  }

  function iniciarPrograma() {
    if (!radialistaIdRef.current || !programaIdRef.current) {
      setErro("Selecione um programa antes de iniciar.");
      return;
    }
    limparTimerPrograma();
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
    programaAtivoRef.current = false;
    setProgramaAtivo(false);
    setAbaEmSegundoPlano(false);
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
      if (!atual) return;

      const chave = `${atual.id}-${new Date().toDateString()}`;
      if (ultimoDisparoAutomaticoRef.current === chave) return;

      ultimoDisparoAutomaticoRef.current = chave;
      selecionarPrograma(atual, true);
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
  useEffect(() => {
    if (!programaAtivo) return;

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
