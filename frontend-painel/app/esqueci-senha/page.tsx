"use client";

import { useState } from "react";
import Link from "next/link";
import { apiFetch, ApiError } from "../../lib/api";
import { OndaLogo, OndaSpin } from "../../components/OndaLogo";
import ThemeToggle from "../../components/ThemeToggle";

export default function EsqueciSenhaPage() {
  const [email, setEmail] = useState("");
  const [erro, setErro] = useState("");
  const [enviado, setEnviado] = useState(false);
  const [carregando, setCarregando] = useState(false);

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    setErro("");
    setCarregando(true);
    try {
      await apiFetch("/auth/esqueci-senha", {
        method: "POST",
        body: JSON.stringify({ email }),
      });
      setEnviado(true);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao enviar o e-mail");
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
          <h1 className="font-display text-lg font-bold text-fg mb-1.5">Esqueci minha senha</h1>
          {enviado ? (
            <p className="text-sm text-fg/70 mt-4">
              Se esse e-mail estiver cadastrado, você vai receber um link para redefinir sua senha em instantes.
            </p>
          ) : (
            <>
              <p className="text-sm text-fg/55 mb-6">
                Informe seu e-mail e enviaremos um link para redefinir sua senha.
              </p>
              <form onSubmit={enviar} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-fg/80 mb-1.5">E-mail</label>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
                  />
                </div>
                {erro && <p className="text-sm text-rust">{erro}</p>}
                <button
                  type="submit"
                  disabled={carregando}
                  className="w-full flex items-center justify-center gap-2 rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-ink hover:bg-brand-600 disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {carregando ? (
                    <>
                      <OndaSpin size={14} /> Enviando...
                    </>
                  ) : (
                    "Enviar link"
                  )}
                </button>
              </form>
            </>
          )}
          <p className="mt-4 text-sm text-fg/55">
            <Link href="/login" className="text-amber hover:text-amber-dim font-medium">
              Voltar para o login
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
