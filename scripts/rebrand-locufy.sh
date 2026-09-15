#!/usr/bin/env bash
#
# rebrand-locufy.sh — troca a identidade "ONDA" pela identidade Locufy
# (manual da marca: roxo #631BF6, ciano #00B4D8, azul #1B263B, laranja #FF8C00,
#  preto #18181A, branco #FFFFFF, cinza #6C707B / Sama Latin + Gotham Rounded)
#
# Uso:
#   ./rebrand-locufy.sh [caminho-do-frontend] [--build] [--no-branch]
#
#   ./rebrand-locufy.sh                      # assume ./frontend-painel
#   ./rebrand-locufy.sh ./frontend-painel --build
#
# O que faz:
#   1. cria a branch rebrand/locufy (a menos que --no-branch)
#   2. renomeia os tokens de cor/tipografia em app/, components/ e lib/
#   3. reescreve globals.css, layout.tsx, manifest.ts e os ícones PWA
#   4. troca components/OndaLogo.tsx por components/LocufyLogo.tsx
#   5. roda os testes e mostra o que sobrou de "ONDA" no repositório
#
# É idempotente: rodar duas vezes não quebra nada (a 2ª passada não acha mais
# nenhum token antigo).

set -euo pipefail

APP="${1:-./frontend-painel}"
[[ "${APP}" == --* ]] && APP="./frontend-painel"
RODAR_BUILD=false
CRIAR_BRANCH=true
for arg in "$@"; do
  [[ "$arg" == "--build" ]] && RODAR_BUILD=true
  [[ "$arg" == "--no-branch" ]] && CRIAR_BRANCH=false
done

log()  { printf '\033[1;35m▸\033[0m %s\n' "$1"; }
ok()   { printf '\033[1;36m✓\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m!\033[0m %s\n' "$1"; }

[[ -d "$APP/app" && -d "$APP/components" ]] || { echo "Não achei o frontend em '$APP'."; exit 1; }
cd "$APP"
RAIZ_GIT="$(git rev-parse --show-toplevel 2>/dev/null || true)"

# ─────────────────────────────────────────────────────────────────────────────
# 0. Segurança: árvore limpa + branch própria
# ─────────────────────────────────────────────────────────────────────────────
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

# ─────────────────────────────────────────────────────────────────────────────
# 1. Renomeia tokens no código todo
#
#    amber      → roxo         (Roxo Frequência Digital  #631BF6)
#    teal       → ciano        (Ciano Transmissão        #00B4D8)
#    rust       → laranja      (Laranja Vibração Humana  #FF8C00)
#    paper      → branco       (Branco Clareza de Voz    #FFFFFF)
#    ink        → grafite      (Preto Cabine Acústica    #18181A)
#    onda-*     → locufy-*     (css vars + chave do localStorage)
#    Onda<X>    → Locufy<X>    (componentes e imports)
#
#    Dois ajustes de contraste que o rename resolve de graça:
#    · text-ink → text-on-brand: o amber era claro (pedia texto escuro em cima),
#      o roxo é escuro (pede texto branco). on-brand = #FFFFFF.
#    · text-/border-/ring-amber → *-roxo-claro: roxo puro em cima do fundo
#      #18181A fica ilegível; a variante clara existe só para texto/ícone/borda.
#      Fundos sólidos (bg-roxo, bg-brand-500) continuam no roxo exato da marca.
#    · bg-paper/5 → bg-fg/5: overlays de hover passam a funcionar nos dois temas.
# ─────────────────────────────────────────────────────────────────────────────
log "renomeando tokens em app/, components/, lib/"
mapfile -t ARQUIVOS < <(find app components lib -type f \
  \( -name '*.ts' -o -name '*.tsx' -o -name '*.css' -o -name '*.js' \) \
  -not -path '*/node_modules/*')

perl -pi -e '
  s/\bamber-dim\b/roxo-dim/g;
  s/--color-amber\b/--color-roxo-claro/g;
  s/\btext-amber\b/text-roxo-claro/g;
  s/\bborder-amber\b/border-roxo-claro/g;
  s/\bring-amber\b/ring-roxo-claro/g;
  s/\bamber\b/roxo/g;
  s/\bteal\b/ciano/g;
  s/\brust\b/laranja/g;
  s/\btext-ink\b/text-on-brand/g;
  s/\bbg-paper\//bg-fg\//g;
  s/\bpaper\b/branco/g;
  s/\bink\b/grafite/g;
  s/\bonda-/locufy-/g;
  s/\bOnda([A-Z]\w*)/Locufy$1/g;
  s/\bONDA\b/Locufy/g;
