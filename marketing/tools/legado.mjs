// Renderiza os posts antigos do canvas (marketing/instagram/src/legado/*.html) em PNG 1080x1350.
import { chromium } from 'playwright';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const DIR = path.join(RAIZ, 'marketing/instagram/src/legado');
const OUT = path.join(RAIZ, 'marketing/instagram/out/legado');
fs.mkdirSync(OUT, { recursive: true });
const srv = http.createServer((req, res) => {
  const p = path.join(RAIZ, decodeURIComponent(new URL(req.url, 'http://x').pathname));
  if (!p.startsWith(RAIZ) || !fs.existsSync(p)) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'content-type': p.endsWith('.html') ? 'text/html; charset=utf-8' : p.endsWith('.png') ? 'image/png' : 'application/octet-stream' });
  fs.createReadStream(p).pipe(res);
});
await new Promise((r) => srv.listen(0, '127.0.0.1', r));
const base = `http://127.0.0.1:${srv.address().port}`;
const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1080, height: 1350 }, deviceScaleFactor: 1 });
for (const f of fs.readdirSync(DIR).filter((f) => f.endsWith('.html'))) {
  await page.goto(`${base}/marketing/instagram/src/legado/${f}`, { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);
  const fontes = await page.evaluate(() => [...document.fonts].filter((x) => x.status === 'loaded').map((x) => x.family).join(','));
  const out = path.join(OUT, f.replace('.html', '.png'));
  await page.locator('body > div').first().screenshot({ path: out });
  console.log(f, '->', path.relative(RAIZ, out), '| fontes:', [...new Set(fontes.split(','))].join(' '));
}
await b.close(); srv.close();
