"use client";

import { useState } from "react";
import Link from "next/link";
import { apiFetch, ApiError } from "../../lib/api";
import { setToken } from "../../lib/auth";
import { RADIALISTA_VAZIO, Radialista } from "../../lib/types";
import { PLANOS, formatarReais } from "../../lib/planos";
import { OndaLogo, OndaSpin } from "../../components/OndaLogo";
import ThemeToggle from "../../components/ThemeToggle";

export default function RegisterPage() {
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [confirmarSenha, setConfirmarSenha] = useState("");
  const [nomeRadio, setNomeRadio] = useState("");
  const [slogan, setSlogan] = useState("");
  const [frequencia, setFrequencia] = useState("");
  const [telefoneRadio, setTelefoneRadio] = useState("");
  const [enderecoRadio, setEnderecoRadio] = useState("");
  const [nomeLocutor, setNomeLocutor] = useState("");
  const [planoId, setPlanoId] = useState("growth");
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(false);

  function validar(): boolean {
    if (!nome.trim()) {
      setErro("Preencha seu nome");
      return false;
    }
    if (!email) {
      setErro("Preencha seu e-mail");
      return false;
    }
    if (senha.length < 8) {
      setErro("A senha precisa ter pelo menos 8 caracteres");
      return false;
    }
    if (senha !== confirmarSenha) {
      setErro("As senhas não conferem");
      return false;
    }
    if (!nomeRadio.trim()) {
      setErro("Dá um nome pra sua rádio");
      return false;
    }
    if (!nomeLocutor.trim()) {
      setErro("Dá um nome pro seu locutor virtual");
      return false;
    }
    return true;
  }

  async function concluir(e: React.FormEvent) {
    e.preventDefault();
    setErro("");
    if (!validar()) return;
    setCarregando(true);
    try {
      const conta = await apiFetch<{ access_token: string }>("/auth/register", {
        method: "POST",
        body: JSON.stringify({ nome: nome.trim(), email, senha }),
      });
      setToken(conta.access_token);

      await apiFetch("/config/radio", {
        method: "PUT",
        body: JSON.stringify({
          nome_radio: nomeRadio.trim(),
          slogan: slogan.trim(),
          frequencia: frequencia.trim(),
          telefone: telefoneRadio.trim(),
          endereco: enderecoRadio.trim(),
        }),
      });

      const radialistas = await apiFetch<Radialista[]>("/config/radialistas");
      const radialista = radialistas[0];
      if (radialista) {
        await apiFetch(`/config/radialistas/${radialista.id}`, {
          method: "PUT",
          body: JSON.stringify({ ...RADIALISTA_VAZIO, nome_locutor: nomeLocutor.trim() }),
        });
      }

      const { url } = await apiFetch<{ url: string }>("/billing/checkout", { method: "POST" });
      window.location.href = url;
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao criar conta");
      setCarregando(false);
    }
  }

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-3xl">
        <div className="flex items-center justify-center gap-3 mb-6">
          <OndaLogo size={34} wordmarkClassName="text-2xl" />
          <ThemeToggle className="ml-1" />
        </div>

        <form onSubmit={concluir} className="bg-surface rounded-2xl border border-border-strong shadow-theme-sm p-6 space-y-8">
          <div>
            <h1 className="font-display text-lg font-bold text-fg mb-4">Criar conta</h1>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
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
                <label className="block text-sm font-medium text-fg/80 mb-1.5">E-mail</label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
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
            </div>
          </div>

          <div>
            <h2 className="font-display text-base font-bold text-fg mb-1">Sua rádio</h2>
            <p className="text-sm text-fg/55 mb-3">Dados da emissora e do locutor de IA que vai atender os ouvintes.</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-fg/80 mb-1.5">Nome da rádio</label>
                <input
                  type="text"
                  required
                  placeholder="Ex.: Rádio Cidade FM"
                  value={nomeRadio}
                  onChange={(e) => setNomeRadio(e.target.value)}
                  className="w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-fg/80 mb-1.5">Slogan</label>
                <input
                  type="text"
                  placeholder="Ex.: A rádio que toca pra você"
                  value={slogan}
                  onChange={(e) => setSlogan(e.target.value)}
                  className="w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-fg/80 mb-1.5">Frequência</label>
                <input
                  type="text"
                  placeholder="Ex.: 98.5 FM"
                  value={frequencia}
                  onChange={(e) => setFrequencia(e.target.value)}
                  className="w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-fg/80 mb-1.5">Telefone da rádio</label>
                <input
                  type="text"
                  placeholder="Ex.: (11) 4000-0000"
                  value={telefoneRadio}
                  onChange={(e) => setTelefoneRadio(e.target.value)}
                  className="w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-fg/80 mb-1.5">Endereço</label>
                <input
                  type="text"
                  placeholder="Ex.: Av. Principal, 123 - Centro"
                  value={enderecoRadio}
                  onChange={(e) => setEnderecoRadio(e.target.value)}
                  className="w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-fg/80 mb-1.5">Nome do locutor virtual</label>
                <input
                  type="text"
                  required
                  placeholder="Ex.: Zé do Rádio"
                  value={nomeLocutor}
                  onChange={(e) => setNomeLocutor(e.target.value)}
                  className="w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
                />
              </div>
            </div>
          </div>

          <div>
            <h2 className="font-display text-base font-bold text-fg mb-1">Escolha seu plano</h2>
            <p className="text-sm text-fg/55 mb-3">
              Você vai ser redirecionado pro checkout seguro pra confirmar a assinatura.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {PLANOS.map((plano) => {
                const selecionado = planoId === plano.id;
                return (
                  <button
                    type="button"
                    key={plano.id}
                    onClick={() => setPlanoId(plano.id)}
                    className={`relative text-left rounded-xl border p-4 transition-colors ${
                      selecionado
                        ? "bg-surface border-amber ring-1 ring-amber/30"
                        : "bg-surface border-border-strong hover:border-amber/40"
                    }`}
                  >
                    {plano.destaque && (
                      <span className="absolute -top-2.5 right-4 rounded-full bg-brand-500 px-2 py-0.5 text-[10px] font-semibold text-ink">
                        Mais escolhido
                      </span>
                    )}
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-display text-sm font-bold text-fg">{plano.nome}</span>
                      <span
                        className={`flex h-4.5 w-4.5 items-center justify-center rounded-full border ${
                          selecionado ? "border-amber bg-amber text-ink" : "border-border-strong"
                        }`}
                      >
                        {selecionado && (
                          <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" strokeWidth={3} stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                          </svg>
                        )}
                      </span>
                    </div>
                    <p className="text-xs text-fg/55 mb-3">{plano.descricao}</p>
                    <div className="mb-2">
                      <span className="font-display text-xl font-bold text-fg">R$ {formatarReais(plano.preco)}</span>
                      <span className="text-xs text-fg/45">/mês</span>
                    </div>
                    <p className="text-xs text-fg/55">
                      {plano.agentes} {plano.agentes === 1 ? "agente" : "agentes"} ·{" "}
                      {plano.mensagens.toLocaleString("pt-BR")} msgs/mês
                    </p>
                  </button>
                );
              })}
            </div>
          </div>

          {erro && <p className="text-sm text-rust">{erro}</p>}

          <button
            type="submit"
            disabled={carregando}
            className="w-full flex items-center justify-center gap-2 rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-ink hover:bg-brand-600 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {carregando ? (
              <>
                <OndaSpin size={14} /> Criando...
              </>
            ) : (
              "Criar conta e assinar"
            )}
          </button>
        </form>

        <p className="mt-4 text-sm text-fg/55 text-center">
          Já tem conta?{" "}
          <Link href="/login" className="text-amber hover:text-amber-dim font-medium">
            Entrar
          </Link>
        </p>
      </div>
    </div>
  );
}
