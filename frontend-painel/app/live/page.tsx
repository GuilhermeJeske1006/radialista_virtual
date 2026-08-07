"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import AppShell from "../../components/AppShell";
import { apiFetch, apiFetchBlob, ApiError } from "../../lib/api";
import { setRadialistaAtualId } from "../../lib/radialistas";
import { Radialista, Programa, DIAS_SEMANA_LABEL } from "../../lib/types";

declare global {
  interface Window {
    YT: any;
    onYouTubeIframeAPIReady: () => void;
  }
}

type Interaction = {
  id: number;
  telefone: string;
  mensagem_usuario: string;
  resposta: string | null;
  status: string;
  criado_em: string;
};

type ProgramSegment = {
  id: number;
  tipo: string;
  fala: string;
  criado_em: string;
  origem: "ia" | "local";
  video_id?: string | null;
  titulo_musica?: string | null;
};

type LiveProgramResponse = {
  tipo: string;
  fala: string;
  criado_em: string;
  video_id?: string | null;
  titulo_musica?: string | null;
};

type ProgramaOpcao = Programa & { radialistaId: number; radialistaNome: string };

type SegmentoPreparado = {
  segmento: Omit<ProgramSegment, "id">;
  audioUrl: string | null;
};

const STATUS_STYLE: Record<string, string> = {
  fila_musica: "bg-brand-50 text-brand-700",
  fila_abraco: "bg-pink-50 text-pink-700",
  guardado: "bg-gray-100 text-gray-600",
  bloqueado_horario: "bg-amber-50 text-amber-700",
  bloqueado_rate_limit: "bg-amber-50 text-amber-700",
  bloqueado_conteudo: "bg-red-50 text-red-700",
};

const STATUS_LABEL: Record<string, string> = {
  fila_musica: "Pedido de musica na fila",
  fila_abraco: "Na fila do alo",
  guardado: "So guardado",
  bloqueado_horario: "Fora do horario",
  bloqueado_rate_limit: "Limite atingido",
  bloqueado_conteudo: "Topico bloqueado",
};

const POLL_MS = 4000;
const INTERVALO_PROGRAMA_MS = 600;

