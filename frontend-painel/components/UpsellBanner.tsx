"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "../lib/api";
export function UpsellBanner() {
  const [aviso, setAviso] = useState<string | null>(null);
  useEffect(() => { apiFetch<{aviso:string|null}>("/billing/consumo-ia").then(r => setAviso(r.aviso)).catch(() => {}); }, []);
  if (!aviso) return null;
  return <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-3xl border border-laranja/40 bg-laranja/10 p-5"><p>{aviso === "esgotado" ? "O limite financeiro foi atingido. Novas gerações estão pausadas." : "Seu consumo está próximo do limite financeiro."}</p><Link className="text-ciano underline" href="/billing">Conferir consumo e limite</Link></div>;
}
