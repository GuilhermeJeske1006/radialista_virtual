"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useConfiguracaoInicial } from "../lib/useConfiguracaoInicial";
import { paginaDoPasso, passoAtual, PASSOS_TOUR } from "../lib/tour";
import { useAppConfigurado, useInstalarApp } from "../lib/instalarApp";

const CHAVE_COLAPSADO = "locufy_tour_colapsado";

export default function OnboardingTour() {
  const pathname = usePathname();
  const configuracao = useConfiguracaoInicial();
  const appPronto = useAppConfigurado();
  const estado = { ...configuracao, appPronto };
  // passo do app: instala direto daqui, sem passar pela pagina do passo -- o cliente so' clica
  // "Instalar" (+ confirmacao do navegador) e o app abre sozinho no ao vivo.
  const { podeInstalar, instalar } = useInstalarApp();
  const [colapsado, setColapsado] = useState(true);

  // le' preferencia so' no cliente -- evita mismatch de hidratacao (localStorage nao existe no SSR).
  // Sem preferência salva: aberto no desktop, recolhido no celular (o cartão cobre metade da tela).
  useEffect(() => {
    let salvo: string | null = null;
    try {
      salvo = localStorage.getItem(CHAVE_COLAPSADO);
    } catch {
      // localStorage bloqueado (aba anonima, etc.) -- decide pelo tamanho da tela
    }
    const telaPequena = typeof window.matchMedia === "function" && window.matchMedia("(max-width: 767px)").matches;
    setColapsado(salvo === null ? telaPequena : salvo === "1");
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
  if (!passo || pathname === paginaDoPasso(passo)) return null;

  const restantes = PASSOS_TOUR.length - PASSOS_TOUR.filter((p) => p.feito(estado)).length;

  if (colapsado) {
    return (
      <button
        type="button"
        onClick={() => alternarColapsado(false)}
        className="fixed bottom-20 right-5 z-40 flex items-center gap-2 rounded-full bg-acento px-4 py-2.5 text-sm font-medium text-on-brand shadow-lg hover:bg-acento/90"
      >
        Configuração inicial: {restantes} {restantes === 1 ? "passo" : "passos"}
      </button>
    );
  }

  return (
    <div className="fixed bottom-20 right-5 z-40 w-80 max-w-[calc(100vw-2.5rem)] rounded-3xl border border-border-strong bg-surface shadow-lg p-5">
      <div className="flex items-start justify-between gap-2 mb-2">
        <span className="text-xs font-medium uppercase tracking-wide text-acento-claro">
          Passo {passo.numero} de {PASSOS_TOUR.length}
        </span>
        <button
          type="button"
          onClick={() => alternarColapsado(true)}
          aria-label="Minimizar guia de configuração"
          className="-m-2 flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-fg/65 hover:bg-fg/5 hover:text-fg"
        >
          ✕
        </button>
      </div>
      <h3 className="font-display text-sm font-bold text-fg mb-1">{passo.titulo}</h3>
      <p className="text-sm text-fg/65 mb-4">{passo.texto}</p>
      {passo.href === "/onboarding/app" && podeInstalar ? (
        <>
          <button
            type="button"
            onClick={() => { void instalar(); }}
            className="block w-full text-center rounded-xl bg-brand-500 px-4 py-2.5 text-sm font-medium text-on-brand hover:bg-brand-600"
          >
            Instalar Locufy
          </button>
          <Link href={passo.href} className="mt-2 block text-center text-xs text-fg/65 hover:text-fg">
            Como funciona
          </Link>
        </>
      ) : (
        <Link
          href={passo.href}
          className="block text-center rounded-xl bg-brand-500 px-4 py-2.5 text-sm font-medium text-on-brand hover:bg-brand-600"
        >
          {passo.cta} →
        </Link>
      )}
    </div>
  );
}
