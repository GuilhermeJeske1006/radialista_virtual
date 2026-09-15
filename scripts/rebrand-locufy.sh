#!/usr/bin/env bash
#
# rebrand-locufy.sh — v3
#
# Além de trocar os tokens, redesenha o "chrome" da aplicação (sidebar, header,
# navegação, modais) para a linguagem visual da marca:
#
#   · cápsula  — o símbolo é um retângulo de raio igual à metade da largura.
#                Vira pílula em item de menu, botão e chip; rounded-3xl em cartão.
#   · monoline — traço 1.75, ponta e junta arredondadas, em todos os ícones.
#   · gradiente — aparece uma vez, no topo da sidebar, atrás do lockup.
#   · voz      — sem all-caps, sem monoespaçado na navegação. O mono sobra só
#                onde existe dado técnico.
#
# Uso:
#   ./rebrand-locufy.sh [caminho-do-frontend] [--build] [--no-branch]
#
# Roda tanto no código original da ONDA quanto por cima das versões anteriores
# deste script.

set -euo pipefail

APP="${1:-./frontend-painel}"
[[ "${APP}" == --* ]] && APP="./frontend-painel"
RODAR_BUILD=false
CRIAR_BRANCH=true
for arg in "$@"; do
  [[ "$arg" == "--build" ]] && RODAR_BUILD=true
  [[ "$arg" == "--no-branch" ]] && CRIAR_BRANCH=false
done

log()  { printf '\033[1;34m▸\033[0m %s\n' "$1"; }
ok()   { printf '\033[1;36m✓\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m!\033[0m %s\n' "$1"; }

[[ -d "$APP/app" && -d "$APP/components" ]] || { echo "Não achei o frontend em '$APP'."; exit 1; }
cd "$APP"
RAIZ_GIT="$(git rev-parse --show-toplevel 2>/dev/null || true)"

if [[ -n "$RAIZ_GIT" ]]; then
  if [[ -n "$(git status --porcelain)" ]]; then
    warn "Há alterações não commitadas. Commite ou faça stash antes de rodar."
    exit 1
  fi
  if $CRIAR_BRANCH; then
    git checkout -b rebrand/locufy 2>/dev/null || git checkout rebrand/locufy
    ok "branch rebrand/locufy"
  fi
else
  warn "Sem git aqui — sem rede de segurança. Faça um backup da pasta antes."
fi

# ═════════════════════════════════════════════════════════════════════════════
# 1. Tokens
#
#   amber → acento (#3167E7, meio do gradiente)   teal  → ciano
#   rust  → laranja                               paper → branco
#   ink   → grafite                               onda-*/Onda* → locufy-*/Locufy*
#
#   · text-ink → text-on-brand: o âmbar era claro e pedia texto escuro; o azul
#     é escuro e pede branco.
#   · text-/border-/ring-amber → *-acento-claro: sólido não alcança contraste
#     sobre o fundo escuro; a variante clara serve texto, ícone e borda.
#   · bg-paper/5 → bg-fg/5: overlay de hover passa a funcionar nos dois temas.
#
#   O segundo bloco converte a v1/v2 roxa. Em código que nunca passou por elas
#   não casa com nada.
# ═════════════════════════════════════════════════════════════════════════════
log "renomeando tokens em app/, components/, lib/"
mapfile -t ARQUIVOS < <(find app components lib -type f \
  \( -name '*.ts' -o -name '*.tsx' -o -name '*.css' -o -name '*.js' \) \
  -not -path '*/node_modules/*')

perl -pi -e '
  s/\bamber-dim\b/acento-dim/g;
  s/--color-amber\b/--color-acento-claro/g;
  s/\btext-amber\b/text-acento-claro/g;
  s/\bborder-amber\b/border-acento-claro/g;
  s/\bring-amber\b/ring-acento-claro/g;
  s/\bamber\b/acento/g;
  s/\bteal\b/ciano/g;
  s/\brust\b/laranja/g;
  s/\btext-ink\b/text-on-brand/g;
  s/\bbg-paper\//bg-fg\//g;
  s/\bpaper\b/branco/g;
  s/\bink\b/grafite/g;
  s/\bonda-/locufy-/g;
  s/\bOnda([A-Z]\w*)/Locufy$1/g;
  s/\bONDA\b/Locufy/g;

  s/\broxo-claro\b/acento-claro/g;
  s/\broxo-dim\b/acento-dim/g;
  s/--color-roxo\b/--color-acento/g;
  s/\broxo\b/acento/g;
' "${ARQUIVOS[@]}"
ok "${#ARQUIVOS[@]} arquivos varridos"

# Cápsula: raio de canto sobe um degrau em toda a aplicação.
log "arredondando: rounded-lg → rounded-xl, rounded-2xl → rounded-3xl"
perl -pi -e '
  s/\brounded-2xl\b/rounded-3xl/g;
  s/\brounded-lg\b/rounded-xl/g;
' "${ARQUIVOS[@]}"

log "movendo o componente de marca"
while IFS= read -r antigo; do
  novo="$(dirname "$antigo")/$(basename "$antigo" | sed 's/^Onda/Locufy/')"
  if [[ -n "$RAIZ_GIT" ]]; then git mv "$antigo" "$novo"; else mv "$antigo" "$novo"; fi
  ok "$(basename "$antigo") → $(basename "$novo")"
done < <(find components -name 'Onda*' -not -path '*/node_modules/*')

# ═════════════════════════════════════════════════════════════════════════════
# 2. Sistema de cores
# ═════════════════════════════════════════════════════════════════════════════
log "escrevendo o novo sistema de cores"
cat > app/globals.css <<'CSS'
@import "tailwindcss";