' "${ARQUIVOS[@]}"
ok "${#ARQUIVOS[@]} arquivos varridos"

# ─────────────────────────────────────────────────────────────────────────────
# 2. components/OndaLogo.tsx → components/LocufyLogo.tsx
# ─────────────────────────────────────────────────────────────────────────────
log "movendo o componente de marca"
while IFS= read -r antigo; do
  novo="$(dirname "$antigo")/$(basename "$antigo" | sed 's/^Onda/Locufy/')"
  if [[ -n "$RAIZ_GIT" ]]; then git mv "$antigo" "$novo"; else mv "$antigo" "$novo"; fi
  ok "$(basename "$antigo") → $(basename "$novo")"
done < <(find components -name 'Onda*' -not -path '*/node_modules/*')

# ─────────────────────────────────────────────────────────────────────────────
# 3. Arquivos reescritos por inteiro
# ─────────────────────────────────────────────────────────────────────────────
log "escrevendo o novo sistema de cores"
cat > app/globals.css <<'CSS'
@import "tailwindcss";

@theme {
  --font-sans: var(--font-locufy-sans), ui-sans-serif, system-ui, sans-serif;
  --font-display: var(--font-locufy-display), var(--font-locufy-sans), sans-serif;
  --font-mono: var(--font-plex-mono), monospace;

  /* papéis que mudam com o tema: valores lá embaixo, em :root e [data-theme] */
  --color-bg: var(--locufy-bg);
  --color-surface: var(--locufy-surface);
  --color-surface-2: var(--locufy-surface-2);
  --color-fg: var(--locufy-fg);
  --color-border: var(--locufy-border);
  --color-border-strong: var(--locufy-border-strong);

  /* Paleta do manual — hex exatos, iguais nos dois temas */
  --color-roxo: #631bf6;    /* Roxo Frequência Digital     */
  --color-ciano-puro: #00b4d8; /* Ciano Transmissão        */
  --color-azul: #1b263b;    /* Azul Estúdio Profissional   */
  --color-laranja-puro: #ff8c00; /* Laranja Vibração Humana */
  --color-grafite: #18181a; /* Preto Cabine Acústica       */
  --color-branco: #ffffff;  /* Branco Clareza de Voz       */
  --color-cinza: #6c707b;   /* Cinza Frequência Neutra     */

  /* texto/ícone em cima de fundo roxo — o roxo é escuro, então é sempre branco */
  --color-on-brand: #ffffff;

  /* variantes legíveis: usadas em texto, ícone e borda, onde o hex puro
     não alcança contraste suficiente contra o fundo do tema ativo */
  --color-roxo-claro: var(--locufy-roxo-claro);
  --color-roxo-dim: var(--locufy-roxo-dim);
  --color-ciano: var(--locufy-ciano);
  --color-laranja: var(--locufy-laranja);

  /* rampa brand-*: bg-brand-500 / text-brand-600 / focus:ring-brand-500 que já
     existem na aplicação passam a render o roxo da marca sem tocar no markup */
  --color-brand-25: #f4f0ff;
  --color-brand-50: #ece4ff;
  --color-brand-100: #d9c9ff;
  --color-brand-200: #bda3ff;
  --color-brand-300: #9d76fb;
  --color-brand-400: #7f45f9;
  --color-brand-500: #631bf6;
  --color-brand-600: #5415d4;
  --color-brand-700: #4511ad;
  --color-brand-800: #360d88;
  --color-brand-900: #270a63;

  --shadow-theme-xs: 0 1px 2px 0 rgba(0, 0, 0, 0.28);
  --shadow-theme-sm: 0 1px 3px 0 rgba(0, 0, 0, 0.36), 0 1px 2px 0 rgba(0, 0, 0, 0.22);
}

/* tema escuro (padrão): cabine acústica com painéis em azul estúdio */
:root {
  --locufy-bg: #18181a;
  --locufy-surface: #1f1f26;
  --locufy-surface-2: #1b263b;
  --locufy-fg: #ffffff;
  --locufy-border: rgba(255, 255, 255, 0.12);
  --locufy-border-strong: rgba(255, 255, 255, 0.22);

  --locufy-roxo-claro: #9a7bfa;
  --locufy-roxo-dim: #c9b8fe;
  --locufy-ciano: #00b4d8;
  --locufy-laranja: #ff8c00;
}

