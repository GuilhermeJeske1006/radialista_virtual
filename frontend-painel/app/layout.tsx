import type { Metadata } from "next";
import { Outfit } from "next/font/google";
import "./globals.css";

const outfit = Outfit({ subsets: ["latin"], variable: "--font-outfit" });

export const metadata: Metadata = {
  title: "Radialista Virtual — Painel",
  description: "Painel de configuração do locutor virtual",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className={outfit.variable}>
      <body className="font-sans bg-gray-50 text-gray-800">{children}</body>
    </html>
  );
}