@theme {
  --font-sans: var(--font-locufy-sans), ui-sans-serif, system-ui, sans-serif;
  --font-display: var(--font-locufy-display), var(--font-locufy-sans), sans-serif;
  --font-mono: var(--font-plex-mono), monospace;

  /* papéis que mudam com o tema — valores em :root e [data-theme] abaixo */
  --color-bg: var(--locufy-bg);
  --color-surface: var(--locufy-surface);
  --color-surface-2: var(--locufy-surface-2);
  --color-fg: var(--locufy-fg);
  --color-border: var(--locufy-border);
  --color-border-strong: var(--locufy-border-strong);

  /* Paleta do manual — hex exatos */
  --color-roxo: #631bf6;         /* Roxo Frequência Digital — início do gradiente */
  --color-ciano-puro: #00b4d8;   /* Ciano Transmissão — fim do gradiente          */
  --color-azul: #1b263b;         /* Azul Estúdio Profissional — base da interface */
  --color-grafite: #18181a;      /* Preto Cabine Acústica                         */
  --color-branco: #ffffff;       /* Branco Clareza de Voz                         */
  --color-cinza: #6c707b;        /* Cinza Frequência Neutra                       */
  --color-laranja-puro: #ff8c00; /* Laranja Vibração Humana                       */

  /* Azul de ação: ponto médio exato do gradiente #631BF6 → #00B4D8. É a cor que
     o logo mostra na maior parte da faixa, e o que a interface usa para tudo
     que é clicável. */
  --color-acento: #3167e7;
  --color-on-brand: #ffffff;

  /* variantes legíveis — texto, ícone e borda, onde o sólido não alcança
     contraste contra o fundo do tema ativo */
  --color-acento-claro: var(--locufy-acento-claro);
  --color-acento-dim: var(--locufy-acento-dim);
  --color-ciano: var(--locufy-ciano);
  --color-laranja: var(--locufy-laranja);

  /* rampa brand-*: bg-brand-500 / text-brand-600 / focus:ring-brand-500 que já
     existem na aplicação passam a render o azul da marca sem tocar no markup */
  --color-brand-25: #eff4ff;
  --color-brand-50: #dfe9fe;
  --color-brand-100: #c2d4fc;
  --color-brand-200: #9bb6f8;
  --color-brand-300: #6d93f3;
  --color-brand-400: #4a79ee;
  --color-brand-500: #3167e7;
  --color-brand-600: #2352c7;
  --color-brand-700: #1c40a0;
  --color-brand-800: #17337d;
  --color-brand-900: #12275e;

  --shadow-theme-xs: 0 1px 2px 0 rgba(8, 14, 26, 0.32);
  --shadow-theme-sm: 0 1px 3px 0 rgba(8, 14, 26, 0.4), 0 1px 2px 0 rgba(8, 14, 26, 0.24);
}

/* Tema escuro (padrão): estúdio azul. Fundo é o Azul Estúdio rebaixado, painéis
   sobem para o #1B263B exato do manual — hierarquia por profundidade, sem
   precisar de borda em tudo. */
:root {
  --locufy-bg: #131c2e;
  --locufy-surface: #1b263b;
  --locufy-surface-2: #24334f;
  --locufy-fg: #ffffff;
  --locufy-border: rgba(255, 255, 255, 0.12);
  --locufy-border-strong: rgba(255, 255, 255, 0.22);

  --locufy-acento-claro: #6ba6ff;
  --locufy-acento-dim: #a8c8ff;
  --locufy-ciano: #00b4d8;
  --locufy-laranja: #ff8c00;
}

[data-theme="light"] {
  --locufy-bg: #ffffff;
  --locufy-surface: #f5f8fc;
  --locufy-surface-2: #e8eef7;
  --locufy-fg: #1b263b;
  --locufy-border: rgba(27, 38, 59, 0.12);
  --locufy-border-strong: rgba(27, 38, 59, 0.2);

  --locufy-acento-claro: #1e4fd8;
  --locufy-acento-dim: #12358f;
  --locufy-ciano: #0085a3;
  --locufy-laranja: #c96a00;

  --shadow-theme-xs: 0 1px 2px 0 rgba(27, 38, 59, 0.08);
  --shadow-theme-sm: 0 1px 3px 0 rgba(27, 38, 59, 0.12), 0 1px 2px 0 rgba(27, 38, 59, 0.08);
}

/* O gradiente do logo. Aparece uma vez por tela, atrás do lockup ou em uma
   superfície de marca — nunca como decoração de cartão. É o único lugar da
   interface onde o roxo puro entra. */
