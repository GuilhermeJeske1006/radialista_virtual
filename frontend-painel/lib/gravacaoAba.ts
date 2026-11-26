// Grava o áudio que sai na aba do /live (fala, vinheta, música do YouTube e fundo, exatamente como
// foi ao ar) e, no fim do programa, converte no backend em MP3 do programa completo.
// A música toca num iframe do YouTube: os bytes nunca passam pelo app, só a captura da aba alcança.
import { apiFetchBlob } from "./api";

export interface GravacaoAba {
  /** Para a captura e devolve o MP3 do programa completo. */
  finalizar(programaId?: number): Promise<Blob>;
  /** Descarta a captura sem converter. */
  cancelar(): void;
}

const MIMES = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus"];

export function capturaDeAbaSuportada(): boolean {
  return (
    typeof navigator !== "undefined" &&
    !!navigator.mediaDevices?.getDisplayMedia &&
    typeof MediaRecorder !== "undefined"
  );
}

function escolherMime(): string | undefined {
  return MIMES.find((m) => MediaRecorder.isTypeSupported(m));
}

// Precisa rodar dentro de um gesto do usuário (clique em Iniciar). Rejeita se o operador recusar
// ou se a aba compartilhada vier sem áudio.
export async function iniciarGravacaoAba(aoPerder?: () => void): Promise<GravacaoAba> {
  const fluxo = await navigator.mediaDevices.getDisplayMedia({
    video: true,
    audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
    preferCurrentTab: true,
    selfBrowserSurface: "include",
    systemAudio: "include",
  } as DisplayMediaStreamOptions);

  const trilhas = fluxo.getAudioTracks();
  const parar = () => fluxo.getTracks().forEach((t) => t.stop());
  if (trilhas.length === 0) {
    parar();
    throw new Error("A aba foi compartilhada sem áudio. Marque 'Compartilhar áudio da aba'.");
  }

  const mime = escolherMime();
  const gravador = new MediaRecorder(new MediaStream(trilhas), mime ? { mimeType: mime } : undefined);
  const pedacos: Blob[] = [];
  gravador.ondataavailable = (e) => {
    if (e.data.size > 0) pedacos.push(e.data);
  };
  // operador clicou em "Parar compartilhamento" na barra do navegador
  trilhas[0].addEventListener("ended", () => aoPerder?.());
  gravador.start(5000);

  const encerrar = () =>
    new Promise<Blob>((resolve) => {
      const montar = () => {
        parar();
        resolve(new Blob(pedacos, { type: gravador.mimeType || "audio/webm" }));
      };
      if (gravador.state === "inactive") return montar();
      gravador.onstop = montar;
      gravador.stop();
    });

  return {
    async finalizar(programaId?: number) {
      const webm = await encerrar();
      if (webm.size === 0) throw new Error("Gravação vazia.");
      let arquivada = true;
      const mp3 = await apiFetchBlob(`/live/gravacao/mp3${programaId ? `?programa_id=${programaId}` : ""}`, {
        method: "POST",
        headers: { "content-type": webm.type || "audio/webm" },
        body: webm,
      }, resposta => { arquivada = resposta.headers.get("X-Gravacao-Arquivada") !== "false"; });
      window.dispatchEvent(new CustomEvent("gravacao-exportada", { detail: { arquivada } }));
      return mp3;
    },
    cancelar() {
      gravador.ondataavailable = null;
      if (gravador.state !== "inactive") gravador.stop();
      parar();
    },
  };
}
