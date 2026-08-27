import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Locufy — Painel do Radialista Virtual",
    short_name: "Locufy",
    description: "Painel de configuração do radialista virtual",
    start_url: "/",
    display: "standalone",
    background_color: "#15130f",
    theme_color: "#15130f",
    lang: "pt-BR",
    icons: [
      {
        src: "/pwa-icon-192",
        sizes: "192x192",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/pwa-icon-512",
        sizes: "512x512",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/pwa-icon-512-maskable",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  };
}
