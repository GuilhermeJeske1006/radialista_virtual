"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AppShell from "../../../components/AppShell";
import { sondarAutoplayComSom } from "../../../lib/autoplay";
import { marcarAppConfigurado, Navegador, useInstalarApp } from "../../../lib/instalarApp";

// Passo 4 do onboarding (lib/tour.ts): o aceite do cliente pra radio tocar sem ninguem clicar.
// Instalar o painel como app (PWA) libera autoplay com som no Chrome/Edge de desktop; no Firefox
// o equivalente e' a permissao de reproducao automatica do site.

type StatusSom = "testando" | "liberado" | "bloqueado" | "inconclusivo";

// So' da pra saber se o navegador libera som SEM clique testando antes de qualquer clique --
// depois de um clique (inclusive o do link que trouxe o usuario ate' aqui) todo navegador libera.
function useStatusSom(): StatusSom {
  const [status, setStatus] = useState<StatusSom>("testando");
  useEffect(() => {
    const ativacao = (navigator as Navigator & { userActivation?: { hasBeenActive: boolean } }).userActivation;
    if (ativacao?.hasBeenActive) {
      setStatus("inconclusivo");
      return;
    }
    let ativo = true;
    sondarAutoplayComSom().then((liberado) => {
      if (ativo) setStatus(liberado ? "liberado" : "bloqueado");
    });
    return () => { ativo = false; };
  }, []);
  return status;
}

const INSTALAR: Record<Navegador, string> = {
  chrome: "Clique no ícone de instalar no fim da barra de endereço, ou no menu ⋮ > Transmitir, salvar e compartilhar > Instalar página como app.",
  edge: "Clique no ícone de instalar na barra de endereço, ou no menu … > Aplicativos > Instalar este site como um aplicativo.",
  firefox: "O Firefox não instala apps. Libere o som do site: clique no cadeado da barra de endereço > Reprodução automática > Permitir áudio e vídeo.",
  safari: "No Safari, use Arquivo > Adicionar ao Dock. Se o som continuar travando, use o Chrome ou o Edge, que são os recomendados.",
  outro: "Use o Chrome ou o Edge e instale o painel como app pelo menu do navegador.",
};

