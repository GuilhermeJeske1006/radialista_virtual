"use client";

import { useEffect, useRef, useState } from "react";
import AppShell from "../../components/AppShell";
import Modal from "../../components/Modal";
import EditarRadialistaForm from "../../components/EditarRadialistaForm";
import EditarProgramaForm from "../../components/EditarProgramaForm";
import { apiFetch, apiFetchBlob, ApiError } from "../../lib/api";
import { setRadialistaAtualId } from "../../lib/radialistas";
import { Radialista, Programa, RadioConta, DIAS_SEMANA_LABEL } from "../../lib/types";
import { OndaLed, OndaSpin, OndaWaveform } from "../../components/OndaLogo";

declare global {
  interface Window {
    YT: any;
    onYouTubeIframeAPIReady: () => void;
  }
}

type Interaction = {
  id: number;
  telefone: string;
  nome: string | null;
  mensagem_usuario: string;
  resposta: string | null;
  status: string;
  criado_em: string;
};

type MusicaBloco = { video_id: string; titulo: string; inicio_segundos?: number; fim_segundos?: number | null };

// Uma linha de dialogo multi-voz (ver ProgramaRadialista no backend) -- so vem preenchido
// quando o programa tem mais de um radialista, uma linha por participante que falou no bloco.
type FalaItem = { radio_config_id: number; nome_locutor: string; voz_id: string | null; texto: string };

type ProgramSegment = {
  id: number;
  tipo: string;
  fala: string;
  criado_em: string;
  origem: "ia" | "local";
  video_id?: string | null;
  titulo_musica?: string | null;
  inicio_segundos?: number;
  fim_segundos?: number | null;
  musicas?: MusicaBloco[];
  patrocinador_id?: number | null;
  patrocinador_audio?: boolean;
  patrocinador_voz_id?: string | null;
  falas?: FalaItem[] | null;
};

type LiveProgramResponse = {
  tipo: string;
  fala: string;
  criado_em: string;
  video_id?: string | null;
  titulo_musica?: string | null;
  inicio_segundos?: number;
  fim_segundos?: number | null;
  musicas?: MusicaBloco[];
  patrocinador_id?: number | null;
  patrocinador_audio?: boolean;
  patrocinador_voz_id?: string | null;
  falas?: FalaItem[] | null;
};

type ProgramaOpcao = Programa & { radialistaId: number; radialistaNome: string };

type AudioFala = { url: string | null; blob: Blob | null };

type SegmentoPreparado = {
  segmento: Omit<ProgramSegment, "id">;
  audioUrl: string | null;
  audioBlob: Blob | null;
  // dialogo multi-voz: um audio por linha/radialista, tocados em sequencia -- null quando
  // o bloco e' de um radialista so (usa audioUrl/audioBlob acima, como sempre foi).
  audiosFalas: AudioFala[] | null;
};