.bg-locufy-gradient {
  background-image: linear-gradient(110deg, #631bf6 0%, #3167e7 52%, #00b4d8 100%);
}

.text-locufy-gradient {
  background-image: linear-gradient(110deg, #631bf6 0%, #3167e7 52%, #00b4d8 100%);
  background-clip: text;
  color: transparent;
}

/* Foco visível e consistente, em pílula, sem depender de cada componente. */
:focus-visible {
  outline: 2px solid var(--color-acento-claro);
  outline-offset: 2px;
}

::selection {
  background: var(--color-acento);
  color: var(--color-on-brand);
}

::-webkit-scrollbar {
  width: 10px;
  height: 10px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: var(--color-border-strong);
  border-radius: 999px;
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
CSS
ok "app/globals.css"

# ═════════════════════════════════════════════════════════════════════════════
# 3. Layout, manifest e ícones
# ═════════════════════════════════════════════════════════════════════════════
log "escrevendo layout, manifest e ícones"

if [[ -f app/fonts/SamaLatin-Bold.woff2 && -f app/fonts/GothamRounded-Book.woff2 ]]; then
  cat > app/layout.tsx <<'TSX'
import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import { IBM_Plex_Mono } from "next/font/google";
import "./globals.css";

const samaLatin = localFont({
  src: [
    { path: "./fonts/SamaLatin-Regular.woff2", weight: "400", style: "normal" },
    { path: "./fonts/SamaLatin-Bold.woff2", weight: "700", style: "normal" },
  ],
  variable: "--font-locufy-display",
  display: "swap",
});

const gothamRounded = localFont({
  src: [
    { path: "./fonts/GothamRounded-Book.woff2", weight: "400", style: "normal" },
    { path: "./fonts/GothamRounded-Medium.woff2", weight: "500", style: "normal" },
    { path: "./fonts/GothamRounded-Bold.woff2", weight: "700", style: "normal" },
  ],
  variable: "--font-locufy-sans",
  display: "swap",
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-mono",
});

export const metadata: Metadata = {
  title: "Locufy — Painel",
  description: "Transforme audiência em conexão. Painel do radialista virtual.",
  appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: "Locufy" },
};

export const viewport: Viewport = { themeColor: "#131C2E" };

const TEMA_INICIAL_SCRIPT = `(function(){try{var t=localStorage.getItem("locufy-theme");if(t==="light")document.documentElement.setAttribute("data-theme","light");}catch(e){}})();`;

const SW_REGISTER_SCRIPT = `if("serviceWorker" in navigator){window.addEventListener("load",function(){navigator.serviceWorker.register("/sw.js").catch(function(){});});}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="pt-BR"
      data-theme="dark"
      suppressHydrationWarning
      className={`${samaLatin.variable} ${gothamRounded.variable} ${plexMono.variable}`}
    >
      <body className="font-sans bg-bg text-fg antialiased">
        <script dangerouslySetInnerHTML={{ __html: TEMA_INICIAL_SCRIPT }} />
        <script dangerouslySetInnerHTML={{ __html: SW_REGISTER_SCRIPT }} />
        {children}
      </body>
    </html>
  );
}
TSX
  ok "app/layout.tsx (fontes licenciadas, next/font/local)"
else
  cat > app/layout.tsx <<'TSX'
import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, Nunito, Outfit } from "next/font/google";
import "./globals.css";

// Substitutas enquanto as licenciadas não entram no repositório: Outfit no
// lugar da Sama Latin (títulos) e Nunito no lugar da Gotham Rounded (texto) —
// é a que mais se aproxima do "Locufy" arredondado do logo. Para trocar,
// coloque os .woff2 em app/fonts/ e rode o script de novo.
const displayFont = Outfit({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-locufy-display",
});

const sansFont = Nunito({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-locufy-sans",
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-mono",
});

export const metadata: Metadata = {
  title: "Locufy — Painel",
  description: "Transforme audiência em conexão. Painel do radialista virtual.",
  appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: "Locufy" },
};

export const viewport: Viewport = { themeColor: "#131C2E" };

const TEMA_INICIAL_SCRIPT = `(function(){try{var t=localStorage.getItem("locufy-theme");if(t==="light")document.documentElement.setAttribute("data-theme","light");}catch(e){}})();`;

const SW_REGISTER_SCRIPT = `if("serviceWorker" in navigator){window.addEventListener("load",function(){navigator.serviceWorker.register("/sw.js").catch(function(){});});}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="pt-BR"
      data-theme="dark"
      suppressHydrationWarning
      className={`${displayFont.variable} ${sansFont.variable} ${plexMono.variable}`}
    >
      <body className="font-sans bg-bg text-fg antialiased">
        <script dangerouslySetInnerHTML={{ __html: TEMA_INICIAL_SCRIPT }} />
        <script dangerouslySetInnerHTML={{ __html: SW_REGISTER_SCRIPT }} />
        {children}
      </body>
    </html>
  );
}
TSX
  warn "app/layout.tsx com fontes substitutas (Outfit/Nunito) — veja o item 2 no fim"
fi

