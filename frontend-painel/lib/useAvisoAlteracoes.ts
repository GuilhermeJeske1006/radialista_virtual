"use client";

import { useEffect } from "react";

export const MENSAGEM_ALTERACOES = "Há alterações não salvas. Sair desta página e descartar?";

/** Enquanto houver alteração não salva, pede confirmação antes de sair: fechar/recarregar a aba
 * (beforeunload) e clicar em link interno do painel (o router do Next não dispara beforeunload). */
export function useAvisoAlteracoes(pendente: boolean): void {
  useEffect(() => {
    if (!pendente) return;

    function antesDeSair(evento: BeforeUnloadEvent) {
      evento.preventDefault();
      evento.returnValue = "";
    }

    function aoClicar(evento: MouseEvent) {
      if (evento.defaultPrevented || evento.button !== 0 || evento.metaKey || evento.ctrlKey || evento.shiftKey) return;
      const link = (evento.target as Element | null)?.closest?.("a[href]") as HTMLAnchorElement | null;
      if (!link || link.target === "_blank" || link.origin !== window.location.origin) return;
      if (link.pathname === window.location.pathname && link.hash) return;
      if (!window.confirm(MENSAGEM_ALTERACOES)) {
        evento.preventDefault();
        evento.stopPropagation();
      }
    }

    window.addEventListener("beforeunload", antesDeSair);
    document.addEventListener("click", aoClicar, true);
    return () => {
      window.removeEventListener("beforeunload", antesDeSair);
      document.removeEventListener("click", aoClicar, true);
    };
  }, [pendente]);
}