const STATUS_STYLE: Record<string, string> = {
  fila_musica: "bg-teal/10 text-teal",
  fila_abraco: "bg-amber/10 text-amber",
  guardado: "bg-paper/10 text-fg/60",
  bloqueado_horario: "bg-amber/10 text-amber",
  bloqueado_rate_limit: "bg-amber/10 text-amber",
  bloqueado_conteudo: "bg-rust/10 text-rust",
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
const INTERVALO_PROGRAMA_MS = 2200;

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
function programaNoAr(programa: Programa, timezone: string): boolean {
  if (!programa.ativo) return false;
  const { diaSemana, dataIso, segundosDoDia } = agoraNoFuso(timezone);
  if (programa.data_especifica) {
    if (programa.data_especifica !== dataIso) return false;
  } else if (programa.dias_semana.length > 0 && !programa.dias_semana.includes(diaSemana)) {
    return false;
  }
  return dentroDaJanela(segundosDoDia, horarioParaSegundos(programa.horario_inicio), horarioParaSegundos(programa.horario_fim));
}

function formatarDiasSemana(dias: number[], dataEspecifica?: string | null): string {
  if (dataEspecifica) return `Avulso em ${dataEspecifica.split("-").reverse().join("/")}`;
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

export default function LivePage() {
  const [radialistas, setRadialistas] = useState<Radialista[]>([]);
  const [radialistaId, setRadialistaId] = useState<number | null>(null);
  const [radioConta, setRadioConta] = useState<RadioConta | null>(null);
  const [programasTodos, setProgramasTodos] = useState<ProgramaOpcao[]>([]);
  const [carregandoProgramas, setCarregandoProgramas] = useState(true);
  const [programaId, setProgramaId] = useState<number | null>(null);
  const [interacoes, setInteracoes] = useState<Interaction[]>([]);
  const [carregandoInteracoes, setCarregandoInteracoes] = useState(true);
  const [programaAtivo, setProgramaAtivo] = useState(false);
  const [gerandoFala, setGerandoFala] = useState(false);
  const [falasPrograma, setFalasPrograma] = useState<ProgramSegment[]>([]);
  const [erro, setErro] = useState("");
  const [avisoGravacao, setAvisoGravacao] = useState("");
  const [abaEmSegundoPlano, setAbaEmSegundoPlano] = useState(false);
  const [pulso, setPulso] = useState(false);
  const [musicaAtual, setMusicaAtual] = useState<string | null>(null);
  const [modalRadialistaId, setModalRadialistaId] = useState<number | null>(null);
  const [modalPrograma, setModalPrograma] = useState<{ radialistaId: number; programaId: number | null } | null>(
    null
  );
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

  function tocarMusica(
    videoId: string,
    titulo: string,
    inicioSegundos = 0,
    fimSegundos: number | null = null
  ): Promise<void> {
    const TIMEOUT_SEGURANCA_MS = 6 * 60 * 1000;
    const POLL_FIM_MS = 500;

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
      // patrocinador com audio pre-gravado: toca o arquivo do anunciante direto, sem TTS
      audioBlob =
        segmento.tipo === "patrocinador" && segmento.patrocinador_audio && segmento.patrocinador_id
          ? await apiFetchBlob(`/patrocinadores/${segmento.patrocinador_id}/audio`)
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
    proximoPreparoRef.current?.then((preparado) => {
      if (preparado.audioUrl) URL.revokeObjectURL(preparado.audioUrl);
      preparado.audiosFalas?.forEach((a) => a.url && URL.revokeObjectURL(a.url));
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

    if (novaFala.video_id) {
      try {
        await reproduzirAudioPreparado(preparado.audioUrl, novaFala.fala);
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
          if (!programaAtivoRef.current) break;
          await tocarMusica(musica.video_id, musica.titulo, musica.inicio_segundos ?? 0, musica.fim_segundos ?? null);
        }
      } catch {
        // segue o programa mesmo se a musica falhar ao tocar
      }
    } else if (preparado.audiosFalas && preparado.audiosFalas.length > 0) {
      // dialogo multi-voz: toca uma linha de cada vez, na voz de quem falou
      for (let i = 0; i < preparado.audiosFalas.length; i++) {
        if (!programaAtivoRef.current) break;
        const textoLinha = novaFala.falas?.[i]?.texto ?? novaFala.fala;
        await reproduzirAudioPreparado(preparado.audiosFalas[i].url, textoLinha);
      }
    } else {
      await reproduzirAudioPreparado(preparado.audioUrl, novaFala.fala);
    }

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
  const nomeLocutor = radialistaSelecionado?.nome_locutor || "Locutor";
  const aoVivoAtivo = radialistaSelecionado?.ativo !== false && Boolean(radioConta?.wuzapi_token);
  const programaSelecionadoNoAr =
    programaSelecionado !== null && radialistaSelecionado !== null && programaNoAr(programaSelecionado, radialistaSelecionado.timezone);

  return (
    <AppShell title="Ao Vivo" maxWidthClassName="max-w-7xl">
      <div id="yt-live-player" className="pointer-events-none fixed left-[-9999px] top-0 h-px w-px overflow-hidden" />
      <div id="yt-bg-player" className="pointer-events-none fixed left-[-9999px] top-0 h-px w-px overflow-hidden" />

      {erro && <p className="text-sm text-rust mb-4">{erro}</p>}
      {abaEmSegundoPlano && (
        <p className="text-sm text-rust mb-4">
          Aba em segundo plano -- o navegador pode pausar o ao vivo. Mantenha esta aba aberta e em foco pra
          transmissao nao parar.
        </p>
      )}
      {avisoGravacao && <p className="text-sm text-teal mb-4">{avisoGravacao}</p>}

      <section className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6 mb-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex-1 min-w-0">
            <h2 className="font-display text-base font-bold text-fg">1. Selecionar programa</h2>
            <p className="text-sm text-fg/55 mt-1">
              Escolha o programa que vai ao ar. Locutor, repertorio, assuntos, voz e horario sao carregados
              automaticamente a partir dele.
            </p>

            <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center">
              <select
                className="w-full sm:max-w-sm rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
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
                  className="rounded-lg bg-rust px-4 py-2.5 text-sm font-medium text-fg hover:bg-rust/90 disabled:opacity-60 disabled:cursor-not-allowed shrink-0"
                >
                  Comecar transmissao
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => pausarPrograma(true)}
                  className="rounded-lg border border-border-strong bg-paper/5 px-4 py-2.5 text-sm font-medium text-fg hover:bg-paper/10 shrink-0"
                >
                  Pausar transmissao
                </button>
              )}
            </div>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            <span
              className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${
                aoVivoAtivo ? "bg-teal/10 text-teal" : "bg-amber/10 text-amber"
              }`}
            >
              {aoVivoAtivo ? "Agente online" : "Aguardando conexao"}
            </span>
            <div className="flex items-center gap-2">
              <OndaLed color="rust" pulse={pulso} />
              <span className="font-mono text-xs font-semibold tracking-wide text-fg/55">AO VIVO</span>
            </div>
          </div>
        </div>

        {programaSelecionado && (
          <div className="mt-5 flex flex-wrap items-center gap-2 border-t border-border pt-4">
            <span className="rounded-full bg-paper/5 px-2.5 py-1 font-mono text-xs font-medium text-fg/70">
              Radialista: {programaSelecionado.radialistaNome}
            </span>
            <span className="rounded-full bg-paper/5 px-2.5 py-1 font-mono text-xs font-medium text-fg/70">
              Voz: {radialistaSelecionado?.voz_id ?? "padrao"}
            </span>
            <span className="rounded-full bg-paper/5 px-2.5 py-1 font-mono text-xs font-medium text-fg/70">
              Generos:{" "}
              {programaSelecionado.generos_musicais.length > 0
                ? programaSelecionado.generos_musicais.slice(0, 3).join(", ")
                : "livre"}
              {programaSelecionado.generos_musicais.length > 3
                ? ` +${programaSelecionado.generos_musicais.length - 3}`
                : ""}
            </span>
            <span className="rounded-full bg-paper/5 px-2.5 py-1 font-mono text-xs font-medium text-fg/70">
              Dias: {formatarDiasSemana(programaSelecionado.dias_semana, programaSelecionado.data_especifica)}
            </span>
            <span className="rounded-full bg-paper/5 px-2.5 py-1 font-mono text-xs font-medium text-fg/70">
              Horario: {formatarFaixaHorario(programaSelecionado)}
            </span>
            <span
              className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                programaSelecionadoNoAr ? "bg-teal/10 text-teal" : "bg-amber/10 text-amber"
              }`}
            >
              {programaSelecionadoNoAr ? "No ar agora" : "Fora do horario agendado"}
            </span>
            <button
              type="button"
              onClick={() => setModalRadialistaId(programaSelecionado.radialistaId)}
              className="text-xs font-medium text-amber hover:text-amber-dim ml-auto"
            >
              Editar radialista
            </button>
            <button
              type="button"
              onClick={() =>
                setModalPrograma({ radialistaId: programaSelecionado.radialistaId, programaId: programaSelecionado.id })
              }
              className="text-xs font-medium text-amber hover:text-amber-dim"
            >
              Editar programa
            </button>
          </div>
        )}
      </section>

      {!programaId ? (
        <section className="bg-surface rounded-2xl border border-dashed border-border-strong p-10 text-center">
          <p className="text-sm text-fg/55">
            Selecione um programa acima para carregar os dados do locutor e liberar a transmissao.
          </p>
        </section>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_380px] gap-5 items-start">
          <section
            className={`rounded-2xl border shadow-theme-xs p-6 transition-colors ${
              programaAtivo ? "bg-surface border-rust/40 ring-1 ring-rust/15" : "bg-surface border-border-strong"
            }`}
          >
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div className="flex items-start gap-3">
                {programaAtivo && <OndaLed color="rust" />}
                <div>
                  <h2 className="font-display text-base font-bold text-fg">
                    2. Programa no ar{" "}
                    <span className={`font-mono text-xs font-medium ${programaAtivo ? "text-rust" : "text-fg/35"}`}>
                      {programaAtivo ? "· transmitindo" : "· pausado"}
                    </span>
                  </h2>
                  <p className="text-sm text-fg/55 mt-1">
                    O agente gera chamadas, comentarios, noticias e blocos musicais conforme a configuracao do
                    programa.
                  </p>
                  {musicaAtual && (
                    <p className="mt-2 inline-flex items-center gap-2 rounded-full bg-teal/10 px-2.5 py-1 text-xs font-medium text-teal">
                      <OndaWaveform bars={8} /> Tocando agora: {musicaAtual}
                    </p>
                  )}
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => gerarProximaFala(true)}
                  disabled={gerandoFala}
                  className="rounded-lg border border-border-strong px-4 py-2.5 text-sm font-medium text-fg hover:bg-paper/5 disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {gerandoFala ? "Gerando..." : "Proxima fala"}
                </button>
              </div>
            </div>

            <div className="mt-5 rounded-xl border border-border bg-bg p-4 min-h-32 max-h-96 overflow-y-auto">
              {falasPrograma.length === 0 ? (
                <p className="text-sm text-fg/55">
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
                          ? "rounded-lg bg-surface border border-rust/30 p-3 text-fg shadow-theme-xs"
                          : "text-fg/55"
                      }
                    >
                      <div className="flex flex-wrap items-center gap-2 mb-1">
                        <span className="rounded-full bg-teal/10 px-2 py-0.5 text-xs font-medium text-teal">
                          {fala.tipo.replace("_", " ")}
                        </span>
                        <span className="font-mono text-xs text-fg/35">{formatarHora(fala.criado_em)}</span>
                        {fala.origem === "local" && (
                          <span className="rounded-full bg-amber/10 px-2 py-0.5 text-xs font-medium text-amber">
                            fallback local
                          </span>
                        )}
                        {index === 0 && gerandoFala && (
                          <span className="flex items-center gap-1.5 text-xs text-fg/35 italic">
                            <OndaSpin size={12} /> gerando proxima...
                          </span>
                        )}
                      </div>
                      <p className={`text-sm leading-6 ${index === 0 ? "font-medium" : ""}`}>{fala.fala}</p>
                    </article>
                  ))}
                </div>
              )}
            </div>
          </section>

          <section className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6 lg:sticky lg:top-22 lg:max-h-[calc(100vh-6.5rem)] flex flex-col">
            <div className="flex items-center justify-between mb-4 shrink-0">
              <h2 className="font-display text-base font-bold text-fg">Conversas</h2>
              <span className="font-mono text-xs font-medium text-fg/35">Atualiza a cada 4s</span>
            </div>

            {carregandoInteracoes ? (
              <p className="flex items-center gap-2 text-sm text-fg/55">
                <OndaSpin size={16} /> Carregando conversas...
              </p>
            ) : interacoes.length === 0 ? (
              <p className="text-sm text-fg/55">
                Nenhuma interacao ainda. Assim que um ouvinte mandar mensagem no WhatsApp, ela aparece aqui.
              </p>
            ) : (
              <div className="space-y-3 overflow-y-auto pr-1 -mr-1">
                {interacoes.map((it) => (
                  <article key={it.id} className="rounded-xl border border-border-strong p-4">
                    <div className="flex items-center justify-between font-mono text-xs text-fg/35 mb-2">
                      <span>{it.nome ? `${it.nome} · ${it.telefone}` : `Ouvinte ${it.telefone}`}</span>
                      <span>{formatarHora(it.criado_em)}</span>
                    </div>

                    <div className="text-sm text-fg/85 mb-2">
                      <span className="font-medium text-fg/55">Ouvinte: </span>
                      {it.mensagem_usuario}
                    </div>

                    {it.resposta && (
                      <div className="text-sm text-fg/85">
                        <span className="font-medium text-amber">{nomeLocutor}: </span>
                        {it.resposta}
                      </div>
                    )}

                    <div className="mt-3">
                      <span
                        className={`inline-block text-xs font-medium px-2 py-0.5 rounded-full ${
                          STATUS_STYLE[it.status] ?? "bg-paper/10 text-fg/60"
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

      <Modal open={modalRadialistaId !== null} onClose={() => setModalRadialistaId(null)} title="Editar radialista" maxWidthClassName="max-w-4xl">
        {modalRadialistaId !== null && (
          <EditarRadialistaForm
            radialistaId={modalRadialistaId}
            onSalvo={() => carregarRadialistasEProgramas()}
            onAbrirPrograma={(progId) => {
              setModalPrograma({ radialistaId: modalRadialistaId, programaId: progId });
              setModalRadialistaId(null);
            }}
            onExcluido={() => {
              const excluidoId = modalRadialistaId;
              setModalRadialistaId(null);
              carregarRadialistasEProgramas();
              if (radialistaIdRef.current === excluidoId) {
                pausarPrograma();
                radialistaIdRef.current = null;
                programaIdRef.current = null;
                setRadialistaId(null);
                setProgramaId(null);
              }
            }}
          />
        )}
      </Modal>

      <Modal open={modalPrograma !== null} onClose={() => setModalPrograma(null)} title="Editar programa" maxWidthClassName="max-w-4xl">
        {modalPrograma !== null && (
          <EditarProgramaForm
            programaId={modalPrograma.programaId}
            radioConfigId={modalPrograma.radialistaId}
            onSalvo={() => carregarRadialistasEProgramas()}
            onExcluido={() => {
              const excluidoId = modalPrograma.programaId;
              setModalPrograma(null);
              carregarRadialistasEProgramas();
              if (excluidoId !== null && programaIdRef.current === excluidoId) {
                pausarPrograma();
                programaIdRef.current = null;
                setProgramaId(null);
              }
            }}
          />
        )}
      </Modal>
    </AppShell>
  );
}