cat > app/manifest.ts <<'TS'
import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Locufy — Painel do Radialista Virtual",
    short_name: "Locufy",
    description: "Transforme audiência em conexão. Painel do radialista virtual.",
    start_url: "/",
    display: "standalone",
    background_color: "#131C2E",
    theme_color: "#131C2E",
    lang: "pt-BR",
    icons: [
      { src: "/pwa-icon-192", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/pwa-icon-512", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/pwa-icon-512-maskable", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
TS
ok "app/manifest.ts"

cat > app/marca-icone.tsx <<'TSX'
/** Símbolo Locufy em branco sobre o gradiente — usado pelos ícones gerados via
 *  next/og (favicon, apple-icon, ícones do PWA). */
export function MarcaIcone({ canvas, mark }: { canvas: number; mark: number }) {
  return (
    <div
      style={{
        width: canvas,
        height: canvas,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "linear-gradient(110deg, #631BF6 0%, #3167E7 52%, #00B4D8 100%)",
      }}
    >
      <svg width={mark} height={mark} viewBox="0 0 64 64" fill="none">
        <rect x="21.5" y="7.5" width="33" height="49" rx="16.5" stroke="#FFFFFF" strokeWidth="3" />
        <rect x="30" y="17" width="16" height="21" rx="8" stroke="#FFFFFF" strokeWidth="3" />
        <path d="M28 34a10 10 0 0 0 20 0" stroke="#FFFFFF" strokeWidth="3" strokeLinecap="round" />
        <path d="M38 44v5" stroke="#FFFFFF" strokeWidth="3" strokeLinecap="round" />
        <path d="M15 27a8 8 0 0 1 2.4-5.7" stroke="#FFFFFF" strokeWidth="2.6" strokeLinecap="round" />
        <path d="M9.5 28a14 14 0 0 1 4-9.9" stroke="#FFFFFF" strokeWidth="2.6" strokeLinecap="round" />
        <path d="M4 29a20 20 0 0 1 5.7-14.1" stroke="#FFFFFF" strokeWidth="2.6" strokeLinecap="round" />
      </svg>
    </div>
  );
}
TSX

cat > app/icon.tsx <<'TSX'
import { ImageResponse } from "next/og";
import { MarcaIcone } from "./marca-icone";

export const size = { width: 32, height: 32 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(<MarcaIcone canvas={32} mark={24} />, { ...size });
}
TSX

cat > app/apple-icon.tsx <<'TSX'
import { ImageResponse } from "next/og";
import { MarcaIcone } from "./marca-icone";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(<MarcaIcone canvas={180} mark={124} />, { ...size });
}
TSX

for icone in 192 512 512-maskable; do
  case "$icone" in
    192)          dim=192; marca=132 ;;
    512)          dim=512; marca=352 ;;
    512-maskable) dim=512; marca=256 ;;  # área segura: glifo dentro de ~80%
  esac
  cat > "app/pwa-icon-$icone/route.tsx" <<TSX
import { ImageResponse } from "next/og";
import { MarcaIcone } from "../marca-icone";

export const dynamic = "force-static";

export async function GET() {
  return new ImageResponse(<MarcaIcone canvas={$dim} mark={$marca} />, {
    width: $dim,
    height: $dim,
  });
}
TSX
done
ok "ícones PWA + favicon"

# ═════════════════════════════════════════════════════════════════════════════
# 4. Marca
# ═════════════════════════════════════════════════════════════════════════════
log "escrevendo components/LocufyLogo.tsx"
cat > components/LocufyLogo.tsx <<'TSX'
type MarkProps = { size?: number; className?: string };

/**
 * Símbolo Locufy: microfone dentro do contorno em cápsula, com as ondas de
 * transmissão saindo à esquerda. Monoline em currentColor — igual ao logo
 * oficial, que é sempre de uma cor só (branco sobre o gradiente, azul sobre
 * fundo claro). Tendo o vetor do manual, troque o conteúdo deste componente e
 * mantenha currentColor.
 */
export function LocufyMark({ size = 34, className = "" }: MarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <rect x="21.5" y="7.5" width="33" height="49" rx="16.5" stroke="currentColor" strokeWidth="3" />
      <rect x="30" y="17" width="16" height="21" rx="8" stroke="currentColor" strokeWidth="3" />
      <path d="M28 34a10 10 0 0 0 20 0" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
      <path d="M38 44v5" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
      <path d="M15 27a8 8 0 0 1 2.4-5.7" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" />
      <path d="M9.5 28a14 14 0 0 1 4-9.9" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" />
      <path d="M4 29a20 20 0 0 1 5.7-14.1" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" />
    </svg>
  );
}

export function LocufyWordmark({ className = "" }: { className?: string }) {
  return <span className={`font-display font-medium tracking-tight ${className}`}>Locufy</span>;
}

/** Lockup completo. Herda a cor do container, então serve tanto em cima do
 *  gradiente quanto de fundo neutro, sem variante extra. */
export function LocufyLogo({
  size = 30,
  wordmarkClassName = "text-lg",
  tagline = false,
}: {
  size?: number;
  wordmarkClassName?: string;
  tagline?: boolean;
}) {
  return (
    <span className="flex items-center gap-2.5">
      <LocufyMark size={size} />
      <span className="flex flex-col">
        <LocufyWordmark className={wordmarkClassName} />
        {tagline && (
          <span className="text-[10px] font-semibold opacity-75">Transforme audiência em conexão.</span>
        )}
      </span>
    </span>
  );
}

