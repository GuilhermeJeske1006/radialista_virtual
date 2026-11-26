#!/usr/bin/env node
// Renderiza as peças de Instagram (marketing/instagram/src/pecas.mjs) em PNG e confere cada uma.
//
//   node instagram.mjs            # todas
//   node instagram.mjs A B3 S1    # só grupos ou peças
//
// Saída em marketing/instagram/out/: <grupo>/<id>.png, pranchas, grade do perfil e checagem.json.
// Sai com código 1 se alguma checagem bloqueante falhar.
import { chromium } from 'playwright';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(AQUI, '../..');
const DIR = path.join(RAIZ, 'marketing/instagram');
const OUT = path.join(DIR, process.argv.includes('--autoteste') ? 'out/_autoteste' : 'out');
const AUTOTESTE = process.argv.includes('--autoteste');
const filtros = process.argv.slice(2).filter((a) => !a.startsWith('--'));

// --autoteste: peças quebradas de propósito; cada uma precisa ser reprovada pelo motivo esperado.
const FIXTURES = (() => {
  const L = '<img class="logo" src="/marketing/brand/locufy-logo-white.png" alt="Locufy">';
  const moldura = (miolo, base = L) => `<div class="frame"><div class="topo"><div class="lab">Teste</div></div><div class="miolo">${miolo}</div><div class="base">${base}</div></div>`;
  const tela = '<div class="shot" style="width:600px;height:300px"><img src="/landing-page/design/grade-profissional.png" alt="" style="left:0;top:0;width:800px"></div>';
  return [
    { id: 'X1', espera: 'texto sobre o logo', html: moldura('<p class="nota" style="margin-top:auto;margin-bottom:-60px">Estimativa de teste encostando no logo da marca.</p>') },
    { id: 'X2', espera: 'fora da área segura', story: true, html: '<div class="frame"><h1 class="h" style="margin-top:-200px">Título alto demais</h1></div>' },
    { id: 'X3', espera: 'contraste', html: moldura('<p class="lead" style="color:#2a3a5c">Texto quase invisível.</p>') },
    { id: 'X4', espera: 'gratuidade', html: moldura('<p class="lead">Teste grátis por R$ 2,99.</p>') },
    { id: 'X5', espera: 'não está no site', html: moldura('<p class="lead">Só R$ 2,99 por mês.</p>') },
    { id: 'X6', espera: 'sem aviso de dados fictícios', html: moldura(tela) },
    { id: 'X7', espera: 'estoura', html: moldura('<div style="height:1400px;flex:none"></div>') },
    { id: 'X8', espera: 'sobreposto', html: moldura('<p class="lead">Primeiro bloco de texto</p><p class="lead" style="margin-top:-40px">Segundo bloco por cima</p>') },
    { id: 'X9', espera: 'sem acento', html: moldura('<p class="lead">A programacao da radio.</p>') },
    { id: 'X10', espera: 'logo distorcido', html: moldura('<p class="lead">Logo esticado.</p>', '<img class="logo" style="width:400px;height:46px" src="/marketing/brand/locufy-logo-white.png" alt="Locufy">') },
  ];
})();

const { grupos } = AUTOTESTE
  ? { grupos: [
    { id: 'X', nome: 'Autoteste feed', formato: 'feed', pecas: FIXTURES.filter((f) => !f.story).map((f) => ({ ...f, alt: '' })) },
    { id: 'XS', nome: 'Autoteste story', formato: 'story', pecas: FIXTURES.filter((f) => f.story).map((f) => ({ ...f, alt: '' })) },
  ] }
  : { grupos: (await Promise.all(['pecas.mjs', 'tendencias.mjs'].map((f) => import(`${pathToFileURL(path.join(DIR, 'src', f)).href}?t=${Date.now()}`))))
    .flatMap((m) => m.grupos) };
const pasta = (g) => g.pasta || g.id;
const colecao = (g) => g.colecao || g.formato;

const TAM = { feed: [1080, 1350], story: [1080, 1920] };
// Feed: o perfil recorta 4:5 para 3:4 (~34 px de cada lado). Stories: 250 px de cima e de baixo ficam sob a interface.
const SEGURA = { feed: { x0: 60, x1: 1020, y0: 48, y1: 1302 }, story: { x0: 64, x1: 1016, y0: 250, y1: 1670 } };

