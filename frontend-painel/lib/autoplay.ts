"use client";

// Autoplay com som sem clique: bloqueado por padrao no Chrome/Edge/Firefox; liberado em PWA
// instalada, com a flag --autoplay-policy=no-user-gesture-required (scripts/abrir-ao-vivo-*),
// politica AutoplayAllowlist ou permissao do site. Usado pelo ao vivo (hooks/useLiveEngine.ts)
// pra decidir se desmuta sozinho, e pelo onboarding (app/onboarding/app) pra mostrar se o
// navegador ja esta pronto pra rodar a radio sem ninguem por perto.

// 50 ms de silencio (WAV PCM 8 kHz mono) pra sondar se o navegador deixa tocar som sem clique.
export const AUDIO_SILENCIO_WAV = (() => {
  const amostras = 400;
  const bytes = new Uint8Array(44 + amostras * 2);
  const v = new DataView(bytes.buffer);
  const texto = (o: number, t: string) => { for (let i = 0; i < t.length; i++) v.setUint8(o + i, t.charCodeAt(i)); };
  texto(0, "RIFF"); v.setUint32(4, 36 + amostras * 2, true); texto(8, "WAVEfmt ");
  v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true); v.setUint32(24, 8000, true);
  v.setUint32(28, 16000, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
  texto(36, "data"); v.setUint32(40, amostras * 2, true);
  let binario = "";
  bytes.forEach((b) => { binario += String.fromCharCode(b); });
  return `data:audio/wav;base64,${typeof btoa === "function" ? btoa(binario) : ""}`;
})();

/** Toca 50 ms de silencio COM som (sem muted). Resolve true se o navegador aceitou sem clique.
 * So' e' conclusivo se rodar ANTES de qualquer clique na pagina -- depois do clique qualquer
 * navegador libera, e o resultado deixa de dizer algo sobre a configuracao. */
export async function sondarAutoplayComSom(): Promise<boolean> {
  if (typeof Audio === "undefined") return false;
  try {
    const silencio = new Audio(AUDIO_SILENCIO_WAV);
    silencio.volume = 0.01;
    await silencio.play();
    silencio.pause();
    return true;
  } catch {
    return false;
  }
}