/** LED de status piscando: no ar / conectado / gravando. */
export function LocufyLed({ color = "acento" as "acento" | "ciano" | "laranja", pulse = true }) {
  const dot = {
    acento: "bg-acento-claro shadow-[0_0_8px_var(--color-acento-claro)]",
    ciano: "bg-ciano shadow-[0_0_8px_var(--color-ciano)]",
    laranja: "bg-laranja shadow-[0_0_8px_var(--color-laranja)]",
  }[color];
  return (
    <span className="relative flex h-2.5 w-2.5 shrink-0">
      {pulse && <span className={`absolute inline-flex h-full w-full rounded-full opacity-75 animate-ping ${dot}`} />}
      <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${dot}`} />
    </span>
  );
}

/** Indicador de carregamento no lugar do "Carregando..." de texto puro. */
export function LocufySpin({ size = 20 }: { size?: number }) {
  return (
    <span className="inline-flex animate-spin" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="12" cy="12" r="10" stroke="var(--color-border-strong)" strokeWidth="2" />
        <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </svg>
    </span>
  );
}

/** Forma de onda animada: áudio ao vivo / geração em andamento. */
export function LocufyWaveform({ bars = 10, className = "" }: { bars?: number; className?: string }) {
  return (
    <span className={`inline-flex items-end gap-[2px] h-4 ${className}`} aria-hidden="true">
      {Array.from({ length: bars }).map((_, i) => (
        <i
          key={i}
          className="w-[2px] bg-current rounded-full animate-pulse"
          style={{
            height: `${30 + ((i * 37) % 70)}%`,
            animationDelay: `${i * 0.1}s`,
            animationDuration: "1s",
          }}
        />
      ))}
    </span>
  );
}
TSX
ok "components/LocufyLogo.tsx"

# ═════════════════════════════════════════════════════════════════════════════
# 5. Navegação, sidebar, header, modais e primitivas
# ═════════════════════════════════════════════════════════════════════════════
log "escrevendo a navegação (fonte única para sidebar e header)"
cat > components/nav.tsx <<'TSX'
/**
 * Navegação em um lugar só — sidebar (desktop) e header (mobile) liam duas
 * listas separadas e saíam de sincronia.
 *
 * Os ícones são monoline de traço 1.75 com ponta arredondada, o mesmo desenho
 * do símbolo da marca. Cada um nomeia o que a pessoa faz ali, não como o
 * sistema chama: microfone para locutores, ondas para transmissão.
 */

export type NavLink = {
  href: string;
  label: string;
  adminOnly?: boolean;
  icon: React.ReactNode;
};

export function NavIcone({ children, className = "h-5 w-5 shrink-0" }: { children: React.ReactNode; className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

export const NAV_LINKS: NavLink[] = [
  {
    href: "/dashboard",
    label: "Visão geral",
    icon: (
      <>
        <rect x="3.5" y="3.5" width="7" height="7" rx="2.5" />
        <rect x="13.5" y="3.5" width="7" height="7" rx="2.5" />
        <rect x="3.5" y="13.5" width="7" height="7" rx="2.5" />
        <rect x="13.5" y="13.5" width="7" height="7" rx="2.5" />
      </>
    ),
  },
  {
    href: "/live",
    label: "Ao vivo",
    icon: (
      <>
        <circle cx="12" cy="12" r="2" />
        <path d="M8.2 8.2a5.4 5.4 0 0 0 0 7.6" />
        <path d="M15.8 8.2a5.4 5.4 0 0 1 0 7.6" />
        <path d="M5.4 5.4a9.3 9.3 0 0 0 0 13.2" />
        <path d="M18.6 5.4a9.3 9.3 0 0 1 0 13.2" />
      </>
    ),
  },
  {
    href: "/radialista",
    label: "Locutores",
    icon: (
      <>
        <rect x="9" y="3" width="6" height="10" rx="3" />
        <path d="M6 11a6 6 0 0 0 12 0" />
        <path d="M12 17v4" />
      </>
    ),
  },
  {
    href: "/programas",
    label: "Programas",
    icon: (
      <>
        <path d="M9 6h11M9 12h11M9 18h11" />
        <circle cx="5" cy="6" r="1" />
        <circle cx="5" cy="12" r="1" />
        <circle cx="5" cy="18" r="1" />
      </>
    ),
  },
  {
    href: "/patrocinadores",
    label: "Patrocinadores",
    icon: (
      <>
        <path d="M4 10.5v3a1 1 0 0 0 1 1h2l6 3.5v-13L7 8.5H5a1 1 0 0 0-1 1Z" />
        <path d="M17.5 9.5a4 4 0 0 1 0 5" />
        <path d="M7 14.5V19" />
      </>
    ),
  },
  {
    href: "/onboarding",
    label: "WhatsApp",
    icon: (
      <>
        <path d="M20.5 11.6a8.5 8.5 0 0 1-12.4 7.5L3.5 20.5l1.4-4.6A8.5 8.5 0 1 1 20.5 11.6Z" />
        <circle cx="8.6" cy="11.8" r=".6" fill="currentColor" />
        <circle cx="12" cy="11.8" r=".6" fill="currentColor" />
        <circle cx="15.4" cy="11.8" r=".6" fill="currentColor" />
      </>
    ),
  },
  {
    href: "/billing",
    label: "Assinatura",
    adminOnly: true,
    icon: (
      <>
        <rect x="3" y="5" width="18" height="14" rx="3.5" />
        <path d="M3 10h18" />
        <path d="M7 14.5h3" />
      </>
    ),
  },
  {
    href: "/equipe",
    label: "Equipe",
    adminOnly: true,
    icon: (
      <>
        <circle cx="9.5" cy="8" r="3" />
        <path d="M4 19a5.5 5.5 0 0 1 11 0" />
        <path d="M16 5.6a3 3 0 0 1 0 5.8" />
        <path d="M17.6 13.6A5.5 5.5 0 0 1 20.5 18" />
      </>
    ),
  },
  {
    href: "/configuracoes",
    label: "Configuração",
    icon: (
      <>
        <path d="M5 4v5M5 14v6M12 4v2M12 11v9M19 4v8M19 17v3" />
        <circle cx="5" cy="11.5" r="2.2" />
        <circle cx="12" cy="8.5" r="2.2" />
        <circle cx="19" cy="14.5" r="2.2" />
      </>
    ),
  },
];

export const LINK_PERFIL: NavLink = {
  href: "/perfil",
  label: "Perfil",
  icon: (
    <>
      <circle cx="12" cy="8" r="3.5" />
      <path d="M5 19.5a7 7 0 0 1 14 0" />
    </>
  ),
};

export const ICONE_SAIR = (
  <>
    <path d="M14 4h3.5A2.5 2.5 0 0 1 20 6.5v11a2.5 2.5 0 0 1-2.5 2.5H14" />
    <path d="M10 8l-4 4 4 4" />
    <path d="M6 12h10" />
  </>
);
TSX
ok "components/nav.tsx"

log "escrevendo components/Sidebar.tsx"
cat > components/Sidebar.tsx <<'TSX'
"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clearToken } from "../lib/auth";
import { limparContaCache, useConta } from "../lib/useConta";
import { LocufyLogo } from "./LocufyLogo";
import { ICONE_SAIR, LINK_PERFIL, NAV_LINKS, NavIcone } from "./nav";

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const conta = useConta();
  const links = NAV_LINKS.filter((link) => !link.adminOnly || conta?.role === "admin");

  function sair() {
    clearToken();
    limparContaCache();
    router.push("/login");
  }

  // Pílula: o item ativo repete a forma da cápsula do símbolo, cheia; os
  // demais ficam só com o texto, sem caixa, para o ativo ser o único bloco
  // sólido da coluna.
  function classes(ativo: boolean) {
    return `flex items-center gap-3 rounded-full px-4 py-2.5 text-sm font-semibold transition-colors ${
      ativo
        ? "bg-acento text-on-brand shadow-[0_8px_24px_-10px_var(--color-acento)]"
        : "text-fg/65 hover:bg-fg/5 hover:text-fg"
    }`;
  }

  return (
    <aside className="hidden md:flex md:w-72.5 md:flex-col md:fixed md:inset-y-0 bg-surface border-r border-border">
      <div className="flex flex-col flex-1 min-h-0">
        {/* Único lugar da interface onde o gradiente aparece — atrás do lockup,
            como no material da marca. */}
        <div className="bg-locufy-gradient px-6 py-7 text-branco shrink-0">
          <LocufyLogo size={34} wordmarkClassName="text-xl" tagline />
        </div>

        <nav className="flex-1 overflow-y-auto px-4 py-5">
          <div className="space-y-1">
            {links.map((link) => (
              <Link key={link.href} href={link.href} className={classes(pathname === link.href)}>
                <NavIcone>{link.icon}</NavIcone>
                {link.label}
              </Link>
            ))}
          </div>
        </nav>

        <div className="px-4 pb-6 pt-2 space-y-1 border-t border-border">
          <Link href={LINK_PERFIL.href} className={classes(pathname === LINK_PERFIL.href)}>
            <NavIcone>{LINK_PERFIL.icon}</NavIcone>
            {LINK_PERFIL.label}
          </Link>
          <button
            onClick={sair}
            className="flex w-full items-center gap-3 rounded-full px-4 py-2.5 text-sm font-semibold text-fg/65 hover:bg-fg/5 hover:text-fg transition-colors"
          >
            <NavIcone>{ICONE_SAIR}</NavIcone>
            Sair
          </button>
        </div>
      </div>
    </aside>
  );
}
TSX
ok "components/Sidebar.tsx"

log "escrevendo components/AppShell.tsx"
cat > components/AppShell.tsx <<'TSX'
"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import Sidebar from "./Sidebar";
import { clearToken } from "../lib/auth";
import { limparContaCache, useConta } from "../lib/useConta";
import { LocufyMark, LocufyWaveform } from "./LocufyLogo";
import { LINK_PERFIL, NAV_LINKS, NavIcone } from "./nav";
import ThemeToggle from "./ThemeToggle";

export default function AppShell({
  title,
  children,
  noAr = false,
  maxWidthClassName = "max-w-4xl",
}: {
  title: string;
  children: React.ReactNode;
  /** Programa transmitindo agora — acende o indicador no header. */
  noAr?: boolean;
  maxWidthClassName?: string;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const conta = useConta();
  const links = NAV_LINKS.filter((link) => !link.adminOnly || conta?.role === "admin");

  function sair() {
    clearToken();
    limparContaCache();
    router.push("/login");
  }

  return (
    <div className="min-h-screen bg-bg">
      <Sidebar />
      <div className="md:pl-72.5 flex flex-col min-h-screen">
        <header className="sticky top-0 z-10 bg-bg/90 backdrop-blur border-b border-border">
          <div className="flex items-center justify-between h-16 px-4 sm:px-6">
            <div className="flex items-center gap-3 min-w-0">
              <LocufyMark size={24} className="shrink-0 text-acento-claro md:hidden" />
              <h1 className="font-display text-xl font-semibold text-fg truncate">{title}</h1>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {/* Estado, não etiqueta: a onda só se mexe quando tem programa no
                  ar, e o chip apaga quando não tem. */}
              <span
                className={`hidden sm:flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-semibold ${
                  noAr ? "bg-ciano/15 text-ciano" : "text-fg/40"
                }`}
              >
                {noAr ? <LocufyWaveform bars={5} className="h-3" /> : null}
                {noAr ? "No ar" : "Fora do ar"}
              </span>
              <ThemeToggle />
              <Link
                href={LINK_PERFIL.href}
                title="Perfil"
                aria-label="Perfil"
                className="flex h-9 w-9 items-center justify-center rounded-full bg-acento/12 text-acento-claro hover:bg-acento/20 transition-colors"
              >
                <NavIcone className="h-5 w-5">{LINK_PERFIL.icon}</NavIcone>
              </Link>
              <button
                onClick={sair}
                aria-label="Sair"
                title="Sair"
                className="hidden sm:flex h-9 w-9 items-center justify-center rounded-full text-fg/50 hover:bg-fg/5 hover:text-fg transition-colors"
              >
                <NavIcone className="h-5 w-5">
                  <path d="M14 4h3.5A2.5 2.5 0 0 1 20 6.5v11a2.5 2.5 0 0 1-2.5 2.5H14" />
                  <path d="M10 8l-4 4 4 4" />
                  <path d="M6 12h10" />
                </NavIcone>
              </button>
            </div>
          </div>

          {/* Mobile: pílulas roláveis, mesma forma do menu do desktop. */}
          <nav className="md:hidden flex gap-2 overflow-x-auto px-4 sm:px-6 pb-3">
            {links.map((link) => {
              const ativo = pathname === link.href;
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`shrink-0 rounded-full px-3.5 py-1.5 text-sm font-semibold whitespace-nowrap transition-colors ${
                    ativo ? "bg-acento text-on-brand" : "bg-fg/5 text-fg/60"
                  }`}
                >
                  {link.label}
                </Link>
              );
            })}
          </nav>
        </header>

        <main className="flex-1 px-4 sm:px-6 py-6">
          <div className={`${maxWidthClassName} mx-auto`}>{children}</div>
        </main>
      </div>
    </div>
  );
}
TSX
ok "components/AppShell.tsx"

log "escrevendo components/Modal.tsx e ConfirmDialog.tsx"
cat > components/Modal.tsx <<'TSX'
"use client";

import { useEffect } from "react";

type ModalProps = {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  maxWidthClassName?: string;
};

export default function Modal({ open, onClose, title, children, maxWidthClassName = "max-w-2xl" }: ModalProps) {
  useEffect(() => {
    if (!open) return;

    function aoTeclar(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }

    window.addEventListener("keydown", aoTeclar);
    const overflowOriginal = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", aoTeclar);
      document.body.style.overflow = overflowOriginal;
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-azul/70 p-4 backdrop-blur-sm sm:p-8"
      onClick={onClose}
    >
      <div
        className={`my-auto w-full ${maxWidthClassName} overflow-hidden rounded-3xl border border-border-strong bg-surface shadow-theme-sm`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-4 px-6 pt-5 pb-4">
          <h2 className="font-display text-lg font-semibold text-fg">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Fechar"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-fg/50 hover:bg-fg/5 hover:text-fg transition-colors"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" className="h-4 w-4">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        </div>
        <div className="max-h-[calc(100vh-9rem)] overflow-y-auto px-6 pb-6">{children}</div>
      </div>
    </div>
  );
}
TSX

cat > components/ConfirmDialog.tsx <<'TSX'
"use client";

import Modal from "./Modal";

type ConfirmDialogProps = {
  open: boolean;
  title: string;
  mensagem: string;
  confirmarLabel?: string;
  cancelarLabel?: string;
  onConfirmar: () => void;
  onCancelar: () => void;
};

export default function ConfirmDialog({
  open,
  title,
  mensagem,
  confirmarLabel = "Excluir",
  cancelarLabel = "Cancelar",
  onConfirmar,
  onCancelar,
}: ConfirmDialogProps) {
  return (
    <Modal open={open} onClose={onCancelar} title={title} maxWidthClassName="max-w-sm">
      <p className="text-sm text-fg/70 mb-6">{mensagem}</p>
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancelar}
          className="rounded-full px-4 py-2.5 text-sm font-semibold text-fg/60 hover:bg-fg/5 hover:text-fg transition-colors"
        >
          {cancelarLabel}
        </button>
        {/* A paleta não tem vermelho. Destrutivo usa o Laranja Vibração Humana
            com texto grafite — é o sinal mais alto do manual. */}
        <button
          type="button"
          onClick={onConfirmar}
          className="rounded-full bg-laranja px-4 py-2.5 text-sm font-semibold text-grafite hover:opacity-90 transition-opacity"
        >
          {confirmarLabel}
        </button>
      </div>
    </Modal>
  );
}
TSX
ok "Modal.tsx, ConfirmDialog.tsx"

log "escrevendo components/ui.tsx (primitivas para as telas migrarem)"
cat > components/ui.tsx <<'TSX'
/**
 * Primitivas da marca. As telas ainda repetem classes soltas de cartão e botão;
 * conforme forem mexidas, troque por estes componentes para o raio, o peso e o
 * espaçamento pararem de divergir tela a tela.
 */

export function Cartao({
  children,
  className = "",
  destaque = false,
}: {
  children: React.ReactNode;
  className?: string;
  /** Realce por borda de acento, para o cartão que pede ação agora. */
  destaque?: boolean;
}) {
  return (
    <div
      className={`rounded-3xl bg-surface p-5 shadow-theme-xs border ${
        destaque ? "border-acento/50 ring-1 ring-acento/15" : "border-border"
      } ${className}`}
    >
      {children}
    </div>
  );
}

export function TituloSecao({ children, acao }: { children: React.ReactNode; acao?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 mb-3">
      <h2 className="font-display text-base font-semibold text-fg">{children}</h2>
      {acao}
    </div>
  );
}

type BotaoProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variante?: "primario" | "secundario" | "fantasma" | "destrutivo";
};

const VARIANTES: Record<NonNullable<BotaoProps["variante"]>, string> = {
  primario: "bg-acento text-on-brand hover:bg-brand-600",
  secundario: "border border-border-strong text-fg hover:bg-fg/5",
  fantasma: "text-fg/60 hover:bg-fg/5 hover:text-fg",
  destrutivo: "bg-laranja text-grafite hover:opacity-90",
};

/** Pílula: mesma forma da cápsula do símbolo. */
export function Botao({ variante = "primario", className = "", ...props }: BotaoProps) {
  return (
    <button
      {...props}
      className={`inline-flex items-center justify-center gap-2 rounded-full px-4 py-2.5 text-sm font-semibold transition-colors disabled:opacity-60 disabled:cursor-not-allowed ${VARIANTES[variante]} ${className}`}
    />
  );
}

export function Chip({
  children,
  tom = "neutro",
}: {
  children: React.ReactNode;
  tom?: "neutro" | "acento" | "ciano" | "laranja";
}) {
  const tons = {
    neutro: "bg-fg/5 text-fg/60",
    acento: "bg-acento/15 text-acento-claro",
    ciano: "bg-ciano/15 text-ciano",
    laranja: "bg-laranja/15 text-laranja",
  }[tom];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${tons}`}>
      {children}
    </span>
  );
}

