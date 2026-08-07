"use client";

import { useState } from "react";
import Link from "next/link";
import { apiFetch, ApiError } from "../../lib/api";
import { setToken } from "../../lib/auth";
import { RADIALISTA_VAZIO, Radialista } from "../../lib/types";
import { PLANOS, formatarReais } from "../../lib/planos";
import { OndaLogo, OndaSpin } from "../../components/OndaLogo";
import ThemeToggle from "../../components/ThemeToggle";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

type CampoErros = {
  nome?: string;
  email?: string;
  senha?: string;
  confirmarSenha?: string;
  nomeRadio?: string;
  nomeLocutor?: string;
};

function validarNome(v: string) {
  return v.trim() ? "" : "Preencha seu nome";
}
function validarEmail(v: string) {
  if (!v) return "Preencha seu e-mail";
  if (!EMAIL_RE.test(v)) return "E-mail inválido";
  return "";
}
function validarSenha(v: string) {
  return v.length >= 8 ? "" : "A senha precisa ter pelo menos 8 caracteres";
}
function validarConfirmarSenha(senha: string, v: string) {
  return v === senha ? "" : "As senhas não conferem";
}
function validarNomeRadio(v: string) {
  return v.trim() ? "" : "Dá um nome pra sua rádio";
}
function validarNomeLocutor(v: string) {
  return v.trim() ? "" : "Dá um nome pro seu locutor virtual";
}

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
  const [campoErros, setCampoErros] = useState<CampoErros>({});
  const [tocado, setTocado] = useState<Record<keyof CampoErros, boolean>>({
    nome: false,
    email: false,
    senha: false,
    confirmarSenha: false,
    nomeRadio: false,
    nomeLocutor: false,
  });

  function marcarTocado(campo: keyof CampoErros) {
    setTocado((t) => ({ ...t, [campo]: true }));
  }

  function onChangeNome(v: string) {
    setNome(v);
    setCampoErros((c) => ({ ...c, nome: validarNome(v) }));
  }
  function onChangeEmail(v: string) {
    setEmail(v);
    setCampoErros((c) => ({ ...c, email: validarEmail(v) }));
  }
  function onChangeSenha(v: string) {
    setSenha(v);
    setCampoErros((c) => ({
      ...c,
      senha: validarSenha(v),
      confirmarSenha: confirmarSenha ? validarConfirmarSenha(v, confirmarSenha) : c.confirmarSenha,
    }));
  }
  function onChangeConfirmarSenha(v: string) {
    setConfirmarSenha(v);
    setCampoErros((c) => ({ ...c, confirmarSenha: validarConfirmarSenha(senha, v) }));
  }
  function onChangeNomeRadio(v: string) {
    setNomeRadio(v);
    setCampoErros((c) => ({ ...c, nomeRadio: validarNomeRadio(v) }));
  }
  function onChangeNomeLocutor(v: string) {
    setNomeLocutor(v);
    setCampoErros((c) => ({ ...c, nomeLocutor: validarNomeLocutor(v) }));
  }

  function validar(): boolean {
    const erros: CampoErros = {
      nome: validarNome(nome),
      email: validarEmail(email),
      senha: validarSenha(senha),
      confirmarSenha: validarConfirmarSenha(senha, confirmarSenha),
      nomeRadio: validarNomeRadio(nomeRadio),
      nomeLocutor: validarNomeLocutor(nomeLocutor),
    };
    setCampoErros(erros);
    setTocado({
      nome: true,
      email: true,
      senha: true,
      confirmarSenha: true,
      nomeRadio: true,
      nomeLocutor: true,
    });
    const primeiroErro = Object.values(erros).find((m) => m);
    if (primeiroErro) {
      setErro(primeiroErro);
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

  const formInvalido =
    !!validarNome(nome) ||
    !!validarEmail(email) ||
    !!validarSenha(senha) ||
    !!validarConfirmarSenha(senha, confirmarSenha) ||
    !!validarNomeRadio(nomeRadio) ||
    !!validarNomeLocutor(nomeLocutor);

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-4xl">
        <div className="flex items-center justify-center gap-3 mb-6">
          <OndaLogo size={34} wordmarkClassName="text-2xl" />
          <ThemeToggle className="ml-1" />
        </div>

        <form onSubmit={concluir} className="bg-surface rounded-2xl border border-border-strong shadow-theme-sm p-6 sm:p-8 space-y-8">
          <div>
            <div className="flex items-center gap-3 mb-5">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-amber text-ink text-sm font-bold">
                1
              </span>
              <div>
                <h1 className="font-display text-lg font-bold text-fg">Criar conta</h1>
                <p className="text-sm text-fg/55">Seus dados de acesso ao painel.</p>
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-5">
              <div>
                <label className="block text-sm font-medium text-fg/80 mb-1.5">Seu nome</label>
                <input
                  type="text"
                  required
                  placeholder="Ex.: João da Silva"
                  value={nome}
                  onChange={(e) => onChangeNome(e.target.value)}
                  onBlur={() => { onChangeNome(nome); marcarTocado("nome"); }}
                  className={`w-full rounded-lg border bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:ring-2 ${
                    tocado.nome && campoErros.nome
                      ? "border-rust focus:border-rust focus:ring-rust/20"
                      : "border-border-strong focus:border-amber/50 focus:ring-amber/20"
                  }`}
                />
                {tocado.nome && campoErros.nome && (
                  <p className="mt-1 text-xs text-rust">{campoErros.nome}</p>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-fg/80 mb-1.5">E-mail</label>
                <input
                  type="email"
                  required
                  placeholder="Ex.: email@dominio.com"
                  value={email}
                  onChange={(e) => onChangeEmail(e.target.value)}
                  onBlur={() => { onChangeEmail(email); marcarTocado("email"); }}
                  className={`w-full rounded-lg border bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:ring-2 ${
                    tocado.email && campoErros.email
                      ? "border-rust focus:border-rust focus:ring-rust/20"
                      : "border-border-strong focus:border-amber/50 focus:ring-amber/20"
                  }`}
                />
                {tocado.email && campoErros.email && (
                  <p className="mt-1 text-xs text-rust">{campoErros.email}</p>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-fg/80 mb-1.5">Senha</label>
                <input
                  type="password"
                  required
                  placeholder="Mínimo de 8 caracteres"
                  minLength={8}
                  value={senha}
                  onChange={(e) => onChangeSenha(e.target.value)}
                  onBlur={() => { onChangeSenha(senha); marcarTocado("senha"); }}
                  className={`w-full rounded-lg border bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:ring-2 ${
                    tocado.senha && campoErros.senha
                      ? "border-rust focus:border-rust focus:ring-rust/20"
                      : "border-border-strong focus:border-amber/50 focus:ring-amber/20"
                  }`}
                />
                {tocado.senha && campoErros.senha ? (
                  <p className="mt-1 text-xs text-rust">{campoErros.senha}</p>
                ) : (
                  <p className="mt-1 text-xs text-fg/40">Mínimo de 8 caracteres</p>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-fg/80 mb-1.5">Confirmar senha</label>
                <input
                  type="password"
                  required
                  placeholder="Digite a mesma senha novamente"
                  minLength={8}
                  value={confirmarSenha}
                  onChange={(e) => onChangeConfirmarSenha(e.target.value)}
                  onBlur={() => { onChangeConfirmarSenha(confirmarSenha); marcarTocado("confirmarSenha"); }}
                  className={`w-full rounded-lg border bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:ring-2 ${
                    tocado.confirmarSenha && campoErros.confirmarSenha
                      ? "border-rust focus:border-rust focus:ring-rust/20"
                      : "border-border-strong focus:border-amber/50 focus:ring-amber/20"
                  }`}
                />
                {tocado.confirmarSenha && campoErros.confirmarSenha && (
                  <p className="mt-1 text-xs text-rust">{campoErros.confirmarSenha}</p>
                )}
              </div>
            </div>
          </div>

          <div className="border-t border-border pt-8">
            <div className="flex items-center gap-3 mb-5">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-amber text-ink text-sm font-bold">
                2
              </span>
              <div>
                <h2 className="font-display text-lg font-bold text-fg">Sua rádio</h2>
                <p className="text-sm text-fg/55">Dados da emissora e do locutor de IA que vai atender os ouvintes.</p>
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-5">
              <div>
                <label className="block text-sm font-medium text-fg/80 mb-1.5">Nome da rádio</label>
                <input
                  type="text"
                  required
                  placeholder="Ex.: Rádio Cidade FM"
                  value={nomeRadio}
                  onChange={(e) => onChangeNomeRadio(e.target.value)}
                  onBlur={() => { onChangeNomeRadio(nomeRadio); marcarTocado("nomeRadio"); }}
                  className={`w-full rounded-lg border bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:ring-2 ${
                    tocado.nomeRadio && campoErros.nomeRadio
                      ? "border-rust focus:border-rust focus:ring-rust/20"
                      : "border-border-strong focus:border-amber/50 focus:ring-amber/20"
                  }`}
                />
                {tocado.nomeRadio && campoErros.nomeRadio && (
                  <p className="mt-1 text-xs text-rust">{campoErros.nomeRadio}</p>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-fg/80 mb-1.5">Nome do locutor virtual</label>
                <input
                  type="text"
                  required
                  placeholder="Ex.: Zé do Rádio"
                  value={nomeLocutor}
                  onChange={(e) => onChangeNomeLocutor(e.target.value)}
                  onBlur={() => { onChangeNomeLocutor(nomeLocutor); marcarTocado("nomeLocutor"); }}
                  className={`w-full rounded-lg border bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:ring-2 ${
                    tocado.nomeLocutor && campoErros.nomeLocutor
                      ? "border-rust focus:border-rust focus:ring-rust/20"
                      : "border-border-strong focus:border-amber/50 focus:ring-amber/20"
                  }`}
                />
                {tocado.nomeLocutor && campoErros.nomeLocutor && (
                  <p className="mt-1 text-xs text-rust">{campoErros.nomeLocutor}</p>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-fg/80 mb-1.5">
                  Slogan <span className="text-fg/40 font-normal">(opcional)</span>
                </label>
                <input
                  type="text"
                  placeholder="Ex.: A rádio que toca pra você"
                  value={slogan}
                  onChange={(e) => setSlogan(e.target.value)}
                  className="w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-fg/80 mb-1.5">
                  Frequência <span className="text-fg/40 font-normal">(opcional)</span>
                </label>
                <input
                  type="text"
                  placeholder="Ex.: 98.5 FM"
                  value={frequencia}
                  onChange={(e) => setFrequencia(e.target.value)}
                  className="w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-fg/80 mb-1.5">
                  Telefone da rádio <span className="text-fg/40 font-normal">(opcional)</span>
                </label>
                <input
                  type="text"
                  placeholder="Ex.: (11) 4000-0000"
                  value={telefoneRadio}
                  onChange={(e) => setTelefoneRadio(e.target.value)}
                  className="w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-fg/80 mb-1.5">
                  Endereço <span className="text-fg/40 font-normal">(opcional)</span>
                </label>
                <input
                  type="text"
                  placeholder="Ex.: Av. Principal, 123 - Centro"
                  value={enderecoRadio}
                  onChange={(e) => setEnderecoRadio(e.target.value)}
                  className="w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
                />
              </div>
            </div>
          </div>

          <div className="border-t border-border pt-8">
            <div className="flex items-center gap-3 mb-5">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-amber text-ink text-sm font-bold">
                3
              </span>
              <div>
                <h2 className="font-display text-lg font-bold text-fg">Escolha seu plano</h2>
                <p className="text-sm text-fg/55">Você vai ser redirecionado pro checkout seguro pra confirmar a assinatura.</p>
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {PLANOS.map((plano) => {
                const selecionado = planoId === plano.id;
                return (
                  <button
                    type="button"
                    key={plano.id}
                    onClick={() => setPlanoId(plano.id)}
                    className={`relative text-left rounded-xl border p-4 transition-colors hover:-translate-y-0.5 hover:shadow-theme-sm ${
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

          <div className="border-t border-border pt-6">
            {erro && <p className="mb-3 text-sm text-rust">{erro}</p>}

            <button
              type="submit"
              disabled={carregando || formInvalido}
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
          </div>
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
