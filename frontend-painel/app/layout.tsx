import type { Metadata } from "next";
import { Bricolage_Grotesque, IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";
import "./globals.css";

const bricolage = Bricolage_Grotesque({
  subsets: ["latin"],
  variable: "--font-bricolage",
});

const plexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-sans",
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-mono",
});

export const metadata: Metadata = {
  title: "ONDA — Painel",
  description: "Painel de configuração do radialista virtual",
};

const TEMA_INICIAL_SCRIPT = `(function(){try{var t=localStorage.getItem("onda-theme");if(t==="light")document.documentElement.setAttribute("data-theme","light");}catch(e){}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="pt-BR"
      data-theme="dark"
      suppressHydrationWarning
      className={`${bricolage.variable} ${plexSans.variable} ${plexMono.variable}`}
    >
      <body className="font-sans bg-bg text-fg antialiased">
        <script dangerouslySetInnerHTML={{ __html: TEMA_INICIAL_SCRIPT }} />
        {children}
      </body>
    </html>
  );
}
