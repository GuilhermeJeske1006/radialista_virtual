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
