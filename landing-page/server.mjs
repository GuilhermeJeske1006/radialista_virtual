import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const root = fileURLToPath(new URL(process.env.SERVE_DIST === '1' ? './dist/' : '.', import.meta.url));
const types = { '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.webp': 'image/webp', '.png': 'image/png', '.jpg': 'image/jpeg', '.txt': 'text/plain; charset=utf-8', '.xml': 'application/xml; charset=utf-8', '.mp3': 'audio/mpeg', '.mp4': 'video/mp4', '.vtt': 'text/vtt; charset=utf-8' };
const port = Number(process.env.PORT || 3010);
http.createServer(async (req, res) => {
  try {
    if (!['GET', 'HEAD'].includes(req.method)) { res.writeHead(405); res.end(); return; }
    const pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
    const relative = pathname === '/' ? 'index.html' : pathname.slice(1);
    if (!['index.html', 'styles.css', 'script.js', 'theme.js', 'config.js', 'robots.txt', 'sitemap.xml'].includes(relative) && !/^assets\/[a-zA-Z0-9_.-]+$/.test(relative)) { res.writeHead(404); res.end('Não encontrado'); return; }
    const data = await readFile(path.join(root, relative));
    res.writeHead(200, { 'Content-Type': types[path.extname(relative)] || 'application/octet-stream', 'X-Content-Type-Options': 'nosniff' });
    res.end(req.method === 'HEAD' ? undefined : data);
  } catch { res.writeHead(404); res.end('Não encontrado'); }
}).listen(port, '127.0.0.1', () => console.log(`Locufy landing page: http://localhost:${port}`));