/** Tela vazia: convite para agir, nunca só "nada aqui". */
export function Vazio({
  titulo,
  descricao,
  acao,
}: {
  titulo: string;
  descricao: string;
  acao?: React.ReactNode;
}) {
  return (
    <div className="rounded-3xl border border-dashed border-border-strong px-6 py-12 text-center">
      <p className="font-display text-base font-semibold text-fg">{titulo}</p>
      <p className="mt-1 text-sm text-fg/55">{descricao}</p>
      {acao && <div className="mt-5 flex justify-center">{acao}</div>}
    </div>
  );
}
TSX
ok "components/ui.tsx"

# Os labels da navegação mudaram ("Dashboard" → "Visão geral", "Radialistas" →
# "Locutores"). O título de cada página é passado no AppShell de cada tela.
log "alinhando os títulos das páginas com os rótulos do menu"
perl -pi -e 's/title="Dashboard"/title="Visão geral"/g; s/title="Radialistas"/title="Locutores"/g; s/title="Ao Vivo"/title="Ao vivo"/g;' \
  $(find app -name 'page.tsx' -not -path '*/node_modules/*') 2>/dev/null || true

# ═════════════════════════════════════════════════════════════════════════════
# 6. Verificação
# ═════════════════════════════════════════════════════════════════════════════
log "procurando sobras da identidade antiga"
SOBRAS="$(grep -rniE 'ONDA\b|\bOnda[A-Z]|--onda-|onda-theme|#e8a33d|#15130f|#f4ead9|#33c2a8|#e2543a|\b(amber|teal|rust|paper|ink|roxo)\b' \
  app components lib public 2>/dev/null | grep -v node_modules || true)"
