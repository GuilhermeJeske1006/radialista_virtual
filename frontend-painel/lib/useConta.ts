"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "./api";
import { Conta } from "./types";

// Cache de modulo (nao por componente) -- Sidebar e AppShell montam juntos e os
// dois usam esse hook, sem isso duplicaria o fetch de /auth/me a cada navegacao.
let contaCache: Conta | null = null;
let buscaEmVoo: Promise<Conta> | null = null;
const assinantes = new Set<(conta: Conta) => void>();

function buscarConta(): Promise<Conta> {
  if (!buscaEmVoo) {
    buscaEmVoo = apiFetch<Conta>("/auth/me").then((conta) => {
      contaCache = conta;
      assinantes.forEach((avisar) => avisar(conta));
      return conta;
    });
  }
  return buscaEmVoo;
}

export function limparContaCache(): void {
  contaCache = null;
  buscaEmVoo = null;
}

export function useConta(): Conta | null {
  const [conta, setConta] = useState<Conta | null>(contaCache);

  useEffect(() => {
    assinantes.add(setConta);
    if (!contaCache) {
      buscarConta().catch(() => {
        // sem conta logada / erro de rede -- apiFetch ja redireciona pro /login em 401
      });
    }
    return () => {
      assinantes.delete(setConta);
    };
  }, []);

  return conta;
}