[data-theme="light"] {
  --locufy-bg: #ffffff;
  --locufy-surface: #f7f7fa;
  --locufy-surface-2: #eef0f5;
  --locufy-fg: #18181a;
  --locufy-border: rgba(24, 24, 26, 0.1);
  --locufy-border-strong: rgba(24, 24, 26, 0.18);

  --locufy-roxo-claro: #631bf6;
  --locufy-roxo-dim: #4a12c4;
  --locufy-ciano: #0085a3;
  --locufy-laranja: #c96a00;

  --shadow-theme-xs: 0 1px 2px 0 rgba(24, 24, 26, 0.08);
  --shadow-theme-sm: 0 1px 3px 0 rgba(24, 24, 26, 0.12), 0 1px 2px 0 rgba(24, 24, 26, 0.08);
}

::selection {
  background: var(--color-roxo);
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
CSS
ok "app/globals.css"

log "escrevendo layout, manifest e ícones"

# Sama Latin e Gotham Rounded são licenciadas — se os arquivos estiverem em
# app/fonts/ o layout usa next/font/local; se não, cai em substitutas do Google
# com o mesmo espírito (Outfit = geométrica de título, Nunito = grotesca
# arredondada de texto).
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
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Locufy",
  },
};

export const viewport: Viewport = {
  themeColor: "#18181A",
};

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

// Substitutas enquanto as licenciadas não entram no repositório:
// Outfit fica no lugar da Sama Latin (títulos) e Nunito no lugar da Gotham
// Rounded (texto). Para trocar: coloque os .woff2 em app/fonts/ e rode o
// script de novo — ele detecta os arquivos e reescreve este layout com
// next/font/local, sem mudar mais nada da aplicação.
const displayFont = Outfit({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
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
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Locufy",
  },
};

export const viewport: Viewport = {
  themeColor: "#18181A",
};

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
  warn "app/layout.tsx com fontes substitutas (Outfit/Nunito) — veja o passo 3 no final"
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
    background_color: "#18181A",
    theme_color: "#18181A",
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

# Ícones: "L" branco sobre o gradiente roxo → ciano da marca.
escrever_icone() {  # $1 = arquivo, $2 = corpo do export
  cat > "$1" <<TSX
import { ImageResponse } from "next/og";

$2
TSX
}

cat > app/icon.tsx <<'TSX'
import { ImageResponse } from "next/og";

export const size = { width: 32, height: 32 };
export const contentType = "image/png";

const MARCA = {
  width: "100%",
  height: "100%",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  background: "linear-gradient(135deg, #631BF6 0%, #00B4D8 100%)",
  color: "#FFFFFF",
  fontWeight: 700,
  fontFamily: "sans-serif",
} as const;

export default function Icon() {
  return new ImageResponse(<div style={{ ...MARCA, fontSize: 22 }}>L</div>, { ...size });
}
TSX

cat > app/apple-icon.tsx <<'TSX'
import { ImageResponse } from "next/og";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "linear-gradient(135deg, #631BF6 0%, #00B4D8 100%)",
          color: "#FFFFFF",
          fontSize: 120,
          fontWeight: 700,
          fontFamily: "sans-serif",
        }}
      >
        L
      </div>
    ),
    { ...size }
  );
}
TSX

for icone in 192 512 512-maskable; do
  case "$icone" in
    192)          dim=192; fonte=130 ;;
    512)          dim=512; fonte=340 ;;
    512-maskable) dim=512; fonte=220 ;;  # área segura: glifo dentro de ~80%
  esac
  cat > "app/pwa-icon-$icone/route.tsx" <<TSX
import { ImageResponse } from "next/og";

export const dynamic = "force-static";

export async function GET() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "linear-gradient(135deg, #631BF6 0%, #00B4D8 100%)",
          color: "#FFFFFF",
          fontSize: $fonte,
          fontWeight: 700,
          fontFamily: "sans-serif",
        }}
      >
        L
      </div>
    ),
    { width: $dim, height: $dim }
  );
}
TSX
done
ok "ícones PWA + favicon"

log "escrevendo components/LocufyLogo.tsx"
cat > components/LocufyLogo.tsx <<'TSX'
type MarkProps = { size?: number; className?: string };

