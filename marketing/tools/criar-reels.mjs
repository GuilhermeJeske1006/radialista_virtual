// Produz os Reels da Locufy de ponta a ponta, sem intervenção:
// seed da rádio de demonstração -> conversa de teste -> gravação de tela -> locução ->
// legendas/montagem -> render. A revisão de marca é feita depois pelo /criar-reels no Claude Code.
//
// Uso (em marketing/tools, com ./start-dev.sh rodando):
//   node criar-reels.mjs              -> todos os vídeos de ../reels/pipeline.json
//   node criar-reels.mjs V5 V8        -> só esses
//   node criar-reels.mjs V5 --refazer -> ignora resultados anteriores e refaz tudo
//
// Retoma de onde parou: etapa com resultado já gerado é pulada (exceto com --refazer).

import { execFileSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const AQUI = dirname(fileURLToPath(import.meta.url));
const MARKETING = resolve(AQUI, "..");
const RAIZ = resolve(MARKETING, "..");
const BACKEND = join(RAIZ, "backend");
const REELS = join(MARKETING, "reels");
const REMOTION = join(MARKETING, "reels-remotion");
const win = process.platform === "win32";

const args = process.argv.slice(2);
const refazer = args.includes("--refazer");
const pipeline = JSON.parse(readFileSync(join(REELS, "pipeline.json"), "utf8"));
const ids = args.filter((a) => !a.startsWith("--"));
const videos = ids.length ? ids : Object.keys(pipeline.videos);

const python = [join(BACKEND, ".venv", "bin", "python"), join(BACKEND, ".venv", "Scripts", "python.exe")].find(existsSync)
  ?? (win ? "python" : "python3");

function rodar(cmd, argumentos, cwd, env = {}) {
  execFileSync(cmd, argumentos, { cwd, stdio: "inherit", env: { ...process.env, ...env } });
}
const py = (script, ...a) => rodar(python, [`scripts/${script}`, ...a], BACKEND, { PYTHONPATH: "." });
const node = (script, cwd, ...a) => rodar(process.execPath, [script, ...a], cwd);

async function noAr(url) {
  try {
    await fetch(url, { signal: AbortSignal.timeout(4000) });
    return true;
  } catch {
    return false;
  }
}

function feito(id, etapa) {
  const pasta = join(REELS, id);
  const roteiro = JSON.parse(readFileSync(join(pasta, "roteiro.json"), "utf8"));
  const ls = (sub) => (existsSync(join(pasta, sub)) ? readdirSync(join(pasta, sub)) : []);
  if (etapa === "conversa-teste") return existsSync(join(pasta, "conversa.json"));
  if (etapa === "gravar-tela") {
    const telas = roteiro.cenas.filter((c) => c.tipo === "tela");
    return telas.every((c) => {
      const nn = String(c.n).padStart(2, "0");
      if (!ls("tela").includes(`cena-${nn}.webm`) || !ls("tela").includes(`cena-${nn}.json`)) return false;
      const marcas = JSON.parse(readFileSync(join(pasta, "tela", `cena-${nn}.json`), "utf8"));
      return (marcas.erros || []).length === 0; // cena com ação que falhou é regravada
    });
  }
  if (etapa === "locucao") return roteiro.cenas.filter((c) => c.fala).every((c) => c.audio_s != null);
  if (etapa === "legendas") return false; // rápido e depende das outras: sempre refaz
  if (etapa === "montar-reel") return existsSync(join(pasta, "out", `${id}.mp4`));
  return false;
}

const ETAPAS = {
  "conversa-teste": (id) => py("conversa_teste.py", id),
  "gravar-tela": (id) => node("gravar.mjs", AQUI, id),
  locucao: (id) => py("locucao_reel.py", id),
  legendas: (id) => node("preparar.mjs", AQUI, id),
  "montar-reel": (id) => node("render.mjs", REMOTION, id),
};

// 1. Preparação
if (!(await noAr("http://localhost:8000/docs")) || !(await noAr("http://localhost:3000/login"))) {
  console.error("Backend (8000) ou painel (3000) fora do ar. Rode ./start-dev.sh na raiz do repositório e tente de novo.");
  process.exit(2);
}
for (const [pasta, nome] of [[AQUI, "marketing/tools"], [REMOTION, "marketing/reels-remotion"]]) {
  if (!existsSync(join(pasta, "node_modules"))) {
    console.log(`Instalando dependências de ${nome}...`);
    rodar(win ? "npm.cmd" : "npm", ["install"], pasta);
  }
}
console.log("Preparando a rádio de demonstração...");
py("seed_demo.py");

// 2. Produção, um vídeo por vez
const resumo = [];
for (const id of videos) {
  const config = pipeline.videos[id];
  if (!config) {
    resumo.push({ id, status: "erro", detalhe: "não existe em pipeline.json" });
    continue;
  }
  console.log(`\n=== ${id} · ${config.titulo} ===`);
  let etapaAtual = null;
  try {
    for (const etapa of config.etapas) {
      etapaAtual = etapa;
      if (!refazer && feito(id, etapa)) {
        console.log(`- ${etapa}: já feito, pulando`);
        continue;
      }
      console.log(`- ${etapa}`);
      ETAPAS[etapa](id);
    }
    resumo.push({ id, status: "ok", detalhe: `marketing/reels/${id}/out/${id}.mp4` });
  } catch (erro) {
    resumo.push({ id, status: "erro", detalhe: `parou em ${etapaAtual}: ${erro.message.split("\n")[0]}` });
  }
}

writeFileSync(join(REELS, "resumo.json"), JSON.stringify(resumo, null, 2));
console.log("\nResumo:");
for (const r of resumo) console.log(`  ${r.id}  ${r.status.padEnd(4)}  ${r.detalhe}`);
process.exit(resumo.some((r) => r.status !== "ok") ? 1 : 0);
