import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Locufy — Painel do Radialista Virtual",
    short_name: "Locufy",
    description: "Transforme audiência em conexão. Painel do radialista virtual.",
    // id fixo = identidade do app instalado. Sem ele o id seria o start_url, e trocar o start_url
    // pro ao vivo (abaixo) transformaria as instalacoes existentes num "outro app".
    id: "/",
    // app instalado abre direto no ao vivo: e' ali que o autoplay liberado da PWA importa
    // (painel aberto sozinho ao ligar o computador, ver components/live/InstalarAppAviso.tsx).
    start_url: "/live",
    display: "standalone",
    background_color: "#131C2E",
    theme_color: "#131C2E",
    lang: "pt-BR",
    shortcuts: [
      { name: "Ao vivo", url: "/live" },
      { name: "Painel", url: "/dashboard" },
    ],
    icons: [
      { src: "/pwa-icon-192", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/pwa-icon-512", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/pwa-icon-512-maskable", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
