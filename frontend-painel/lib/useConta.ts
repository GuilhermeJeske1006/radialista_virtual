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
    buscaEmVoo = apiFetch<Conta>("/auth/me").then(
      (conta) => {
        contaCache = conta;
        assinantes.forEach((avisar) => avisar(conta));
        return conta;
      },
      (erro) => {
        // sem isso, toda tela montada depois herdaria a mesma falha até um reload
        buscaEmVoo = null;
        throw erro;
      },
    );
  }
  return buscaEmVoo;
}

export function limparContaCache(): void {
  contaCache = null;
  buscaEmVoo = null;
}

/** Conta já carregada (cache) ou a busca em andamento -- pra quem precisa saber se falhou. */
export function obterConta(): Promise<Conta> {
  return contaCache ? Promise.resolve(contaCache) : buscarConta();
}

/** Busca a conta de novo e avisa quem está montado -- depois do checkout o status muda. */
export function recarregarConta(): Promise<Conta> {
  buscaEmVoo = null;
  return buscarConta();
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
