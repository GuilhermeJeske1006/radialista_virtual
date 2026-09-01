"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "./api";
import { SuperAdminConta } from "./types";

// Mesmo padrao de cache de modulo de useConta.ts. O 401 do apiFetch ja redireciona
// sozinho pro /login (unico, ver app/login/page.tsx) -- esse hook e' o proprio guard de
// acesso das paginas /admin/*, sem precisar de um useEffect extra checando flag nenhuma.
let cache: SuperAdminConta | null = null;
let buscaEmVoo: Promise<SuperAdminConta> | null = null;
const assinantes = new Set<(admin: SuperAdminConta) => void>();

function buscarSuperAdmin(): Promise<SuperAdminConta> {
  if (!buscaEmVoo) {
    buscaEmVoo = apiFetch<SuperAdminConta>("/admin/auth/me").then((admin) => {
      cache = admin;
      assinantes.forEach((avisar) => avisar(admin));
      return admin;
    });
  }
  return buscaEmVoo;
}

export function limparSuperAdminCache(): void {
  cache = null;
  buscaEmVoo = null;
}

export function useSuperAdmin(): SuperAdminConta | null {
  const [admin, setAdmin] = useState<SuperAdminConta | null>(cache);

  useEffect(() => {
    assinantes.add(setAdmin);
    if (!cache) {
      buscarSuperAdmin().catch(() => {
        // sem sessao de admin / erro de rede -- apiFetch ja redireciona pro /login em 401
      });
    }
    return () => {
      assinantes.delete(setAdmin);
    };
  }, []);

  return admin;
}