function formatarHora(iso: string): string {
  return new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

const DIAS_SEMANA_ORDEM = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function horarioParaSegundos(horario: string): number {
  const [h, m, s] = horario.split(":").map(Number);
  return h * 3600 + m * 60 + (s || 0);
}

function dentroDaJanela(segundosAgora: number, inicioSeg: number, fimSeg: number): boolean {
  if (inicioSeg <= fimSeg) return segundosAgora >= inicioSeg && segundosAgora <= fimSeg;
  return segundosAgora >= inicioSeg || segundosAgora <= fimSeg;
}

function agoraNoFuso(timezone: string): { diaSemana: number; segundosDoDia: number } {
  const partes = new Intl.DateTimeFormat("en-US", {
    timeZone: timezone,
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).formatToParts(new Date());
  const obter = (tipo: string) => partes.find((p) => p.type === tipo)?.value ?? "";
  const diaSemana = DIAS_SEMANA_ORDEM.indexOf(obter("weekday"));
  const hora = Number(obter("hour")) % 24;
  const minuto = Number(obter("minute"));
  const segundo = Number(obter("second"));
  return { diaSemana, segundosDoDia: hora * 3600 + minuto * 60 + segundo };
}

// espelha app/guardrails/schedule.py (programa_no_ar / encontrar_programa_atual) do backend
function programaNoAr(programa: Programa, timezone: string): boolean {
  if (!programa.ativo) return false;
  const { diaSemana, segundosDoDia } = agoraNoFuso(timezone);
  if (programa.dias_semana.length > 0 && !programa.dias_semana.includes(diaSemana)) return false;
  return dentroDaJanela(segundosDoDia, horarioParaSegundos(programa.horario_inicio), horarioParaSegundos(programa.horario_fim));
}

function formatarDiasSemana(dias: number[]): string {
  if (dias.length === 0) return "Todos os dias";
  return dias
    .slice()
    .sort((a, b) => a - b)
    .map((d) => DIAS_SEMANA_LABEL[d])
    .join(", ");
}

function formatarFaixaHorario(p: { horario_inicio: string; horario_fim: string }): string {
  return `${p.horario_inicio.slice(0, 5)}-${p.horario_fim.slice(0, 5)}`;
}

function escolher(lista: string[], fallback: string) {
  return lista.length > 0 ? lista[Math.floor(Math.random() * lista.length)] : fallback;
}

function gerarFalaLocal(
  radialista: Radialista,
  programa: Programa,
  totalFalas: number
): Omit<ProgramSegment, "id" | "criado_em" | "origem"> {
  const nome = radialista.nome_locutor || "Locutor";
  const roteiro = ["abertura", "musica", "comentario", "noticia", "chamada_ouvinte"];
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

  return { tipo, fala: falas[tipo] };
}

export default function LivePage() {
  const [radialistas, setRadialistas] = useState<Radialista[]>([]);
  const [radialistaId, setRadialistaId] = useState<number | null>(null);
  const [programasTodos, setProgramasTodos] = useState<ProgramaOpcao[]>([]);
  const [carregandoProgramas, setCarregandoProgramas] = useState(true);
  const [programaId, setProgramaId] = useState<number | null>(null);
  const [interacoes, setInteracoes] = useState<Interaction[]>([]);
  const [carregandoInteracoes, setCarregandoInteracoes] = useState(true);
  const [programaAtivo, setProgramaAtivo] = useState(false);
  const [gerandoFala, setGerandoFala] = useState(false);
  const [falasPrograma, setFalasPrograma] = useState<ProgramSegment[]>([]);
  const [erro, setErro] = useState("");
  const [pulso, setPulso] = useState(false);
  const [musicaAtual, setMusicaAtual] = useState<string | null>(null);
  const ultimoIdRef = useRef<number | null>(null);
  const radialistaIdRef = useRef<number | null>(null);
  const programaIdRef = useRef<number | null>(null);
  const programaAtivoRef = useRef(false);
  const gerandoFalaRef = useRef(false);
  const falasProgramaRef = useRef<ProgramSegment[]>([]);
  const programaTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const ultimoDisparoAutomaticoRef = useRef<string | null>(null);
  const ytApiPromiseRef = useRef<Promise<void> | null>(null);
  const musicPlayerRef = useRef<any>(null);
  const musicStopRef = useRef<(() => void) | null>(null);
  const audioFalaRef = useRef<HTMLAudioElement | null>(null);
  const bgPlayerRef = useRef<any>(null);
  const bgProntoRef = useRef(false);
  const proximoPreparoRef = useRef<Promise<SegmentoPreparado> | null>(null);

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

  useEffect(() => {
    apiFetch<Radialista[]>("/config/radialistas")
      .then(async (lista) => {
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
      })
      .catch((err) => {
        setErro(err instanceof ApiError ? err.message : "Erro ao carregar radialistas");
        setCarregandoProgramas(false);
      });
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
    ultimoIdRef.current = null;
    setCarregandoInteracoes(true);

    radialistaIdRef.current = radialista.id;
    setRadialistaId(radialista.id);
    setRadialistaAtualId(radialista.id);

    programaIdRef.current = opcao.id;
    setProgramaId(opcao.id);

    if (iniciarAutomaticamente) iniciarPrograma();
  }

  useEffect(() => {
    if (radialistaId === null) return;
    let ativo = true;

    async function buscar() {
      try {
        const dados = await apiFetch<Interaction[]>(`/metrics/interactions?radialista_id=${radialistaId}&limit=30`);
        if (!ativo) return;
        if (dados.length > 0 && dados[0].id !== ultimoIdRef.current) {
          ultimoIdRef.current = dados[0].id;
          setPulso(true);
          setTimeout(() => setPulso(false), 700);
        }
        setInteracoes(dados);
        setErro("");
      } catch (err) {
        if (ativo) setErro(err instanceof ApiError ? err.message : "Erro ao carregar interacoes");
      } finally {
        if (ativo) setCarregandoInteracoes(false);
      }
    }

    buscar();
    const intervalo = setInterval(buscar, POLL_MS);
    return () => {
      ativo = false;
      clearInterval(intervalo);
    };
  }, [radialistaId]);

  function limparTimerPrograma() {
    if (programaTimerRef.current) {
      clearTimeout(programaTimerRef.current);
      programaTimerRef.current = null;
    }
  }

  function pararFala() {
    if (audioFalaRef.current) {
      audioFalaRef.current.pause();
      audioFalaRef.current = null;
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

      const fala = new SpeechSynthesisUtterance(texto);
      fala.lang = "pt-BR";
      fala.rate = 0.96;
      fala.pitch = 1;
      fala.onend = () => resolve();
      fala.onerror = () => resolve();
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(fala);
    });
  }

  // toca um audio ja sintetizado (preparado com antecedencia por prepararSegmento);
  // se nao tiver audio pronto (TTS indisponivel), cai pra voz do navegador
  async function reproduzirAudioPreparado(audioUrl: string | null, texto: string): Promise<void> {
    duckMusicaFundo(true);
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
        return;
      }
      await falarComVozNavegador(texto);
    } finally {
      duckMusicaFundo(false);
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
    try {
      const musica = await apiFetch<{ video_id: string; titulo: string }>(
        `/live/${radialistaIdRef.current}/programas/${programaIdRef.current}/musica-fundo`
      );
      videoId = musica.video_id;
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
      playerVars: { autoplay: 1, controls: 0, loop: 1, playlist: videoId },
      events: {
        onReady: (evento: any) => {
          bgProntoRef.current = true;
          evento.target.setVolume(VOLUME_FUNDO_NORMAL);
          evento.target.playVideo();
        },
        onStateChange: (evento: any) => {
          if (evento.data === window.YT.PlayerState.ENDED) evento.target.playVideo();
        },
      },
    });
  }

  function tocarMusica(videoId: string, titulo: string): Promise<void> {
    const TIMEOUT_SEGURANCA_MS = 6 * 60 * 1000;

    return new Promise((resolvePromise) => {
      async function iniciar() {
        if (typeof window === "undefined" || !ytApiPromiseRef.current) {
          resolvePromise();
          return;
        }

        try {
          await ytApiPromiseRef.current;
        } catch {
          resolvePromise();
          return;
        }

        if (!window.YT || !window.YT.Player) {
          resolvePromise();
          return;
        }

        setMusicaAtual(titulo || "Musica ao vivo");
        if (bgProntoRef.current) bgPlayerRef.current?.setVolume(0); // pedido do ouvinte toca sozinho, sem o fundo

        let finalizado = false;
        let timeoutId: ReturnType<typeof setTimeout>;
        const finalizar = () => {
          if (finalizado) return;
          finalizado = true;
          clearTimeout(timeoutId);
          musicStopRef.current = null;
          try {
            musicPlayerRef.current?.stopVideo?.();
          } catch {
            // ignora falha ao parar o player
          }
          if (bgProntoRef.current) bgPlayerRef.current?.setVolume(VOLUME_FUNDO_NORMAL);
          setMusicaAtual(null);
          resolvePromise();
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
          playerVars: { autoplay: 1, controls: 0 },
          events: {
            onReady: (evento: any) => evento.target.playVideo(),
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
    return novaFala;
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
          }),
        }
      );
      segmento = { ...resposta, origem: "ia" };
      setErro("");
    } catch (err) {
      const radialistaAtual = radialistas.find((r) => r.id === radialistaIdRef.current);
      const programaAtual = programasTodos.find((p) => p.id === programaIdRef.current);
      if (radialistaAtual && programaAtual) {
        const local = gerarFalaLocal(radialistaAtual, programaAtual, falasProgramaRef.current.length);
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

    let audioUrl: string | null = null;
    try {
      if (!radialistaIdRef.current) throw new Error("sem radialista selecionado");
      const audioBlob = await apiFetchBlob(`/live/${radialistaIdRef.current}/tts`, {
        method: "POST",
        body: JSON.stringify({ texto: segmento.fala }),
      });
      audioUrl = URL.createObjectURL(audioBlob);
    } catch {
      audioUrl = null; // backend TTS indisponivel -- cai pra voz do navegador na hora de tocar
    }

    return { segmento, audioUrl };
  }

  function descartarPreparo() {
    proximoPreparoRef.current?.then((preparado) => {
      if (preparado.audioUrl) URL.revokeObjectURL(preparado.audioUrl);
    }).catch(() => {});
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

    gerandoFalaRef.current = true;
    setGerandoFala(true);
    setErro("");

    const preparado = await (proximoPreparoRef.current ?? prepararSegmento());
    proximoPreparoRef.current = null;

    const novaFala = adicionarFala(preparado.segmento);
    limparTimerPrograma();

    // ja dispara a preparacao do proximo bloco em paralelo com a fala atual
    // no ar -- e o que deixa as falas coladas, sem vazio entre elas
    if (programaAtivoRef.current) {
      proximoPreparoRef.current = prepararSegmento();
    }

    gerandoFalaRef.current = false;
    setGerandoFala(false);

    if (novaFala.tipo === "musica" && novaFala.video_id) {
      try {
        await reproduzirAudioPreparado(preparado.audioUrl, novaFala.fala);
        await tocarMusica(novaFala.video_id, novaFala.titulo_musica ?? "");
      } catch {
        // segue o programa mesmo se a musica falhar ao tocar
      }
    } else {
      await reproduzirAudioPreparado(preparado.audioUrl, novaFala.fala);
    }

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
    iniciarMusicaFundo();
    gerarProximaFala(true);
  }

  function pausarPrograma() {
    limparTimerPrograma();
    programaAtivoRef.current = false;
    setProgramaAtivo(false);
    pararFala();
    musicStopRef.current?.();
    pararMusicaFundo();
    descartarPreparo();

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

  const programaSelecionado = programasTodos.find((p) => p.id === programaId) ?? null;
  const radialistaSelecionado = programaSelecionado
    ? radialistas.find((r) => r.id === programaSelecionado.radialistaId) ?? null
    : null;
  const nomeLocutor = radialistaSelecionado?.nome_locutor || "Locutor";
  const aoVivoAtivo = radialistaSelecionado?.ativo !== false && Boolean(radialistaSelecionado?.wuzapi_token);
  const programaSelecionadoNoAr =
    programaSelecionado !== null && radialistaSelecionado !== null && programaNoAr(programaSelecionado, radialistaSelecionado.timezone);

  return (
    <AppShell title="Ao Vivo" maxWidthClassName="max-w-7xl">
      <div id="yt-live-player" className="pointer-events-none fixed left-[-9999px] top-0 h-px w-px overflow-hidden" />
      <div id="yt-bg-player" className="pointer-events-none fixed left-[-9999px] top-0 h-px w-px overflow-hidden" />

      {erro && <p className="text-sm text-red-600 mb-4">{erro}</p>}

      <section className="bg-white rounded-2xl border border-gray-200 shadow-theme-xs p-6 mb-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex-1 min-w-0">
            <h2 className="text-base font-semibold text-gray-900">1. Selecionar programa</h2>
            <p className="text-sm text-gray-500 mt-1">
              Escolha o programa que vai ao ar. Locutor, repertorio, assuntos, voz e horario sao carregados
              automaticamente a partir dele.
            </p>

            <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center">
              <select
                className="w-full sm:max-w-sm rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:border-brand-300 focus:ring-2 focus:ring-brand-500/20"
                value={programaId ?? ""}
                disabled={carregandoProgramas || programaAtivo}
                onChange={(e) => {
                  const valor = e.target.value ? Number(e.target.value) : null;
                  const opcao = programasTodos.find((p) => p.id === valor);
                  if (opcao) selecionarPrograma(opcao);
                }}
              >
                <option value="">
                  {carregandoProgramas
                    ? "Carregando programas..."
                    : programasTodos.length === 0
                      ? "Nenhum programa cadastrado"
                      : "Selecione um programa"}
                </option>
                {radialistas.map((r) => {
                  const doRadialista = programasTodos.filter((p) => p.radialistaId === r.id);
                  if (doRadialista.length === 0) return null;
                  return (
                    <optgroup key={r.id} label={r.nome_locutor || `Radialista #${r.id}`}>
                      {doRadialista.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.nome} · {formatarFaixaHorario(p)}
                        </option>
                      ))}
                    </optgroup>
                  );
                })}
              </select>

              {!programaAtivo ? (
                <button
                  type="button"
                  onClick={iniciarPrograma}
                  disabled={!programaId || gerandoFala}
                  className="rounded-lg bg-red-500 px-4 py-2.5 text-sm font-medium text-white hover:bg-red-600 disabled:opacity-60 disabled:cursor-not-allowed shrink-0"
                >
                  Comecar transmissao
                </button>
              ) : (
                <button
                  type="button"
                  onClick={pausarPrograma}
                  className="rounded-lg bg-gray-700 px-4 py-2.5 text-sm font-medium text-white hover:bg-gray-800 shrink-0"
                >
                  Pausar transmissao
                </button>
              )}
            </div>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            <span
              className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${
                aoVivoAtivo ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
              }`}
            >
              {aoVivoAtivo ? "Agente online" : "Aguardando conexao"}
            </span>
            <div className="flex items-center gap-2">
              <span className="relative flex h-2.5 w-2.5">
                <span
                  className={`absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75 ${
                    pulso ? "animate-ping" : ""
                  }`}
                />
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-red-500" />
              </span>
              <span className="text-xs font-semibold tracking-wide text-gray-500">AO VIVO</span>
            </div>
          </div>
        </div>

        {programaSelecionado && (
          <div className="mt-5 flex flex-wrap items-center gap-2 border-t border-gray-100 pt-4">
            <span className="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-700">
              Radialista: {programaSelecionado.radialistaNome}
            </span>
            <span className="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-700">
              Voz: {radialistaSelecionado?.voz_id ?? "padrao"}
            </span>
            <span className="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-700">
              Generos:{" "}
              {programaSelecionado.generos_musicais.length > 0
                ? programaSelecionado.generos_musicais.slice(0, 3).join(", ")
                : "livre"}
              {programaSelecionado.generos_musicais.length > 3
                ? ` +${programaSelecionado.generos_musicais.length - 3}`
                : ""}
            </span>
            <span className="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-700">
              Dias: {formatarDiasSemana(programaSelecionado.dias_semana)}
            </span>
            <span className="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-700">
              Horario: {formatarFaixaHorario(programaSelecionado)}
            </span>
            <span
              className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                programaSelecionadoNoAr ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
              }`}
            >
              {programaSelecionadoNoAr ? "No ar agora" : "Fora do horario agendado"}
            </span>
            <Link
              href={`/dashboard/${programaSelecionado.radialistaId}`}
              className="text-xs font-medium text-brand-600 hover:text-brand-700 ml-auto"
            >
              Editar radialista
            </Link>
            <Link
              href={`/dashboard/${programaSelecionado.radialistaId}/programas/${programaSelecionado.id}`}
              className="text-xs font-medium text-brand-600 hover:text-brand-700"
            >
              Editar programa
            </Link>
          </div>
        )}
      </section>

      {!programaId ? (
        <section className="bg-white rounded-2xl border border-dashed border-gray-300 p-10 text-center">
          <p className="text-sm text-gray-500">
            Selecione um programa acima para carregar os dados do locutor e liberar a transmissao.
          </p>
        </section>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_380px] gap-5 items-start">
          <section
            className={`rounded-2xl border shadow-theme-xs p-6 transition-colors ${
              programaAtivo ? "bg-white border-red-200 ring-1 ring-red-100" : "bg-white border-gray-200"
            }`}
          >
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div className="flex items-start gap-3">
                {programaAtivo && (
                  <span className="relative flex h-2.5 w-2.5 mt-1.5 shrink-0">
                    <span className="absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75 animate-ping" />
                    <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-red-500" />
                  </span>
                )}
                <div>
                  <h2 className="text-base font-semibold text-gray-900">
                    2. Programa no ar{" "}
                    <span className={`text-xs font-medium ${programaAtivo ? "text-red-600" : "text-gray-400"}`}>
                      {programaAtivo ? "· transmitindo" : "· pausado"}
                    </span>
                  </h2>
                  <p className="text-sm text-gray-500 mt-1">
                    O agente gera chamadas, comentarios, noticias e blocos musicais conforme a configuracao do
                    programa.
                  </p>
                  {musicaAtual && (
                    <p className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-700">
                      Tocando agora: {musicaAtual}
                    </p>
                  )}
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => gerarProximaFala(true)}
                  disabled={gerandoFala}
                  className="rounded-lg border border-gray-300 px-4 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {gerandoFala ? "Gerando..." : "Proxima fala"}
                </button>
              </div>
            </div>

            <div className="mt-5 rounded-xl border border-gray-200 bg-gray-50 p-4 min-h-32 max-h-96 overflow-y-auto">
              {falasPrograma.length === 0 ? (
                <p className="text-sm text-gray-500">
                  {programaAtivo
                    ? "Gerando a primeira fala..."
                    : "Clique em comecar transmissao acima, ou aguarde o horario agendado comecar."}
                </p>
              ) : (
                <div className="space-y-3">
                  {falasPrograma.map((fala, index) => (
                    <article
                      key={fala.id}
                      className={
                        index === 0
                          ? "rounded-lg bg-white border border-red-100 p-3 text-gray-900 shadow-theme-xs"
                          : "text-gray-600"
                      }
                    >
                      <div className="flex flex-wrap items-center gap-2 mb-1">
                        <span className="rounded-full bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700">
                          {fala.tipo.replace("_", " ")}
                        </span>
                        <span className="text-xs text-gray-400">{formatarHora(fala.criado_em)}</span>
                        {fala.origem === "local" && (
                          <span className="rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">
                            fallback local
                          </span>
                        )}
                        {index === 0 && gerandoFala && (
                          <span className="text-xs text-gray-400 italic">gerando proxima...</span>
                        )}
                      </div>
                      <p className={`text-sm leading-6 ${index === 0 ? "font-medium" : ""}`}>{fala.fala}</p>
                    </article>
                  ))}
                </div>
              )}
            </div>
          </section>

          <section className="bg-white rounded-2xl border border-gray-200 shadow-theme-xs p-6 lg:sticky lg:top-22 lg:max-h-[calc(100vh-6.5rem)] flex flex-col">
            <div className="flex items-center justify-between mb-4 shrink-0">
              <h2 className="text-base font-semibold text-gray-900">Conversas</h2>
              <span className="text-xs font-medium text-gray-400">Atualiza a cada 4s</span>
            </div>

            {carregandoInteracoes ? (
              <p className="text-sm text-gray-500">Carregando conversas...</p>
            ) : interacoes.length === 0 ? (
              <p className="text-sm text-gray-500">
                Nenhuma interacao ainda. Assim que um ouvinte mandar mensagem no WhatsApp, ela aparece aqui.
              </p>
            ) : (
              <div className="space-y-3 overflow-y-auto pr-1 -mr-1">
                {interacoes.map((it) => (
                  <article key={it.id} className="rounded-xl border border-gray-200 p-4">
                    <div className="flex items-center justify-between text-xs text-gray-400 mb-2">
                      <span>Ouvinte {it.telefone}</span>
                      <span>{formatarHora(it.criado_em)}</span>
                    </div>

                    <div className="text-sm text-gray-800 mb-2">
                      <span className="font-medium text-gray-500">Ouvinte: </span>
                      {it.mensagem_usuario}
                    </div>

                    {it.resposta && (
                      <div className="text-sm text-gray-800">
                        <span className="font-medium text-brand-600">{nomeLocutor}: </span>
                        {it.resposta}
                      </div>
                    )}

                    <div className="mt-3">
                      <span
                        className={`inline-block text-xs font-medium px-2 py-0.5 rounded-full ${
                          STATUS_STYLE[it.status] ?? "bg-gray-100 text-gray-600"
                        }`}
                      >
                        {STATUS_LABEL[it.status] ?? it.status}
                      </span>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </AppShell>
  );
}
