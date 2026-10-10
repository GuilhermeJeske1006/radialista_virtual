// Grava as cenas de tela de um Reel da Locufy, seguindo marketing/reels/<id>/roteiro.json.
//
// Uso (em marketing/tools, depois de `npm install`):
//   node gravar.mjs V5            -> grava todas as cenas do tipo "tela" do V5
//   node gravar.mjs V5 /live      -> só as cenas com essa rota
//
// Saída em marketing/reels/<id>/tela/:
//   cena-NN.webm   vídeo 1080x1920 da cena (NN = campo "n" da cena)
//   cena-NN.json   marcações: início útil do vídeo e falas do ao vivo capturadas
//   cena-NN-aovivo-KK.mp3  áudio real de cada fala do ao vivo (resposta de /proxima ou /tts)
//
// Login: lê marketing/reels/.demo.json (gerado por backend/scripts/seed_demo.py).
// Ações aceitas em "acoes": {ir}, {clicar}, {digitar:{campo,texto}}, {selecionar:{campo,opcao}},
// {rolar}, {destacar}, {esperar}, {esperar_ao_vivo}.

import { chromium } from "playwright";
import { existsSync, mkdirSync, readFileSync, renameSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const AQUI = dirname(fileURLToPath(import.meta.url));
const REELS = resolve(AQUI, "..", "reels");
const AUTH = join(AQUI, ".auth.json");
const VIEWPORT = { width: 540, height: 960 };
const VIDEO = { width: 1080, height: 1920 };
const TIMEOUT_AO_VIVO_MS = 10 * 60 * 1000;

const [video, filtroRota] = process.argv.slice(2);
if (!video) {
  console.error("Uso: node gravar.mjs <id-do-video> [rota]");
  process.exit(2);
}

const roteiro = JSON.parse(readFileSync(join(REELS, video, "roteiro.json"), "utf8"));
const demoPath = join(REELS, ".demo.json");
if (!existsSync(demoPath)) {
  console.error("Rode backend/scripts/seed_demo.py antes (marketing/reels/.demo.json não existe).");
  process.exit(2);
}
const demo = JSON.parse(readFileSync(demoPath, "utf8"));
const PAINEL = (demo.painel_url || "http://localhost:3000").replace(/\/$/, "");

const cenas = roteiro.cenas.filter(
  (c) => c.tipo === "tela" && (!filtroRota || c.rota === filtroRota),
);
if (cenas.length === 0) {
  console.log(`${video}: nenhuma cena de tela${filtroRota ? ` com a rota ${filtroRota}` : ""}.`);
  process.exit(0);
}

const pasta = join(REELS, video, "tela");
mkdirSync(pasta, { recursive: true });
const pausa = (ms) => new Promise((r) => setTimeout(r, ms));
const humano = () => 300 + Math.random() * 500;
const nn = (n) => String(n).padStart(2, "0");

// Cursor visível no vídeo: o Chromium headless não desenha o ponteiro do mouse.
const CURSOR = `
  window.addEventListener('DOMContentLoaded', () => {
    const c = document.createElement('div');
    c.id = '__cursor_reels';
    Object.assign(c.style, {position:'fixed', zIndex: 2147483647, width:'22px', height:'22px',
      margin:'-11px 0 0 -11px', borderRadius:'50%', background:'rgba(255,140,0,.85)',
      boxShadow:'0 0 0 6px rgba(255,140,0,.25)', pointerEvents:'none', left:'-50px', top:'-50px',
      transition:'transform .12s'});
    document.body.appendChild(c);
    window.addEventListener('mousemove', e => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; });
    window.addEventListener('mousedown', () => { c.style.transform = 'scale(.7)'; });
    window.addEventListener('mouseup', () => { c.style.transform = 'scale(1)'; });
  });`;

async function fazerLogin(browser) {
  const ctx = await browser.newContext({ viewport: VIEWPORT, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  await page.goto(`${PAINEL}/login`);
  await page.locator('input[type="email"]').fill(demo.email);
  await page.locator('input[type="password"]').fill(demo.senha);
  await page.locator('button[type="submit"]').click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"), { timeout: 30000 });
  await ctx.storageState({ path: AUTH });
  await ctx.close();
}

// Acha o elemento pelo nome visível, tentando os jeitos mais comuns em ordem.
async function alvo(page, nome) {
  const tentativas = [
    page.getByRole("button", { name: nome }),
    page.getByRole("link", { name: nome }),
    page.getByRole("radio", { name: nome }),
    page.getByLabel(nome, { exact: false }),
    page.getByPlaceholder(nome),
    page.getByText(nome, { exact: false }),
  ];
  for (const loc of tentativas) {
    const primeiro = loc.first();
    if ((await loc.count()) > 0 && (await primeiro.isVisible().catch(() => false))) return primeiro;
  }
  throw new Error(`Elemento "${nome}" não encontrado na tela ${page.url()}`);
}

async function moverAte(page, loc) {
  await loc.scrollIntoViewIfNeeded();
  const caixa = await loc.boundingBox();
  if (caixa) await page.mouse.move(caixa.x + caixa.width / 2, caixa.y + caixa.height / 2, { steps: 20 });
  await pausa(humano());
}

async function executar(page, acao, capturas) {
  const [tipo, valor] = Object.entries(acao)[0];
  if (tipo === "ir") {
    await page.goto(valor.startsWith("http") ? valor : `${PAINEL}${valor}`);
  } else if (tipo === "clicar") {
    const loc = await alvo(page, valor);
    await moverAte(page, loc);
    await loc.click();
  } else if (tipo === "digitar") {
    const loc = await alvo(page, valor.campo);
    await moverAte(page, loc);
    await loc.click();
    await loc.fill("");
    await loc.pressSequentially(valor.texto, { delay: 40 });
  } else if (tipo === "selecionar") {
    const loc = await alvo(page, valor.campo);
    await moverAte(page, loc);
    await loc.selectOption({ label: valor.opcao });
  } else if (tipo === "rolar") {
    await page.mouse.wheel(0, valor);
  } else if (tipo === "destacar") {
    const loc = await alvo(page, valor);
    await moverAte(page, loc);
    await loc.evaluate((el) => {
      el.style.outline = "4px solid #FF8C00";
      el.style.outlineOffset = "4px";
      el.style.borderRadius = "8px";
    });
  } else if (tipo === "esperar") {
    await pausa(valor);
  } else if (tipo === "esperar_ao_vivo") {
    const limite = Date.now() + TIMEOUT_AO_VIVO_MS;
    while (capturas.length < valor && Date.now() < limite) await pausa(500);
    if (capturas.length < valor) throw new Error(`Só ${capturas.length} de ${valor} falas do ao vivo chegaram.`);
    await pausa(8000); // deixa a última fala tocar na tela
  } else {
    throw new Error(`Ação desconhecida: ${tipo}`);
  }
  await pausa(humano());
}

async function gravarCena(browser, cena) {
  const tmp = join(pasta, `.tmp-${nn(cena.n)}`);
  rmSync(tmp, { recursive: true, force: true });
  const externo = cena.rota.startsWith("http");
  const ctx = await browser.newContext({
    viewport: VIEWPORT,
    deviceScaleFactor: 2,
    storageState: externo ? undefined : AUTH,
    recordVideo: { dir: tmp, size: VIDEO },
  });
  await ctx.addInitScript(CURSOR);
  const page = await ctx.newPage();
  // O vídeo começa quando a página é criada: os tempos (ms) são contados a partir daqui.
  const t0 = Date.now();

  const capturas = [];
  const salvarAudio = (b64, arquivo) => writeFileSync(join(pasta, arquivo), Buffer.from(b64, "base64"));
  page.on("response", async (resp) => {
    try {
      const url = resp.url();
      if (/\/live\/\d+\/programas\/\d+\/proxima/.test(url) && resp.ok()) {
        const ms = Date.now() - t0;
        const dados = await resp.json();
        const k = capturas.length + 1;
        const item = { ms, tipo: dados.tipo, fala: dados.fala, falas: dados.falas || null, audios: [] };
        if (dados.audio_base64) {
          const arq = `cena-${nn(cena.n)}-aovivo-${nn(k)}.mp3`;
          salvarAudio(dados.audio_base64, arq);
          item.audios.push(arq);
        }
        (dados.audios_falas_base64 || []).forEach((b64, i) => {
          if (!b64) return;
          const arq = `cena-${nn(cena.n)}-aovivo-${nn(k)}-${i + 1}.mp3`;
          salvarAudio(b64, arq);
          item.audios.push(arq);
        });
        capturas.push(item);
        console.log(`  ao vivo ${k}: ${dados.tipo} (${item.audios.length} áudio(s))`);
      } else if (/\/live\/\d+\/tts/.test(url) && resp.ok()) {
        // Fala sem áudio embutido: o painel busca em /tts. Guarda junto da última captura.
        const corpo = await resp.body();
        const ultima = capturas.at(-1);
        if (ultima) {
          const arq = `cena-${nn(cena.n)}-aovivo-${nn(capturas.length)}-tts-${ultima.audios.length + 1}.mp3`;
          writeFileSync(join(pasta, arq), corpo);
          ultima.audios.push(arq);
        }
      }
    } catch (erro) {
      console.warn(`  aviso: resposta não capturada (${erro.message})`);
    }
  });

  const erros = [];
  let inicioMs = 0;
  try {
    await page.goto(externo ? cena.rota : `${PAINEL}${cena.rota}`, { waitUntil: "domcontentloaded" });
    await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});
    for (const seletor of cena.desfocar || []) {
      await page.addStyleTag({ content: `${seletor}{filter:blur(14px)!important}` });
    }
    await pausa(800);
    inicioMs = Date.now() - t0;
    for (const acao of cena.acoes || []) {
      try {
        await executar(page, acao, capturas);
      } catch (erro) {
        erros.push(`${JSON.stringify(acao)} -> ${erro.message}`);
        await page.screenshot({ path: join(pasta, `cena-${nn(cena.n)}-erro.png`) });
        if (Object.keys(acao)[0] === "esperar_ao_vivo") break;
      }
    }
    // Garante pelo menos a duração da cena depois do início útil.
    const minimoMs = inicioMs + (cena.fim_s - cena.inicio_s) * 1000 + 500;
    const falta = minimoMs - (Date.now() - t0);
    if (falta > 0) await pausa(falta);
  } finally {
    const gravacao = page.video();
    await ctx.close();
    const caminho = gravacao ? await gravacao.path() : null;
    if (caminho) renameSync(caminho, join(pasta, `cena-${nn(cena.n)}.webm`));
    rmSync(tmp, { recursive: true, force: true });
  }

  writeFileSync(
    join(pasta, `cena-${nn(cena.n)}.json`),
    JSON.stringify({ cena: cena.n, inicio_ms: inicioMs, ao_vivo: capturas, erros }, null, 2),
  );
  return erros;
}

// O ao vivo toca áudio sem clique do usuário; sem essa flag o Chromium bloqueia o autoplay.
const browser = await chromium.launch({ args: ["--autoplay-policy=no-user-gesture-required"] });
const falhas = [];
try {
  if (cenas.some((c) => !c.rota.startsWith("http"))) await fazerLogin(browser);
  for (const cena of cenas) {
    console.log(`${video} · cena ${cena.n} · ${cena.rota}`);
    const erros = await gravarCena(browser, cena);
    erros.forEach((e) => falhas.push(`cena ${cena.n}: ${e}`));
  }
} finally {
  await browser.close();
}

if (falhas.length) {
  console.error(`\n${video}: ${falhas.length} ação(ões) falharam (ver tela/cena-NN-erro.png):`);
  falhas.forEach((f) => console.error(`  - ${f}`));
  process.exit(1);
}
console.log(`\n${video}: gravação concluída em ${pasta}`);