export default function OnboardingAppPage() {
  const router = useRouter();
  const statusSom = useStatusSom();
  const { comoApp, podeInstalar, instalado, navegador, instalar } = useInstalarApp();
  const firefox = navegador === "firefox";

  function concluir(destino: string) {
    marcarAppConfigurado();
    router.push(destino);
  }

  return (
    <AppShell title="Deixe a rádio tocar sozinha" maxWidthClassName="max-w-lg">
      <div className="bg-surface rounded-3xl border border-border-strong shadow-theme-xs p-6">
        <h2 className="font-display text-lg font-bold text-fg mb-1">Som automático, sem ninguém por perto</h2>
        <p className="text-sm text-fg/65 mb-5">
          Por segurança, o navegador bloqueia som de sites até alguém clicar na página, e a rádio fica muda depois de
          reiniciar o computador ou recarregar a página. Instalando o Locufy como app, o som fica liberado e o painel
          toca sozinho.
        </p>

        <div
          role="status"
          className={`rounded-xl border px-4 py-3 mb-6 text-sm ${
            statusSom === "liberado"
              ? "border-ciano bg-ciano/10 text-ciano"
              : statusSom === "bloqueado"
                ? "border-laranja bg-laranja/10 text-laranja"
                : "border-border-strong text-fg/65"
          }`}
        >
          {statusSom === "testando" && "Testando o som automático neste navegador..."}
          {statusSom === "liberado" && "✓ Som automático liberado neste navegador. A rádio toca sem ninguém clicar."}
          {statusSom === "bloqueado" && "Som automático bloqueado neste navegador: sem clique, a voz e a música ficam mudas."}
          {statusSom === "inconclusivo" && (
            <>
              Pra testar o som automático, a página precisa abrir sem nenhum clique.{" "}
              <button type="button" onClick={() => window.location.reload()} className="font-medium text-acento-claro underline">
                Recarregar e testar
              </button>
            </>
          )}
        </div>

        {comoApp && statusSom === "bloqueado" ? (
          <div className="rounded-xl border border-laranja bg-laranja/10 px-4 py-3 mb-6">
            <p className="text-sm font-medium text-laranja">Este atalho não liberou o som.</p>
            <p className="text-sm text-fg/65 mt-0.5">
              Ele foi criado sem o app completo (acontece ao instalar por um endereço que não entrega o manifest, como o
              ngrok gratuito). Remova este atalho ({navegador === "edge" ? "edge://apps" : "chrome://apps"} &gt; botão direito &gt;
              Remover) e instale de novo pelo botão Instalar Locufy, em app.locufybr.com.
            </p>
          </div>
        ) : comoApp ? (
          <div className="mb-6">
            <p className="text-sm font-medium text-fg mb-3">Tudo pronto: você está no app Locufy.</p>
            <Link
              href="/live"
              className="block text-center rounded-xl bg-brand-500 px-4 py-2.5 text-sm font-medium text-on-brand hover:bg-brand-600"
            >
              Ir pro Ao Vivo →
            </Link>
          </div>
        ) : instalado ? (
          <div className="rounded-xl border border-ciano bg-ciano/10 px-4 py-3 mb-6">
            <p className="text-sm font-medium text-ciano">Pronto! O Locufy abriu numa janela própria, já no Ao Vivo.</p>
            <p className="text-sm text-fg/65 mt-0.5">
              Com o programa na grade, ele entra no ar sozinho no horário. Pode fechar esta aba do navegador.
            </p>
          </div>
        ) : podeInstalar ? (
          <div className="mb-6">
            <button
              type="button"
              onClick={() => { void instalar(); }}
              className="w-full rounded-full bg-ciano px-4 py-3 text-base font-semibold text-grafite hover:opacity-90 transition-opacity"
            >
              Instalar Locufy
            </button>
            <p className="mt-2 text-center text-xs text-fg/65">
              O navegador pede pra confirmar. Depois o Locufy abre sozinho, já no Ao Vivo, com o som liberado.
            </p>
          </div>
        ) : (
          <div className="mb-6">
            <p className="text-sm font-medium text-fg mb-1">
              {firefox ? "Libere a reprodução automática" : "Instale o Locufy pelo navegador"}
            </p>
            <p className="text-sm text-fg/65 mb-3">{INSTALAR[navegador]}</p>
            <button
              type="button"
              onClick={() => concluir("/live")}
              className="w-full rounded-xl bg-brand-500 px-4 py-2.5 text-sm font-medium text-on-brand hover:bg-brand-600"
            >
              {firefox ? "Já liberei" : "Já instalei"}
            </button>
          </div>
        )}

        <details className="mb-4 text-sm text-fg/65">
          <summary className="cursor-pointer font-medium text-fg">Abrir junto com o computador (opcional)</summary>
          <div className="mt-2 space-y-2">
            <p>
              <strong className="font-medium text-fg">Mac:</strong> Ajustes do Sistema &gt; Geral &gt; Itens de Início &gt; + e escolha
              {firefox ? " o Firefox" : " o app Locufy (em Aplicativos > Chrome Apps ou Edge Apps)"}.
            </p>
            <p>
              <strong className="font-medium text-fg">Windows:</strong> tecle Win+R, digite <code>shell:startup</code> e copie pra essa
              pasta o atalho {firefox ? "do Firefox" : "do Locufy"} da área de trabalho ou do Menu Iniciar.
            </p>
          </div>
        </details>

        {!comoApp && !instalado && (
          <button type="button" onClick={() => concluir("/dashboard")} className="block w-full text-center text-xs text-fg/65 hover:text-fg">
            Pular por enquanto
          </button>
        )}
      </div>
    </AppShell>
  );
}