if [[ -z "$SOBRAS" ]]; then
  ok "nada de ONDA no frontend"
else
  warn "revise manualmente:"
  echo "$SOBRAS"
fi

if [[ -n "$RAIZ_GIT" ]]; then
  FORA="$(cd "$RAIZ_GIT" && grep -rlw 'ONDA' . 2>/dev/null | grep -v node_modules | grep -v '^\./frontend-painel' || true)"
  [[ -n "$FORA" ]] && { warn "'ONDA' também aparece fora do frontend (backend, prompts, e-mails, README):"; echo "$FORA"; }
fi

log "typecheck"
npx tsc --noEmit 2>/dev/null || warn "tsc acusou erro — provavelmente uma tela importando algo renomeado"

log "testes"
npm test -- --run 2>/dev/null || warn "testes falharam ou não existem — confira antes de commitar"

if $RODAR_BUILD; then
  log "build de produção"
  npm run build
fi

cat <<'FIM'

──────────────────────────────────────────────────────────────────────
Rebrand + redesenho aplicados.

FORMA
  · cápsula do símbolo vira pílula: menu, botão e chip em rounded-full
  · cartão sobe para rounded-3xl; rounded-lg vira rounded-xl
  · ícones monoline 1.75 de ponta arredondada, set autoral em components/nav.tsx

