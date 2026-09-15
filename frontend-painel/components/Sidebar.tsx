"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { apiFetch } from "../lib/api";
import { limparContaCache, useConta } from "../lib/useConta";
import { useConfiguracaoInicialCompleta } from "../lib/useConfiguracaoInicial";
import { LocufyMark } from "./LocufyLogo";
import { ICONE_SAIR, LINK_AJUDA, LINK_PERFIL, NAV_LINKS, NavGroup, NavIcone } from "./nav";

const ORDEM_GRUPOS: NavGroup[] = ["Principal", "Conteúdo", "Conta"];

function ContaMenu({ colapsada }: { colapsada: boolean }) {
  const pathname = usePathname();
  const router = useRouter();
  const conta = useConta();
  const [aberto, setAberto] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const botaoRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    function aoClicarFora(evento: MouseEvent) {
      if (ref.current && !ref.current.contains(evento.target as Node)) setAberto(false);
    }
    document.addEventListener("mousedown", aoClicarFora);
    return () => document.removeEventListener("mousedown", aoClicarFora);
  }, []);

  useEffect(() => {
    setAberto(false);
  }, [pathname]);

  function sair() {
    apiFetch("/auth/logout", { method: "POST" }).catch(() => {});
    limparContaCache();
    router.push("/login");
  }

  const inicial = (conta?.nome || conta?.email || "?").charAt(0).toUpperCase();
  const itemClasses =
    "flex items-center gap-3 rounded-full px-3.5 py-2 text-sm font-semibold text-fg/65 hover:bg-fg/5 hover:text-fg transition-colors";

  return (
    <div
      ref={ref}
      className="relative"
      onKeyDown={(event) => {
        if (event.key === "Escape" && aberto) {
          setAberto(false);
          botaoRef.current?.focus();
        }
      }}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setAberto(false);
      }}
    >
      {aberto && (
        <div
          className={`absolute bottom-full mb-2 rounded-2xl border border-border-strong bg-surface shadow-theme-sm py-1.5 ${
            colapsada ? "left-0 w-52" : "left-0 right-0"
          }`}
        >
          {(conta?.nome || conta?.email) && (
            <div className="px-3.5 py-2 mb-1 border-b border-border">
              {conta?.nome && <div className="text-sm font-semibold text-fg truncate">{conta.nome}</div>}
              {conta?.email && <div className="text-xs text-fg/55 truncate">{conta.email}</div>}
            </div>
          )}
          <div className="px-1.5 space-y-0.5">
            <Link href={LINK_AJUDA.href} className={itemClasses}>
              <NavIcone>{LINK_AJUDA.icon}</NavIcone>
              {LINK_AJUDA.label}
            </Link>
            <Link href={LINK_PERFIL.href} className={itemClasses}>
              <NavIcone>{LINK_PERFIL.icon}</NavIcone>
              {LINK_PERFIL.label}
            </Link>
            <button onClick={sair} className={`w-full ${itemClasses}`}>
              <NavIcone>{ICONE_SAIR}</NavIcone>
              Sair
            </button>
          </div>
        </div>
      )}
      <button
        ref={botaoRef}
        type="button"
        aria-label="Menu da conta"
        aria-expanded={aberto}
        onClick={() => setAberto((v) => !v)}
        title={colapsada ? conta?.nome || "Conta" : undefined}
        className={`flex w-full items-center gap-3 rounded-full px-3.5 py-2.5 text-sm font-semibold text-fg/65 hover:bg-fg/5 hover:text-fg transition-colors ${
          colapsada ? "justify-center" : ""
        }`}
      >
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-acento/15 text-acento-claro text-xs font-bold">
          {inicial}
        </span>
        {!colapsada && <span className="truncate">{conta?.nome || conta?.email || "Conta"}</span>}
      </button>
    </div>
  );
}

// tela Ao Vivo precisa do máximo de largura pra grade de colunas -- sidebar
// vira uma trilha só de ícones nessa rota (sem toggle manual, só auto por rota).
export default function Sidebar() {
  const pathname = usePathname();
  const conta = useConta();
  const colapsada = pathname === "/live";
  const setupCompleto = useConfiguracaoInicialCompleta();
  const links = NAV_LINKS.filter((link) => !link.adminOnly || conta?.role === "admin").map((link) =>
    link.numeroSetup && !setupCompleto ? { ...link, label: `${link.numeroSetup}. ${link.label}` } : link
  );
  const grupos = ORDEM_GRUPOS.map((grupo) => ({
    grupo,
    links: links.filter((link) => link.group === grupo),
  })).filter((g) => g.links.length > 0);

  // Pílula: o item ativo repete a forma da cápsula do símbolo, cheia; os
  // demais ficam só com o texto, sem caixa, para o ativo ser o único bloco
  // sólido da coluna.
  function classes(ativo: boolean) {
    return `flex items-center gap-3 rounded-full px-4 py-2.5 text-sm font-semibold transition-colors ${
      colapsada ? "justify-center px-0 w-11 h-11 mx-auto" : ""
    } ${
      ativo
        ? "bg-acento text-on-brand shadow-[0_8px_24px_-10px_var(--color-acento)]"
        : "text-fg/65 hover:bg-fg/5 hover:text-fg"
    }`;
  }

  return (
    <aside
      className={`hidden md:flex md:flex-col md:fixed md:inset-y-0 z-20 bg-surface border-r border-border transition-[width] duration-150 ${
        colapsada ? "md:w-20" : "md:w-72.5"
      }`}
    >
      <div className="flex flex-col flex-1 min-h-0">
        {/* Lockup oficial, sem faixa de cor por trás — só troca de arte (branca
            no tema escuro, grafite no claro) pra continuar legível nos dois. */}
        <div
          className={`flex items-center justify-center border-b border-border shrink-0 ${
            colapsada ? "py-6" : "px-3"
          }`}
        >
          {colapsada ? (
            <LocufyMark size={32} className="shrink-0 text-acento-claro" />
          ) : (
            <>
              <img
                src="/Logos/Logo_Locufy_Logotipo_Horizontal_01.png"
                alt="Locufy"
                className="locufy-so-escuro mx-auto w-full max-w-44 h-auto object-contain object-center"
                style={{ maxWidth: '53%' }}
              />
              <img
                src="/Logos/Logo_Locufy_Logotipo_Horizontal_02.png"
                alt="Locufy"
                style={{ maxWidth: '53%' }}
                className="locufy-so-claro mx-auto w-full max-w-44 h-auto object-contain object-center"
              />
            </>
          )}
        </div>

        <nav className={`flex-1 overflow-y-auto py-5 space-y-5 ${colapsada ? "px-3" : "px-4"}`}>
          {grupos.map(({ grupo, links: linksDoGrupo }) => (
            <div key={grupo}>
              {!colapsada && (
                <div className="px-4 mb-2 text-xs font-semibold uppercase tracking-wide text-fg/45">{grupo}</div>
              )}
              <div className="space-y-1">
                {linksDoGrupo.map((link) => (
                  <Link
                    key={link.href}
                    href={link.href}
                    title={colapsada ? link.label : undefined}
                    aria-label={colapsada ? link.label : undefined}
                    className={classes(pathname === link.href)}
                  >
                    <NavIcone>{link.icon}</NavIcone>
                    {!colapsada && link.label}
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </nav>

        <div className={`pb-3 pt-2 border-t border-border ${colapsada ? "px-3" : "px-4"}`}>
          <ContaMenu colapsada={colapsada} />
        </div>
      </div>
    </aside>
  );
}