// ---------- regras de texto ----------
const site = fs.readFileSync(path.join(RAIZ, 'landing-page/index.html'), 'utf8');
const PRECOS_SITE = new Set([...site.matchAll(/(\d+,\d{2})/g)].map((m) => m[1]));
const PRECO_HORA = /\b(3,86|4,16|5,05|7,16|7,46|8,35)\b/;
const BANIDOS = [
  [/gr[aá]tis|gratuit/i, 'promete gratuidade (cadastro exige assinatura)'],
  [/sem cart[aã]o/i, '"sem cartão" (cadastro exige cartão)'],
  [/[—–]/, 'travessão (regra editorial)'],
  [/n[aã]o [ée] s[oó]/i, 'paralelismo "não é só X"'],
  [/revolucion|incr[ií]ve|surpreendente|game.?changer/i, 'importância inflada'],
  [/substitu/i, 'fala em substituir pessoas'],
  [/garant/i, 'promessa de garantia'],
  [/\p{Extended_Pictographic}/u, 'emoji na arte'],
];
const SEM_ACENTO = ['radio', 'voce', 'nao', 'musica', 'audio', 'programacao', 'configuracao', 'comentarios', 'noticias',
  'horario', 'horarios', 'proximo', 'periodo', 'tambem', 'ja', 'mes', 'numero', 'catalogo', 'video', 'historico',
  'inteligencia', 'essencia', 'agil', 'duvida', 'duvidas', 'participacoes', 'transmissao', 'demonstracao', 'ficticios', 'ficticia'];

function lintTexto(texto, { exigeEstimativa = true } = {}) {
  const erros = [];
  for (const [re, motivo] of BANIDOS) if (re.test(texto)) erros.push(`texto: ${motivo}`);
  for (const m of texto.matchAll(/R\$\s?(\d+,\d{2})/g)) if (!PRECOS_SITE.has(m[1])) erros.push(`preço R$ ${m[1]} não está no site`);
  for (const m of texto.matchAll(/(\d+,\d{2})(?![\d%])(?!\s?%)/g)) if (!PRECOS_SITE.has(m[1])) erros.push(`valor ${m[1]} não está no site`);
  if (exigeEstimativa && PRECO_HORA.test(texto) && !/estimativa|≈/i.test(texto)) erros.push('preço por hora sem "estimativa" ou "≈"');
  // Nomes próprios em inglês (estudos, empresas) não passam pela regra de acento.
  const baixo = texto.replace(/Audio Pulse|Inside Audio|Radio World|Radio Today/g, '').toLowerCase();
  for (const p of SEM_ACENTO) if (new RegExp(`(^|[^\\p{L}])${p}($|[^\\p{L}])`, 'u').test(baixo)) erros.push(`palavra sem acento: "${p}"`);
  return [...new Set(erros)];
}

// ---------- servidor local ----------
const MIME = { '.css': 'text/css', '.png': 'image/png', '.webp': 'image/webp', '.jpg': 'image/jpeg', '.woff2': 'font/woff2', '.ttf': 'font/ttf', '.html': 'text/html; charset=utf-8' };
const porId = new Map();
for (const g of grupos) for (const p of g.pecas) porId.set(p.id, { ...p, formato: g.formato, grupo: g.id });

const doc = (corpo, formato) => `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<link rel="stylesheet" href="/marketing/instagram/src/base.css"></head>
<body><div id="c" class="canvas ${formato}">${corpo}</div></body></html>`;

let pranchaHtml = '';
const servidor = http.createServer((req, res) => {
  const url = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  if (url.startsWith('/peca/')) {
    const p = porId.get(url.slice(6));
    if (!p) { res.writeHead(404); return res.end(); }
    res.writeHead(200, { 'content-type': MIME['.html'] });
    return res.end(doc(p.html, p.formato));
  }
  if (url === '/prancha') { res.writeHead(200, { 'content-type': MIME['.html'] }); return res.end(pranchaHtml); }
  if (!/^\/(marketing|landing-page)\//.test(url) || url.includes('..')) { res.writeHead(403); return res.end(); }
  const arq = path.join(RAIZ, url);
  if (!fs.existsSync(arq)) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'content-type': MIME[path.extname(arq)] || 'application/octet-stream' });
  fs.createReadStream(arq).pipe(res);
});
await new Promise((r) => servidor.listen(0, '127.0.0.1', r));
const BASE = `http://127.0.0.1:${servidor.address().port}`;

