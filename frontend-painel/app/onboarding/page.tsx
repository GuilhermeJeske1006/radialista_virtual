"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { LocufySpin } from "../../components/LocufyLogo";
import { appConfigurado } from "../../lib/instalarApp";
import { passoAtual } from "../../lib/tour";
import { obterConfiguracaoInicial } from "../../lib/useConfiguracaoInicial";

// "Continuar →" dos passos do onboarding (ex.: app/onboarding/locutor) cai aqui: manda pro
// proximo passo pendente do tour (lib/tour.ts) ou, com tudo pronto, pro painel.
export default function OnboardingPage() {
  const router = useRouter();

  useEffect(() => {
    let ativo = true;
    obterConfiguracaoInicial().then((configuracao) => {
      if (!ativo) return;
      const passo = passoAtual({ ...configuracao, appPronto: appConfigurado() });
      router.replace(passo?.href ?? "/dashboard");
    });
    return () => { ativo = false; };
  }, [router]);

  return (
    <p className="flex items-center justify-center gap-2 p-10 text-sm text-fg/65">
      <LocufySpin size={16} /> Carregando...
    </p>
  );
}
