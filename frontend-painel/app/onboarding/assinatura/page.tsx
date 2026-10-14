"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AtivarAssinatura from "../../../components/AtivarAssinatura";
import EtapasCadastro from "../../../components/EtapasCadastro";
import { LocufyLogo, LocufySpin } from "../../../components/LocufyLogo";
import ThemeToggle from "../../../components/ThemeToggle";
import { apiFetch } from "../../../lib/api";
import { assinaturaObrigatoria, precisaAssinar } from "../../../lib/assinatura";
import { limparContaCache, obterConta, recarregarConta, useConta } from "../../../lib/useConta";

// dadosIncompletos: o cadastro criou a conta, mas não salvou o nome da rádio (?dados=incompletos).
type Retorno = { confirmando: boolean; erro: string; dadosIncompletos: boolean };

// Passo 3 do cadastro e passo 1 do onboarding (lib/tour.ts). O cadastro termina aqui; conta que
// parou antes de pagar cai aqui vinda de qualquer página do painel (AppShell) até ativar o
// Locufy Flex; cancelada vem pelo tour.
// Fora do AppShell de propósito: sem menu, a única saída é assinar ou sair da conta.
export default function OnboardingAssinaturaPage() {
  const router = useRouter();
  const conta = useConta();
  const [retorno, setRetorno] = useState<Retorno | null>(null);
  const [erroConta, setErroConta] = useState(false);

  // Fora do AppShell, ninguém mais avisa se /auth/me falhar -- sem isso, "Carregando…" para sempre.
  useEffect(() => {
    obterConta().catch(() => setErroConta(true));
  }, []);

  function tentarDeNovo() {
    setErroConta(false);
    recarregarConta().catch(() => setErroConta(true));
  }

  // Volta do banco (3DS com redirecionamento): o Stripe acrescenta redirect_status na URL. Lê uma
  // vez só -- a URL é limpa logo depois, e uma segunda execução do efeito (StrictMode) não pode
  // apagar o retorno já lido.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const status = params.get("redirect_status");
    setRetorno((anterior) => anterior ?? {
      confirmando: status === "succeeded" || status === "processing",
      erro: status === "failed" ? "O banco não aprovou o pagamento. Tente de novo ou use outro cartão." : "",
      dadosIncompletos: params.get("dados") === "incompletos",
    });
    if (window.location.search) window.history.replaceState(null, "", window.location.pathname);
  }, []);

  // Um destino só: a conta recarregada ao confirmar o pagamento também dispara o efeito abaixo.
  const destino = retorno?.dadosIncompletos ? "/dashboard?onboarding=incompleto" : "/onboarding";
  const jaAssinada = conta !== null && !precisaAssinar(conta);
  useEffect(() => {
    if (jaAssinada && retorno) router.replace(destino);
  }, [jaAssinada, retorno, destino, router]);

  function sair() {
    apiFetch("/auth/logout", { method: "POST" }).catch(() => {});
    limparContaCache();
    router.push("/login");
  }

  const cadastro = assinaturaObrigatoria(conta);
  const admin = conta?.role === "admin";

  let conteudo: React.ReactNode;
  if (!conta && erroConta) {
    conteudo = (
      <div role="alert">
        <p className="text-sm text-fg/80">Não foi possível carregar sua conta. Confira a conexão e tente de novo.</p>
        <button
          type="button"
          onClick={tentarDeNovo}
          className="mt-4 rounded-xl bg-brand-500 px-4 py-2.5 text-sm font-medium text-on-brand hover:bg-brand-600"
        >
          Tentar de novo
        </button>
      </div>
    );
  } else if (!conta || !retorno || jaAssinada) {
    conteudo = (
      <p className="flex items-center gap-2 text-sm text-fg/65">
        <LocufySpin size={16} /> Carregando…
      </p>
    );
  } else if (!admin) {
    conteudo = (
      <>
        <h1 className="font-display text-xl font-bold text-fg mb-2">Assinatura pendente</h1>
        <p className="text-sm text-fg/80">
          A assinatura do Locufy Flex desta rádio {cadastro ? "ainda não foi ativada" : "foi cancelada"}. Peça a quem
          administra a conta para entrar e concluir o pagamento.
        </p>
      </>
    );
  } else {
    conteudo = (
      <>
        {cadastro && <EtapasCadastro atual={3} />}
        <h1 className="font-display text-xl font-bold text-fg mb-2">
          {cadastro ? "Ative o Locufy Flex" : "Reative o Locufy Flex"}
        </h1>
        <p className="text-sm text-fg/65 mb-6">
          {cadastro
            ? "Última etapa do cadastro. Com a assinatura ativa, você já cria o radialista com IA e coloca a rádio no ar."
            : "Sua assinatura foi cancelada. Reative para voltar a gerar com IA e colocar a rádio no ar."}
        </p>
        {retorno.dadosIncompletos && (
          <p role="status" className="mb-5 max-w-lg rounded-xl border border-acento-claro/40 bg-acento/10 px-4 py-3 text-sm text-fg/80">
            Sua conta foi criada, mas o nome da rádio pode não ter sido salvo. Você confere em Configurações depois de
            assinar.
          </p>
        )}
        {retorno.erro && <p role="alert" className="mb-4 text-sm text-laranja">{retorno.erro}</p>}
        <div className="max-w-lg">
          <AtivarAssinatura
            confirmando={retorno.confirmando}
            rotuloBotao={cadastro ? "Assinar e continuar" : "Reativar assinatura"}
            onAtivada={() => router.replace(destino)}
          />
        </div>
      </>
    );
  }

  return (
    <main className="min-h-screen bg-bg flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-2xl">
        <div className="flex items-center justify-center gap-3 mb-6">
          <LocufyLogo wordmarkClassName="text-2xl" />
          <ThemeToggle />
        </div>
        <div className="bg-surface rounded-3xl border border-border-strong shadow-theme-sm p-5 sm:p-8">{conteudo}</div>
        <p className="mt-6 text-center text-sm text-fg/65">
          {conta && !cadastro && (
            <>
              <Link href="/dashboard" className="text-acento-claro underline">
                Voltar ao painel
              </Link>
              {" · "}
            </>
          )}
          <button type="button" onClick={sair} className="text-acento-claro underline">
            Sair da conta
          </button>
        </p>
        <p className="mt-3 text-center text-xs text-fg/65">
          Ao assinar, você concorda com os{" "}
          <Link href="/termos" className="underline">
            Termos de Uso
          </Link>{" "}
          e a{" "}
          <Link href="/privacidade" className="underline">
            Política de Privacidade
          </Link>
          .
        </p>
      </div>
    </main>
  );
}