COR
  · fundo e painéis   → Azul Estúdio (#131C2E / #1B263B / #24334F)
  · clicável          → #3167E7, o meio do gradiente do logo
  · ao vivo / áudio   → Ciano Transmissão (#00B4D8)
  · destrutivo/alerta → Laranja Vibração Humana (#FF8C00) com texto grafite
  · gradiente e roxo puro → só no topo da sidebar e nos ícones da marca

VOZ
  · saiu o dial de FM, o all-caps dos rótulos e o mono da navegação
  · "Dashboard" → "Visão geral", "Radialistas" → "Locutores": o menu passa a
    nomear o que a pessoa faz, não como o sistema chama

O QUE AINDA É DECISÃO SUA

1. Indicador "no ar" — o header antes mostrava "NO AR" fixo, sem estado real.
   Agora é <AppShell noAr={...}>, com padrão false. Passe o estado verdadeiro
   em app/live/page.tsx (a variável programaAtivo) e nas telas que souberem.

2. Telas internas — o script padroniza o chrome, não o interior das páginas.
   components/ui.tsx traz Cartao, Botao, Chip, TituloSecao e Vazio para as
   telas irem convergindo conforme forem mexidas. Comece por dashboard e live,
   que são as mais vistas.

3. SVG oficial — components/LocufyLogo.tsx traz uma reconstrução em
   currentColor. Troque pelo vetor do manual quando tiver, mantendo currentColor
   para o lockup continuar servindo sobre o gradiente e sobre fundo claro.

4. Fontes — Sama Latin e Gotham Rounded são licenciadas e não estão no Google
   Fonts. Coloque os .woff2 em app/fonts/ com estes nomes e rode de novo:
     SamaLatin-Regular.woff2      GothamRounded-Book.woff2
     SamaLatin-Bold.woff2         GothamRounded-Medium.woff2
                                  GothamRounded-Bold.woff2

5. Rota /dashboard — o rótulo mudou, a rota não. Renomear a pasta é uma
   migração à parte, com redirect, e o script não encosta nisso.

Para desfazer:  git checkout . && git checkout - && git branch -D rebrand/locufy
──────────────────────────────────────────────────────────────────────
FIM
