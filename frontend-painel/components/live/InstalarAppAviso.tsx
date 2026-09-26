"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Navegador, useAppConfigurado, useInstalarApp } from "../../lib/instalarApp";

const CHAVE_DISPENSADO = "locufy-instalar-app-dispensado";

// Passo a passo quando o navegador nao oferece o botao de instalar (ja recusou uma vez, Firefox,
// Safari...). Firefox nao instala PWA no desktop: la' o aceite e' a permissao de autoplay do site.
const INSTRUCOES: Record<Navegador, string> = {
  chrome: "Clique no ícone de instalar no fim da barra de endereço (ou menu ⋮ > Transmitir, salvar e compartilhar > Instalar página como app).",
  edge: "Clique no ícone de instalar na barra de endereço (ou menu … > Aplicativos > Instalar este site como um aplicativo).",
  firefox: "O Firefox não instala apps: clique no cadeado da barra de endereço > Reprodução automática > Permitir áudio e vídeo.",
  safari: "No Safari, use Arquivo > Adicionar ao Dock. Se o som ainda travar, use o Chrome ou o Edge.",
  outro: "Instale o painel como app pelo menu do navegador (Chrome ou Edge recomendados).",
};

export default function InstalarAppAviso() {
  const { comoApp, podeInstalar, instalado, navegador, instalar } = useInstalarApp();
  const [dispensado, setDispensado] = useState(true);
  // ja' passou pelo passo do app no onboarding (instalou, liberou o som ou pulou) neste aparelho
  const appPronto = useAppConfigurado();

  useEffect(() => {
    try {
      setDispensado(localStorage.getItem(CHAVE_DISPENSADO) === "1");
    } catch {
      setDispensado(false);
    }
  }, []);

  function dispensar() {
    setDispensado(true);
    try {
      localStorage.setItem(CHAVE_DISPENSADO, "1");
    } catch {
      // sem storage (aba anonima etc.) -- so' esconde nesta visita
    }
  }

  if (comoApp || dispensado || (appPronto && !instalado)) return null;

  if (instalado) {
    return (
      <div className="mb-4 rounded-xl border border-ciano bg-ciano/10 px-4 py-3" role="status">
        <p className="text-sm font-medium text-ciano">
          Locufy instalado. Abra o ao vivo pelo ícone do app: a voz e a música saem sozinhas, sem precisar clicar.
          Pra abrir junto com o computador, ative "abrir ao iniciar/fazer login" nas opções do app no navegador.
        </p>
      </div>
    );
  }

  return (
    <div className="mb-4 flex flex-wrap items-center gap-3 rounded-xl border border-ciano bg-ciano/10 px-4 py-3">
      <div className="flex-1 min-w-[14rem]">
        <p className="text-sm font-semibold text-ciano">Deixe a rádio tocar sozinha</p>
        <p className="text-sm text-fg/80">
          Sem o app, o navegador bloqueia o som até alguém clicar na página, e depois de reiniciar o computador ou
          recarregar a página a rádio fica muda. Instalado, o painel toca sozinho.
        </p>
        {!podeInstalar && <p className="mt-1 text-sm text-fg/80">{INSTRUCOES[navegador]}</p>}
        <Link href="/onboarding/app" className="mt-1 inline-block text-sm font-medium text-ciano underline">
          Ver passo a passo e testar o som
        </Link>
      </div>
      <div className="flex items-center gap-2">
        {podeInstalar && (
          <button
            type="button"
            onClick={() => { void instalar(); }}
            className="rounded-full bg-ciano px-4 py-2.5 text-sm font-semibold text-grafite hover:opacity-90 transition-opacity"
          >
            Instalar Locufy
          </button>
        )}
        <button type="button" onClick={dispensar} className="px-3 py-2 text-sm text-fg/65 hover:text-fg">
          Agora não
        </button>
      </div>
    </div>
  );
}