// ---------- medições no navegador ----------
function coletar({ segura }) {
  const C = document.getElementById('c');
  const cr = C.getBoundingClientRect();
  const problemas = [];
  const avisos = [];
  const textos = [];

  const opacidade = (el) => { let o = 1; for (let e = el; e && e !== C.parentElement; e = e.parentElement) o *= parseFloat(getComputedStyle(e).opacity); return o; };
  const bloco = (el) => { let e = el; while (e && e !== C && getComputedStyle(e).display === 'inline') e = e.parentElement; return e; };

  const tw = document.createTreeWalker(C, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = tw.nextNode())) {
    if (!n.textContent.trim()) continue;
    const el = n.parentElement;
    const cs = getComputedStyle(el);
    const r = document.createRange();
    r.selectNodeContents(n);
    const fs = parseFloat(cs.fontSize);
    const rects = [...r.getClientRects()].filter((q) => q.width > 0.5 && q.height > 0.5)
      .map((q) => ({ x: q.left - cr.left, y: q.top - cr.top, w: q.width, h: q.height }));
    const t = { texto: n.textContent.trim().replace(/\s+/g, ' ').slice(0, 50), cor: cs.color, op: opacidade(el), fs, peso: +cs.fontWeight, familia: cs.fontFamily, rects };
    t._bloco = bloco(el);
    t._el = el;
    textos.push(t);
    if (fs < 20) problemas.push(`fonte de ${fs}px em "${t.texto}"`);
    else if (fs < 24) avisos.push(`fonte de ${fs}px em "${t.texto}" (pequena no celular)`);
    for (const q of rects) {
      if (q.x < segura.x0 - 0.5 || q.x + q.w > segura.x1 + 0.5 || q.y < segura.y0 - 0.5 || q.y + q.h > segura.y1 + 0.5) {
        problemas.push(`fora da área segura: "${t.texto}" (x ${Math.round(q.x)}–${Math.round(q.x + q.w)}, y ${Math.round(q.y)}–${Math.round(q.y + q.h)})`);
        break;
      }
    }
  }

  // Sobreposição entre textos de blocos diferentes (caixa encolhida para ignorar a sobra da fonte).
  const enc = (t, q) => ({ x0: q.x + 1, x1: q.x + q.w - 1, y0: q.y + t.fs * 0.2, y1: q.y + q.h - t.fs * 0.2 });
  for (let i = 0; i < textos.length; i++) for (let j = i + 1; j < textos.length; j++) {
    const a = textos[i]; const b = textos[j];
    if (a._bloco === b._bloco || a._bloco.contains(b._bloco) || b._bloco.contains(a._bloco)) continue;
    for (const qa of a.rects) for (const qb of b.rects) {
      const A = enc(a, qa); const B = enc(b, qb);
      if (A.x0 < B.x1 && B.x0 < A.x1 && A.y0 < B.y1 && B.y0 < A.y1) problemas.push(`texto sobreposto: "${a.texto}" × "${b.texto}"`);
    }
  }

  // Estouro: filhos fora do contêiner (geometria, não scrollHeight: título com entrelinha curta "vaza" por natureza).
  const caixa = (el) => { const q = el.getBoundingClientRect(); return { x0: q.left, x1: q.right, y0: q.top, y1: q.bottom }; };
  for (const pai of C.querySelectorAll('.frame, .miolo')) {
    const P = caixa(pai);
    for (const f of pai.children) {
      const F = caixa(f);
      if (F.y1 > P.y1 + 1 || F.x1 > P.x1 + 1 || F.x0 < P.x0 - 1) problemas.push(`<${f.tagName.toLowerCase()} class="${f.className}"> estoura .${pai.className.split(' ')[0]} (${Math.round(Math.max(F.y1 - P.y1, F.x1 - P.x1, P.x0 - F.x0))}px)`);
    }
  }
  for (const t of textos) {
    const box = t._el.closest('.cartao, .chat, .bolha, .barra, .elo, .item, .lin, .shot, .dia, .carta');
    if (!box) continue;
    const B = caixa(box);
    for (const q of t.rects) {
      const ax0 = q.x + cr.left; const ax1 = ax0 + q.w; const ay0 = q.y + cr.top + t.fs * 0.2; const ay1 = q.y + cr.top + q.h - t.fs * 0.2;
      if (ax0 < B.x0 - 1 || ax1 > B.x1 + 1 || ay0 < B.y0 - 1 || ay1 > B.y1 + 1) { problemas.push(`texto sai da caixa .${box.className.split(' ')[0]}: "${t.texto}"`); break; }
    }
  }
  for (const el of C.querySelectorAll('*')) {
    if (el.closest('.shot, svg') || el.classList.contains('luz')) continue;
    const cs = getComputedStyle(el);
    if (cs.overflow === 'visible' && cs.overflowX === 'visible' && cs.overflowY === 'visible') continue;
    if (el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1) problemas.push(`conteúdo cortado em <${el.tagName.toLowerCase()} class="${el.className}">`);
  }
  // Texto em cima de elemento visual (logo, tela, forma de onda, medidor, faixa de figurinha).
  const visuais = [...C.querySelectorAll('img, svg.forma, .shot, .medidor, [data-figurinha]')].filter((v) => !v.closest('.shot') || v.classList.contains('shot'));
  for (const t of textos) for (const v of visuais) {
    if (v.contains(t._el)) continue;
    const V = caixa(v);
    for (const q of t.rects) {
      const ax0 = q.x + cr.left + 1; const ax1 = ax0 + q.w - 2; const ay0 = q.y + cr.top + t.fs * 0.2; const ay1 = q.y + cr.top + q.h - t.fs * 0.2;
      if (ax0 < V.x1 && V.x0 < ax1 && ay0 < V.y1 && V.y0 < ay1) { problemas.push(`texto sobre ${v.classList.contains('logo') ? 'o logo' : v.hasAttribute('data-figurinha') ? 'a faixa da figurinha' : v.className.baseVal ?? v.className}: "${t.texto}"`); break; }
    }
  }
  // Elementos visuais (telas, figurinhas, cartões) também dentro da área segura na horizontal.
  for (const el of C.querySelectorAll('.shot, .chat, .cartao, .medidor, .forma, [data-figurinha]')) {
    const q = el.getBoundingClientRect();
    const x0 = q.left - cr.left; const x1 = q.right - cr.left; const y1 = q.bottom - cr.top; const y0 = q.top - cr.top;
    if (x0 < segura.x0 - 40 || x1 > segura.x1 + 40 || y0 < segura.y0 - 1 || y1 > segura.y1 + 1) problemas.push(`${el.className || 'figurinha'} sai da área segura (y ${Math.round(y0)}–${Math.round(y1)})`);
  }

  // Imagens carregadas e logo sem distorção.
  for (const img of C.querySelectorAll('img')) {
    if (!img.complete || !img.naturalWidth) { problemas.push(`imagem não carregou: ${img.src}`); continue; }
    if (img.classList.contains('logo')) {
      const q = img.getBoundingClientRect();
      const d = Math.abs(q.width / q.height - img.naturalWidth / img.naturalHeight) / (img.naturalWidth / img.naturalHeight);
      if (d > 0.01) problemas.push(`logo distorcido (${(d * 100).toFixed(1)}%)`);
    }
  }

  // Fontes da marca carregadas.
  const carregadas = [...document.fonts].filter((f) => f.status === 'loaded').map((f) => f.family.replace(/"/g, ''));
  for (const fam of ['Outfit', 'Geist Mono']) {
    const usa = textos.some((t) => t.familia.includes(fam));
    if (usa && !carregadas.includes(fam)) problemas.push(`fonte ${fam} não carregou`);
  }

  const figurinhas = [...C.querySelectorAll('[data-figurinha]')].map((el) => {
    const q = el.getBoundingClientRect();
    return { x: Math.round(q.left - cr.left), y: Math.round(q.top - cr.top), w: Math.round(q.width), h: Math.round(q.height) };
  });
  return { problemas, avisos, figurinhas, texto: C.innerText.replace(/\s+/g, ' ').trim(), textos: textos.map(({ _bloco, _el, ...t }) => t), temTela: !!C.querySelector('.shot, .chat') };
}

async function contraste(page, fundoB64, textos) {
  return page.evaluate(async ({ b64, textos }) => {
    const img = new Image();
    img.src = `data:image/png;base64,${b64}`;
    await img.decode();
    const cv = document.createElement('canvas');
    cv.width = img.width; cv.height = img.height;
    const cx = cv.getContext('2d', { willReadFrequently: true });
    cx.drawImage(img, 0, 0);
    const px = cx.getImageData(0, 0, cv.width, cv.height).data;
    const lin = (c) => { c /= 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
    const lum = (r, g, b) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
    const res = [];
    for (const t of textos) {
      const m = t.cor.match(/[\d.]+/g).map(Number);
      const a = (m[3] ?? 1) * t.op;
      const vals = [];
      for (const q of t.rects) {
        const y0 = Math.max(0, Math.round(q.y + t.fs * 0.2)); const y1 = Math.min(cv.height - 1, Math.round(q.y + q.h - t.fs * 0.2));
        const x0 = Math.max(0, Math.round(q.x)); const x1 = Math.min(cv.width - 1, Math.round(q.x + q.w));
        for (let y = y0; y <= y1; y += 3) for (let x = x0; x <= x1; x += 3) {
          const i = (y * cv.width + x) * 4;
          const br = px[i]; const bg = px[i + 1]; const bb = px[i + 2];
          const L1 = lum(m[0] * a + br * (1 - a), m[1] * a + bg * (1 - a), m[2] * a + bb * (1 - a));
          const L2 = lum(br, bg, bb);
          vals.push((Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05));
        }
      }
      if (!vals.length) continue;
      vals.sort((x, y) => x - y);
      res.push({ texto: t.texto, fs: t.fs, peso: t.peso, p10: +vals[Math.floor(vals.length * 0.1)].toFixed(2) });
    }
    return res;
  }, { b64: fundoB64, textos });
}

// ---------- execução ----------
fs.mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch();
const ctx = await browser.newContext({ deviceScaleFactor: 1, viewport: { width: 1080, height: 1920 } });
const page = await ctx.newPage();
const relatorio = [];
let falhas = 0;

const quer = (g, p) => !filtros.length || filtros.includes(g.id) || filtros.includes(p.id);

for (const g of grupos) {
  const [W, H] = TAM[g.formato];
  for (const p of g.pecas) {
    if (!quer(g, p)) continue;
    await page.setViewportSize({ width: W, height: H });
    await page.goto(`${BASE}/peca/${encodeURIComponent(p.id)}`, { waitUntil: 'networkidle' });
    await page.evaluate(async () => {
      await document.fonts.ready;
      await Promise.all([...document.images].map((i) => (i.complete ? 0 : new Promise((r) => { i.onload = i.onerror = r; }))));
    });
    const destino = path.join(OUT, pasta(g), `${p.id}.png`);
    fs.mkdirSync(path.dirname(destino), { recursive: true });
    const png = await page.locator('#c').screenshot({ path: destino, type: 'png' });
    const dim = { w: png.readUInt32BE(16), h: png.readUInt32BE(20) };

    const m = await page.evaluate(coletar, { segura: SEGURA[g.formato] });
    const problemas = [...m.problemas];
    const avisos = [...m.avisos];
    if (dim.w !== W || dim.h !== H) problemas.push(`tamanho ${dim.w}x${dim.h}, esperado ${W}x${H}`);
    problemas.push(...lintTexto(`${m.texto} ${p.alt}`));
    if (m.temTela && !/fictíci|demonstrativ|ilustrativ/i.test(m.texto)) problemas.push('tela ou conversa sem aviso de dados fictícios');
    if (p.figurinha && !m.figurinhas.length) problemas.push(`falta espaço para a figurinha "${p.figurinha}"`);

    await page.addStyleTag({ content: '#c *{color:transparent!important;-webkit-text-fill-color:transparent!important;text-shadow:none!important}' });
    const fundo = await page.locator('#c').screenshot({ type: 'png' });
    const cts = await contraste(page, fundo.toString('base64'), m.textos);
    for (const c of cts) {
      const minimo = c.fs >= 64 ? 3 : 4.5;
      if (c.p10 < minimo) problemas.push(`contraste ${c.p10}:1 (mín. ${minimo}) em "${c.texto}"`);
    }
    const piorContraste = cts.reduce((a, c) => (c.p10 < a.p10 ? c : a), { p10: 99 });

    const ok = problemas.length === 0;
    if (!ok) falhas++;
    relatorio.push({ id: p.id, grupo: g.id, arquivo: path.relative(RAIZ, destino), ok, problemas, avisos, pior_contraste: piorContraste.p10, figurinhas: m.figurinhas, alt: p.alt, figurinha: p.figurinha || null });
    console.log(`${ok ? 'OK  ' : 'FALHA'} ${p.id.padEnd(5)} contraste mín. ${String(piorContraste.p10).padEnd(5)} ${problemas.length ? '\n      - ' + problemas.join('\n      - ') : ''}${avisos.length ? `\n      (aviso) ${avisos.join('; ')}` : ''}`);
  }
}

// Legendas: mesmas regras de texto.
const legendas = path.join(DIR, 'legendas.md');
if (!AUTOTESTE && fs.existsSync(legendas) && !filtros.length) {
  // Hashtags e links ficam sem acento por convenção; trechos entre crases são instruções, não legenda.
  const corpo = fs.readFileSync(legendas, 'utf8').replace(/`[^`]*`/g, '').replace(/#[\p{L}\d_]+/gu, '').replace(/https?:\/\/\S+/g, '');
  const erros = lintTexto(corpo, { exigeEstimativa: false });
  if (!/estimativa/i.test(corpo)) erros.push('legendas citam preço por hora sem "estimativa"');
  console.log(`${erros.length ? 'FALHA' : 'OK  '} legendas.md${erros.length ? '\n      - ' + erros.join('\n      - ') : ''}`);
  if (erros.length) falhas++;
  relatorio.push({ id: 'legendas.md', ok: !erros.length, problemas: erros });
}

// Pranchas e prévia da grade do perfil (3:4).
if (!AUTOTESTE && !filtros.length) {
  const img = (g, p, w) => `<img src="/marketing/instagram/out/${pasta(g)}/${p.id}.png?${Date.now()}" style="width:${w}px;display:block;border-radius:6px">`;
  const estilo = '<style>body{margin:0;background:#0d0f14;font-family:Outfit,sans-serif;color:#fff}h2{font:600 28px Outfit;margin:36px 40px 16px}.l{display:flex;gap:16px;padding:0 40px;flex-wrap:wrap}.t{font:20px "Geist Mono",monospace;color:#aab;margin-top:8px}</style><link rel="stylesheet" href="/marketing/instagram/src/base.css">';
  for (const fmt of ['feed', 'story', 'tendencias']) {
    pranchaHtml = `<!doctype html><meta charset="utf-8">${estilo}<body style="width:${fmt === 'feed' ? 2000 : 2000}px">` +
      grupos.filter((g) => colecao(g) === fmt).map((g) => `<h2>${g.nome}</h2><div class="l">${g.pecas.map((p) => `<div>${img(g, p, fmt === 'story' ? 260 : 300)}<div class="t">${p.id}</div></div>`).join('')}</div>`).join('') + '<div style="height:40px"></div></body>';
    await page.setViewportSize({ width: 2000, height: 800 });
    await page.goto(`${BASE}/prancha`, { waitUntil: 'networkidle' });
    await page.screenshot({ path: path.join(OUT, `prancha-${fmt}.png`), fullPage: true });
  }
  // Grade do perfil: capa de cada post recortada em 3:4, como o Instagram mostra.
  const capas = grupos.filter((g) => colecao(g) === 'feed').flatMap((g) => (g.id === 'P' ? g.pecas : [g.pecas[0]]).map((p) => ({ g, p })));
  pranchaHtml = `<!doctype html><meta charset="utf-8">${estilo}<body style="width:1100px;background:#000"><div style="display:grid;grid-template-columns:repeat(3,1fr);gap:4px;padding:4px">` +
    capas.map(({ g, p }) => `<div style="aspect-ratio:3/4;overflow:hidden;position:relative"><img src="/marketing/instagram/out/${pasta(g)}/${p.id}.png" style="position:absolute;height:100%;left:50%;transform:translateX(-50%)"></div>`).join('') + '</div></body>';
  await page.setViewportSize({ width: 1100, height: 800 });
  await page.goto(`${BASE}/prancha`, { waitUntil: 'networkidle' });
  await page.screenshot({ path: path.join(OUT, 'grade-perfil.png'), fullPage: true });
}

if (AUTOTESTE) {
  let erradas = 0;
  for (const f of FIXTURES) {
    const r = relatorio.find((x) => x.id === f.id);
    const pegou = r && r.problemas.some((m) => m.includes(f.espera));
    if (!pegou) erradas++;
    console.log(`${pegou ? 'PEGOU ' : 'ESCAPOU'} ${f.id.padEnd(4)} espera "${f.espera}"`);
  }
  await browser.close(); servidor.close();
  console.log(`\nAutoteste: ${FIXTURES.length - erradas}/${FIXTURES.length} defeitos detectados.`);
  process.exit(erradas ? 1 : 0);
}
fs.writeFileSync(path.join(OUT, filtros.length ? 'checagem-parcial.json' : 'checagem.json'), JSON.stringify({ quando: new Date().toISOString(), falhas, pecas: relatorio }, null, 2));
await browser.close();
servidor.close();
console.log(`\n${relatorio.length} itens, ${falhas} com falha. Saída: ${path.relative(RAIZ, OUT)}/`);
process.exit(falhas ? 1 : 0);
