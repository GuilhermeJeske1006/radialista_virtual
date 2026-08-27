"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { apiFetch, ApiError } from "../../lib/api";
import { LocufyLogo, LocufySpin } from "../../components/LocufyLogo";
import ThemeToggle from "../../components/ThemeToggle";

function AceitarConviteForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") || "";

  const [nome, setNome] = useState("");
  const [senha, setSenha] = useState("");
  const [confirmarSenha, setConfirmarSenha] = useState("");
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(false);

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    setErro("");
    if (!nome.trim()) {
      setErro("Preencha seu nome");
      return;
    }
    if (senha.length < 8) {
      setErro("A senha precisa ter pelo menos 8 caracteres");
      return;
    }
    if (senha !== confirmarSenha) {
      setErro("As senhas não conferem");
      return;
    }
    setCarregando(true);
    try {
      // sessao ja vem via cookie httpOnly no Set-Cookie da resposta -- nada pra guardar aqui.
      await apiFetch("/convites/aceitar", {
        method: "POST",
        body: JSON.stringify({ token, nome: nome.trim(), senha }),
      });
      router.push("/dashboard");
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao aceitar convite");
    } finally {
      setCarregando(false);
    }
  }

  if (!token) {
    return (
      <p className="text-sm text-rust-text">
        Link inválido. Peça um novo convite pra quem administra sua rádio.
      </p>
    );
  }

  return (
    <form onSubmit={enviar} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-fg/80 mb-1.5">Seu nome</label>
        <input
          type="text"
          required
          value={nome}
          onChange={(e) => setNome(e.target.value)}
          className="w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-fg/80 mb-1.5">Senha</label>
        <input
          type="password"
          required
          minLength={8}
          value={senha}
          onChange={(e) => setSenha(e.target.value)}
          className="w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-fg/80 mb-1.5">Confirmar senha</label>
        <input
          type="password"
          required
          minLength={8}
          value={confirmarSenha}
          onChange={(e) => setConfirmarSenha(e.target.value)}
          className="w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
        />
      </div>
      {erro && <p className="text-sm text-rust-text">{erro}</p>}
      <button
        type="submit"
        disabled={carregando}
        className="w-full flex items-center justify-center gap-2 rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-ink hover:bg-brand-600 disabled:opacity-60 disabled:cursor-not-allowed"
      >
        {carregando ? (
          <>
            <LocufySpin size={14} /> Entrando...
          </>
        ) : (
          "Entrar na equipe"
        )}
      </button>
    </form>
  );
}

export default function ConvitePage() {
  return (
    <div className="min-h-screen bg-bg flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="flex items-center justify-center gap-3 mb-6">
          <LocufyLogo wordmarkClassName="text-2xl" />
          <ThemeToggle className="ml-1" />
        </div>
        <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-sm p-6">
          <h1 className="font-display text-lg font-bold text-fg mb-1">Você foi convidado</h1>
          <p className="text-sm text-fg/65 mb-6">Crie sua senha para entrar na equipe.</p>
          <Suspense fallback={<LocufySpin size={16} />}>
            <AceitarConviteForm />
          </Suspense>
        </div>
        <p className="mt-4 text-sm text-fg/65 text-center">
          Já tem conta?{" "}
          <Link href="/login" className="text-amber-text hover:text-amber-dim font-medium">
            Entrar
          </Link>
        </p>
      </div>
    </div>
  );
}
