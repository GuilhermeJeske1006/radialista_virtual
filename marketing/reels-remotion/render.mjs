// Renderiza o MP4 final e a capa de um Reel.
// Uso (em marketing/reels-remotion, depois de `npm install`): node render.mjs V5
// Antes: node ../tools/preparar.mjs V5 (gera montagem.json e legendas.srt).

import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";

const id = process.argv[2];
if (!id) {
  console.error("Uso: node render.mjs <id-do-video>");
  process.exit(2);
}
if (!existsSync(`../reels/${id}/montagem.json`)) {
  console.error(`Falta ../reels/${id}/montagem.json: rode antes node ../tools/preparar.mjs ${id}`);
  process.exit(2);
}
mkdirSync(`../reels/${id}/out`, { recursive: true });
const props = JSON.stringify({ id, montagem: null });
const npx = process.platform === "win32" ? "npx.cmd" : "npx";

execFileSync(npx, ["remotion", "render", "src/index.ts", "Reel", `../reels/${id}/out/${id}.mp4`, `--props=${props}`], {
  stdio: "inherit",
});
execFileSync(
  npx,
  ["remotion", "still", "src/index.ts", "Reel", `../reels/${id}/out/capa.jpg`, "--frame=20", `--props=${props}`],
  { stdio: "inherit" },
);
console.log(`${id}: ../reels/${id}/out/${id}.mp4 e capa.jpg prontos`);
