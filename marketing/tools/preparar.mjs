// Prepara a montagem de um Reel: junta roteiro, gravações, áudios e conversa em
// marketing/reels/<id>/montagem.json (lido pelo Remotion) e gera legendas.srt.
//
// Uso (em marketing/tools): node preparar.mjs V5
//
// Regras de tempo:
// - cada cena começa onde a anterior terminou; dura o tempo do roteiro, ou mais, se a fala
//   gravada (audio_s) for mais longa;
// - cena de tela com ao vivo começa o vídeo 0,8 s antes da fala de número "foco_ao_vivo",
//   e os áudios reais do ao vivo entram no mesmo instante em que chegaram na gravação;
// - "fala" vira legenda embaixo; "legenda" sem fala vira chamada no alto da tela.

import { copyFileSync, existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const AQUI = dirname(fileURLToPath(import.meta.url));
const MARKETING = resolve(AQUI, "..");
const REELS = join(MARKETING, "reels");
const FPS = 30;
const MAX_CARACTERES = 64; // 2 linhas de 32

const video = process.argv[2];
if (!video) {
  console.error("Uso: node preparar.mjs <id-do-video>");
  process.exit(2);
}
const pasta = join(REELS, video);
const roteiro = JSON.parse(readFileSync(join(pasta, "roteiro.json"), "utf8"));
const lerJson = (arq, padrao) => (existsSync(arq) ? JSON.parse(readFileSync(arq, "utf8")) : padrao);

let temFfprobe = true;
function duracao(arq) {
  if (temFfprobe) {
    try {
      const saida = execFileSync(
        "ffprobe",
        ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", arq],
        { stdio: ["ignore", "pipe", "ignore"] },
      );
      const d = Number.parseFloat(saida.toString().trim());
      if (Number.isFinite(d)) return d;
    } catch (erro) {
      if (erro.code === "ENOENT") temFfprobe = false; // ffprobe não instalado
    }
  }
  return (statSync(arq).size * 8) / 128000; // mp3 de 128 kbps
}

function blocos(texto) {
  const palavras = texto.split(/\s+/).filter(Boolean);
  const saida = [];
  let atual = "";
  for (const p of palavras) {
    if ((atual + " " + p).trim().length > MAX_CARACTERES) {
      saida.push(atual.trim());
      atual = p;
    } else {
      atual = `${atual} ${p}`;
    }
  }
  if (atual.trim()) saida.push(atual.trim());
  return saida;
}

const legendas = [];
function legendar(texto, inicio_s, dur_s, quem = null) {
  const partes = blocos(texto);
  const total = partes.reduce((s, p) => s + p.length, 0) || 1;
  let t = inicio_s;
  for (const p of partes) {
    const d = (dur_s * p.length) / total;
    legendas.push({ inicio_s: t, fim_s: t + d, texto: p, quem });
    t += d;
  }
}

// Logo da marca dentro da pasta servida pelo Remotion.
mkdirSync(join(REELS, "_marca"), { recursive: true });
for (const arq of ["locufy-logo-white.png", "locufy-icon-white.png", "trilha.mp3"]) {
  const origem = join(MARKETING, "brand", arq);
  if (existsSync(origem)) copyFileSync(origem, join(REELS, "_marca", arq));
}

const conversa = lerJson(join(pasta, "conversa.json"), []);
const cenas = [];
const avisos = [];
let cursor = 0;

for (const cena of roteiro.cenas) {
  const nn = String(cena.n).padStart(2, "0");
  let dur = cena.fim_s - cena.inicio_s;
  const item = { n: cena.n, tipo: cena.tipo, titulo: cena.titulo || null, chamada: null, audios: [] };

  const falaArq = join(pasta, "audio", `cena-${nn}.mp3`);
  if (cena.fala) {
    if (existsSync(falaArq)) {
      const d = cena.audio_s ?? duracao(falaArq);
      dur = Math.max(dur, d + 0.4);
      item.audios.push({ arquivo: `${video}/audio/cena-${nn}.mp3`, inicio_s: 0.2, volume: 1 });
      legendar(cena.fala, cursor + 0.2, d);
    } else {
      avisos.push(`cena ${cena.n}: sem áudio de fala (rode a locução); legenda pelo tempo da cena`);
      legendar(cena.fala, cursor + 0.2, dur - 0.4);
    }
  } else if (cena.legenda) {
    item.chamada = cena.legenda;
  }

  if (cena.tipo === "tela") {
    const marcas = lerJson(join(pasta, "tela", `cena-${nn}.json`), null);
    if (!marcas || !existsSync(join(pasta, "tela", `cena-${nn}.webm`))) {
      avisos.push(`cena ${cena.n}: gravação de tela não encontrada (rode a gravação)`);
    } else {
      let inicioVideo = marcas.inicio_ms / 1000;
      const capturas = marcas.ao_vivo || [];
      const foco = cena.foco_ao_vivo ? capturas[cena.foco_ao_vivo - 1] : null;
      if (cena.foco_ao_vivo && !foco) avisos.push(`cena ${cena.n}: fala ${cena.foco_ao_vivo} do ao vivo não foi capturada`);
      if (foco) inicioVideo = Math.max(inicioVideo, foco.ms / 1000 - 0.8);
      item.video = { arquivo: `${video}/tela/cena-${nn}.webm`, inicio_s: inicioVideo };
      if (foco) {
        for (const cap of capturas.slice(cena.foco_ao_vivo - 1)) {
          let t = cap.ms / 1000 - inicioVideo;
          const linhas = cap.falas && cap.falas.length ? cap.falas : [{ nome_locutor: null, texto: cap.fala }];
          cap.audios.forEach((arq, i) => {
            if (t >= dur) return;
            const d = duracao(join(pasta, "tela", arq));
            item.audios.push({ arquivo: `${video}/tela/${arq}`, inicio_s: t, volume: 1 });
            const linha = linhas[Math.min(i, linhas.length - 1)];
            if (linha?.texto) legendar(linha.texto, cursor + t, Math.min(d, dur - t), linha.nome_locutor);
            t += d;
          });
        }
      }
    }
  }

  if (cena.tipo === "celular") {
    if (!conversa.length) avisos.push(`cena ${cena.n}: conversa.json não existe (rode a conversa de teste)`);
    item.conversa = conversa;
  }

  item.inicio_f = Math.round(cursor * FPS);
  item.dur_f = Math.round(dur * FPS);
  cenas.push(item);
  cursor += dur;
}

const trilha = existsSync(join(REELS, "_marca", "trilha.mp3")) ? "_marca/trilha.mp3" : null;
const montagem = {
  id: video,
  titulo: roteiro.titulo,
  fps: FPS,
  largura: 1080,
  altura: 1920,
  total_frames: Math.round(cursor * FPS),
  trilha,
  logo: "_marca/locufy-logo-white.png",
  icone: "_marca/locufy-icon-white.png",
  cenas,
  legendas: legendas.map((l) => ({
    inicio_f: Math.round(l.inicio_s * FPS),
    fim_f: Math.round(l.fim_s * FPS),
    texto: l.texto,
    quem: l.quem,
  })),
};
writeFileSync(join(pasta, "montagem.json"), JSON.stringify(montagem, null, 2));

const tempo = (s) => {
  const ms = Math.round(s * 1000);
  const h = String(Math.floor(ms / 3600000)).padStart(2, "0");
  const m = String(Math.floor((ms % 3600000) / 60000)).padStart(2, "0");
  const seg = String(Math.floor((ms % 60000) / 1000)).padStart(2, "0");
  return `${h}:${m}:${seg},${String(ms % 1000).padStart(3, "0")}`;
};
const srt = legendas
  .map((l, i) => `${i + 1}\n${tempo(l.inicio_s)} --> ${tempo(l.fim_s)}\n${l.quem ? `${l.quem}: ` : ""}${l.texto}\n`)
  .join("\n");
writeFileSync(join(pasta, "legendas.srt"), srt);

console.log(`${video}: montagem.json e legendas.srt prontos (${cursor.toFixed(1)} s, ${cenas.length} cenas, ${legendas.length} legendas)`);
avisos.forEach((a) => console.warn(`AVISO ${a}`));