/**
 * Símbolo Locufy: cápsula de microfone dentro do contorno arredondado, com as
 * ondas de transmissão saindo à esquerda.
 *
 * Isto é a reconstrução em SVG inline (herda a cor do tema via CSS vars). Se o
 * arquivo vetorial oficial do manual estiver disponível, troque o conteúdo
 * deste componente pelo SVG exportado do original.
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
    >
      <rect
        x="20.5"
        y="6.5"
        width="35"
        height="51"
        rx="17.5"
        stroke="var(--color-roxo-claro)"
        strokeWidth="3"
      />
      <rect
        x="30"
        y="16"
        width="16"
        height="21"
        rx="8"
        stroke="var(--color-roxo-claro)"
        strokeWidth="3"
      />
      <path
        d="M27 33a11 11 0 0 0 22 0"
        stroke="var(--color-roxo-claro)"
        strokeWidth="3"
        strokeLinecap="round"
      />
      <path d="M38 44v5" stroke="var(--color-roxo-claro)" strokeWidth="3" strokeLinecap="round" />
      <path d="M14 27a9 9 0 0 1 2.6-6.4" stroke="var(--color-ciano)" strokeWidth="2.6" strokeLinecap="round" />
      <path d="M8 28a15 15 0 0 1 4.4-10.6" stroke="var(--color-ciano)" strokeWidth="2.6" strokeLinecap="round" />
      <path d="M2 29a21 21 0 0 1 6.2-14.8" stroke="var(--color-ciano)" strokeWidth="2.6" strokeLinecap="round" />
    </svg>
  );
}

export function LocufyWordmark({ className = "" }: { className?: string }) {
  return <span className={`font-display font-bold tracking-tight ${className}`}>Locufy</span>;
}

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
      <span className="flex flex-col leading-none">
        <LocufyWordmark className={wordmarkClassName} />
        {tagline && (
          <span className="mt-1 text-[10px] text-fg/50">Transforme audiência em conexão.</span>
        )}
      </span>
    </span>
  );
}

/** LED de status piscando, ex.: "no ar" / conectado / gravando. */
export function LocufyLed({ color = "roxo" as "roxo" | "ciano" | "laranja", pulse = true }) {
  const dot = {
    roxo: "bg-roxo-claro shadow-[0_0_8px_var(--color-roxo-claro)]",
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
        <path d="M12 2a10 10 0 0 1 10 10" stroke="var(--color-roxo-claro)" strokeWidth="2" strokeLinecap="round" />
      </svg>
    </span>
  );
}

/** Forma de onda animada, indica áudio ao vivo / geração em andamento. */
export function LocufyWaveform({ bars = 10, className = "" }: { bars?: number; className?: string }) {
  return (
    <span className={`inline-flex items-end gap-[2px] h-4 ${className}`}>
      {Array.from({ length: bars }).map((_, i) => (
        <i
          key={i}
          className="w-[2px] bg-ciano rounded-full animate-pulse"
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

# ─────────────────────────────────────────────────────────────────────────────
# 4. Verificação
# ─────────────────────────────────────────────────────────────────────────────
log "procurando sobras da identidade antiga"
SOBRAS="$(grep -rniE 'ONDA\b|\bOnda[A-Z]|--onda-|onda-theme|#e8a33d|#15130f|#f4ead9|#33c2a8|#e2543a|\b(amber|teal|rust|paper|ink)\b' \
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

log "rodando os testes"
npm test -- --run 2>/dev/null || warn "testes falharam ou não existem — confira antes de commitar"

if $RODAR_BUILD; then
  log "build de produção"
  npm run build
fi

cat <<'FIM'

──────────────────────────────────────────────────────────────────────
Rebrand aplicado. O que ainda é decisão humana:

1. SVG oficial — components/LocufyLogo.tsx traz uma reconstrução do símbolo.
   Substitua pelo vetor exportado do manual assim que tiver o arquivo.

2. Ícones PWA — hoje são a letra "L" sobre o gradiente roxo→ciano, geradas em
   tempo de build. Se quiser o símbolo do microfone, exporte PNGs de 192 e 512
   para public/ e aponte o manifest para eles.

3. Fontes — Sama Latin e Gotham Rounded são licenciadas e não estão no Google
   Fonts. Coloque os .woff2 em app/fonts/ com estes nomes e rode o script de
   novo (ele troca para next/font/local sozinho):
     SamaLatin-Regular.woff2      GothamRounded-Book.woff2
     SamaLatin-Bold.woff2         GothamRounded-Medium.woff2
                                  GothamRounded-Bold.woff2

4. Sidebar — a régua de dial FM ("88 90 92 ... Locufy ... 108") era a metáfora
   de rádio da ONDA. Com "Locufy" no lugar de "ONDA" o tick fica mais largo e a
   metáfora muda de sentido. Vale trocar por uma barra de ondas ou remover.

5. Contraste — roxo puro (#631BF6) só aparece em preenchimento; texto, ícone e
   borda usam --color-roxo-claro, que clareia no tema escuro. Se algum lugar
   ficou apagado, é esse par de tokens que se ajusta, não o hex da marca.

Para desfazer tudo:  git checkout . && git checkout - && git branch -D rebrand/locufy
──────────────────────────────────────────────────────────────────────
FIM
</content>
