"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiFetch, ApiError } from "../../lib/api";
import { getEmailLembrado, limparEmailLembrado, setEmailLembrado, setToken } from "../../lib/auth";
import { OndaLogo } from "../../components/OndaLogo";
import ThemeToggle from "../../components/ThemeToggle";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [lembrar, setLembrar] = useState(false);
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(false);

  useEffect(() => {
    const emailLembrado = getEmailLembrado();
    if (emailLembrado) {
      setEmail(emailLembrado);
      setLembrar(true);
    }
  }, []);

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    setErro("");
    setCarregando(true);
    try {
      const dados = await apiFetch<{ access_token: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, senha }),
      });
      setToken(dados.access_token);
      if (lembrar) {
        setEmailLembrado(email);
      } else {
        limparEmailLembrado();
      }
      router.push("/dashboard");
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao entrar");
    } finally {
      setCarregando(false);
    }
  }

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="flex items-center justify-center gap-3 mb-6">
          <OndaLogo size={34} wordmarkClassName="text-2xl" />
          <ThemeToggle className="ml-1" />
        </div>
        <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-sm p-6">
          <h1 className="font-display text-lg font-bold text-fg mb-6">Entrar</h1>
          <form onSubmit={enviar} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-fg/80 mb-1.5">E-mail</label>
              <input
                type="email"
                required
                placeholder="Ex.: email@dominio.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-fg/80 mb-1.5">Senha</label>
              <input
                type="password"
                placeholder="Mínimo de 8 caracteres"
                minLength={8}
                required
                value={senha}
                onChange={(e) => setSenha(e.target.value)}
                className="w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
              />
            </div>
            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 text-sm text-fg/70">
                <input
                  type="checkbox"
                  checked={lembrar}
                  onChange={(e) => setLembrar(e.target.checked)}
                  className="h-4 w-4 rounded border-border-strong accent-amber"
                />
                Lembrar senha
              </label>
              <Link href="/esqueci-senha" className="text-sm text-amber hover:text-amber-dim font-medium">
                Esqueci minha senha
              </Link>
            </div>
            {erro && <p className="text-sm text-rust">{erro}</p>}
            <button
              type="submit"
              disabled={carregando}
              className="w-full rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-ink hover:bg-brand-600 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {carregando ? "Entrando..." : "Entrar"}
            </button>
          </form>
          <p className="mt-4 text-sm text-fg/55">
            Não tem conta?{" "}
            <Link href="/register" className="text-amber hover:text-amber-dim font-medium">
              Criar conta
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
