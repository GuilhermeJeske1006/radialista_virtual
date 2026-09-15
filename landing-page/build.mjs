import { cp, mkdir } from 'node:fs/promises';
const source = new URL('.', import.meta.url);
const output = new URL('dist/', source);
await mkdir(output, { recursive: true });
for (const file of ['index.html', 'styles.css', 'script.js', 'theme.js', 'config.js', 'robots.txt', 'sitemap.xml', 'assets']) {
  await cp(new URL(file, source), new URL(file, output), { recursive: true });
}
console.log('Landing page pronta em dist/. Publique o conteúdo em uma hospedagem estática.');
