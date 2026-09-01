"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useConfiguracaoInicial } from "../lib/useConfiguracaoInicial";
import { passoAtual, PASSOS_TOUR } from "../lib/tour";

const CHAVE_COLAPSADO = "locufy_tour_colapsado";

export default function OnboardingTour() {
  const pathname = usePathname();
  const estado = useConfiguracaoInicial();
  const [colapsado, setColapsado] = useState(true);

  // le' preferencia so' no cliente -- evita mismatch de hidratacao (localStorage nao existe no SSR).
  useEffect(() => {
    try {
      setColapsado(localStorage.getItem(CHAVE_COLAPSADO) === "1");
    } catch {
      // localStorage bloqueado (aba anonima, etc.) -- mantem aberto por padrao
    }
  }, []);

  function alternarColapsado(valor: boolean) {
    setColapsado(valor);
    try {
      localStorage.setItem(CHAVE_COLAPSADO, valor ? "1" : "0");
    } catch {
      // sem storage disponivel, so' nao persiste entre sessoes
    }
  }

  const passo = passoAtual(estado);

  // sem passo pendente (setup completo), sem dado carregado ainda, ou usuario ja' esta' na
  // pagina certa pra esse passo -- a propria pagina explica o que fazer, o card so' atrapalharia.
  if (!passo || pathname === passo.href) return null;

  const restantes = PASSOS_TOUR.length - PASSOS_TOUR.filter((p) => p.feito(estado)).length;

  if (colapsado) {
    return (
      <button
        type="button"
        onClick={() => alternarColapsado(false)}
        className="fixed bottom-5 right-5 z-40 flex items-center gap-2 rounded-full bg-amber px-4 py-2.5 text-sm font-medium text-ink shadow-lg hover:bg-amber/90"
      >
        Configuração pendente ({restantes})
      </button>
    );
  }

  return (
    <div className="fixed bottom-5 right-5 z-40 w-80 max-w-[calc(100vw-2.5rem)] rounded-2xl border border-border-strong bg-surface shadow-lg p-5">
      <div className="flex items-start justify-between gap-2 mb-2">
        <span className="text-xs font-medium uppercase tracking-wide text-amber-text">
          Passo {passo.numero} de {PASSOS_TOUR.length}
        </span>
        <button
          type="button"
          onClick={() => alternarColapsado(true)}
          aria-label="Minimizar guia de configuração"
          className="shrink-0 text-fg/50 hover:text-fg"
        >
          ✕
        </button>
      </div>
      <h3 className="font-display text-sm font-bold text-fg mb-1">{passo.titulo}</h3>
      <p className="text-sm text-fg/65 mb-4">{passo.texto}</p>
      <Link
        href={passo.href}
        className="block text-center rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-ink hover:bg-brand-600"
      >
        {passo.cta} →
      </Link>
    </div>
  );
}
