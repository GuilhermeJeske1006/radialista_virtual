"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AppShell from "../../components/AppShell";
import { apiFetch, ApiError } from "../../lib/api";
import { Conta } from "../../lib/types";
import { PLANOS } from "../../lib/planos";
import { rotuloStatusAssinatura } from "../../lib/rotulosConsumo";
import { LocufyLed, LocufySpin } from "../../components/LocufyLogo";

const STATUS_COR: Record<string, "ciano" | "acento" | "laranja"> = {
  trial: "acento",
  ativo: "ciano",
  inadimplente: "laranja",
  cancelado: "laranja",
};

const STATUS_CLASSE: Record<"ciano" | "acento" | "laranja", string> = {
  ciano: "bg-ciano/10 text-ciano",
  acento: "bg-acento/10 text-acento-claro",
  laranja: "bg-laranja/10 text-laranja",
};

function formatarData(iso: string): string {
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" });
}

export default function PerfilPage() {
  const router = useRouter();
  const [conta, setConta] = useState<Conta | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");

  const [nome, setNome] = useState("");
  const [salvandoNome, setSalvandoNome] = useState(false);
  const [erroNome, setErroNome] = useState("");
  const [mensagemNome, setMensagemNome] = useState("");

  const [senhaAtual, setSenhaAtual] = useState("");
  const [senhaNova, setSenhaNova] = useState("");
  const [confirmarSenha, setConfirmarSenha] = useState("");
  const [salvandoSenha, setSalvandoSenha] = useState(false);
  const [erroSenha, setErroSenha] = useState("");
  const [mensagemSenha, setMensagemSenha] = useState("");

  useEffect(() => {
    apiFetch<Conta>("/auth/me")
      .then((dados) => {
        setConta(dados);
        setNome(dados.nome);
      })
      .catch((err) => setErro(err instanceof ApiError ? err.message : "Erro ao carregar perfil"))
      .finally(() => setCarregando(false));
  }, []);

  async function salvarNome(e: React.FormEvent) {
    e.preventDefault();
    setErroNome("");
    setMensagemNome("");
    if (!nome.trim()) {
      setErroNome("Informe um nome");
      return;
    }

    setSalvandoNome(true);
    try {
      const atualizado = await apiFetch<Conta>("/auth/perfil", {
        method: "PATCH",
        body: JSON.stringify({ nome: nome.trim() }),
      });
      setConta(atualizado);
      setNome(atualizado.nome);
      setMensagemNome("Nome atualizado.");
    } catch (err) {
      setErroNome(err instanceof ApiError ? err.message : "Erro ao atualizar nome");
    } finally {
      setSalvandoNome(false);
    }
  }

  async function alterarSenha(e: React.FormEvent) {
    e.preventDefault();
    setErroSenha("");
    setMensagemSenha("");

    if (senhaNova.length < 8) {
      setErroSenha("A nova senha precisa ter pelo menos 8 caracteres");
      return;
    }
    if (senhaNova !== confirmarSenha) {
      setErroSenha("A confirmação não bate com a nova senha");
      return;
    }

    setSalvandoSenha(true);
    try {
      await apiFetch("/auth/senha", {
        method: "PUT",
        body: JSON.stringify({ senha_atual: senhaAtual, senha_nova: senhaNova }),
      });
      setMensagemSenha("Senha alterada.");
      setSenhaAtual("");
      setSenhaNova("");
      setConfirmarSenha("");
    } catch (err) {
      setErroSenha(err instanceof ApiError ? err.message : "Erro ao alterar senha");
    } finally {
      setSalvandoSenha(false);
    }
  }

  function sair() {
    apiFetch("/auth/logout", { method: "POST" }).catch(() => {});
    router.push("/login");
  }

  if (carregando) {
    return (
      <AppShell title="Perfil">
        <p className="flex items-center gap-2 text-sm text-fg/65">
          <LocufySpin size={16} /> Carregando…
        </p>
      </AppShell>
    );
  }

  if (!conta) {
    return (
      <AppShell title="Perfil">
        <p className="text-sm text-laranja">{erro || "Não foi possível carregar seu perfil."}</p>
      </AppShell>
    );
  }

  const nomePlano = PLANOS.find((p) => p.id === conta.plano)?.nome ?? conta.plano;
  const statusCor = STATUS_COR[conta.plano_status] ?? "acento";

  return (
    <AppShell title="Perfil" maxWidthClassName="max-w-2xl">
      <div className="space-y-5">
        <div className="bg-surface rounded-3xl border border-border-strong shadow-theme-xs p-6">
          <h2 className="font-display text-base font-bold text-fg mb-5">Sua conta</h2>

          <form onSubmit={salvarNome} className="flex items-end gap-2 mb-4">
            <div className="flex-1 min-w-0">
              <label htmlFor="perfil-nome" className="block text-sm font-medium text-fg/80 mb-1.5">Nome</label>
              <input
                id="perfil-nome"
                type="text"
                required
                value={nome}
                onChange={(e) => setNome(e.target.value)}
                className="w-full rounded-xl border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-acento-claro/50 focus:ring-2 focus:ring-acento-claro/20"
              />
            </div>
            <button
              type="submit"
              disabled={salvandoNome || nome.trim() === conta.nome}
              className="rounded-xl border border-border-strong px-4 py-2 text-sm font-medium text-fg hover:bg-fg/5 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {salvandoNome ? "Salvando…" : "Salvar"}
            </button>
          </form>
          {erroNome && <p className="text-sm text-laranja mb-4">{erroNome}</p>}
          {mensagemNome && <p className="text-sm text-ciano mb-4">{mensagemNome}</p>}

          <dl className="space-y-4">
            <div className="flex items-center justify-between gap-4">
              <dt className="text-sm text-fg/65">E-mail</dt>
              <dd className="text-sm font-medium text-fg">{conta.email}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt className="text-sm text-fg/65">Membro desde</dt>
              <dd className="text-sm font-medium text-fg">{formatarData(conta.criado_em)}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt className="text-sm text-fg/65">Plano</dt>
              <dd className="text-sm font-medium text-fg">{nomePlano}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt className="text-sm text-fg/65">Status</dt>
              <dd>
                <span
                  className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_CLASSE[statusCor]}`}
                >
                  <LocufyLed color={statusCor} pulse={false} />
                  {rotuloStatusAssinatura(conta.plano_status)}
                </span>
              </dd>
            </div>
          </dl>
          <Link href="/billing" className="mt-5 inline-block text-sm font-medium text-acento-claro hover:text-acento-dim">
            Gerenciar assinatura →
          </Link>
        </div>

        <form onSubmit={alterarSenha} className="bg-surface rounded-3xl border border-border-strong shadow-theme-xs p-6">
          <h2 className="font-display text-base font-bold text-fg mb-5">Alterar senha</h2>
          <div className="space-y-4">
            <div>
              <label htmlFor="perfil-senha-atual" className="block text-sm font-medium text-fg/80 mb-1.5">Senha atual</label>
              <input
                id="perfil-senha-atual"
                type="password"
                required
                value={senhaAtual}
                onChange={(e) => setSenhaAtual(e.target.value)}
                className="w-full rounded-xl border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-acento-claro/50 focus:ring-2 focus:ring-acento-claro/20"
              />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label htmlFor="perfil-senha-nova" className="block text-sm font-medium text-fg/80 mb-1.5">Nova senha</label>
                <input
                  id="perfil-senha-nova"
                  type="password"
                  required
                  minLength={8}
                  value={senhaNova}
                  onChange={(e) => setSenhaNova(e.target.value)}
                  className="w-full rounded-xl border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-acento-claro/50 focus:ring-2 focus:ring-acento-claro/20"
                />
              </div>
              <div>
                <label htmlFor="perfil-senha-confirmar" className="block text-sm font-medium text-fg/80 mb-1.5">Confirmar nova senha</label>
                <input
                  id="perfil-senha-confirmar"
                  type="password"
                  required
                  minLength={8}
                  value={confirmarSenha}
                  onChange={(e) => setConfirmarSenha(e.target.value)}
                  className="w-full rounded-xl border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-acento-claro/50 focus:ring-2 focus:ring-acento-claro/20"
                />
              </div>
            </div>
            {erroSenha && <p className="text-sm text-laranja">{erroSenha}</p>}
            {mensagemSenha && <p className="text-sm text-ciano">{mensagemSenha}</p>}
            <button
              type="submit"
              disabled={salvandoSenha}
              className="rounded-xl bg-brand-500 px-4 py-2.5 text-sm font-medium text-on-brand hover:bg-brand-600 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {salvandoSenha ? "Salvando…" : "Alterar senha"}
            </button>
          </div>
        </form>

        <div className="bg-surface rounded-3xl border border-border-strong shadow-theme-xs p-6">
          <h2 className="font-display text-base font-bold text-fg mb-1">Sessão</h2>
          <p className="text-sm text-fg/65 mb-4">Encerrar sua sessão neste dispositivo.</p>
          <button
            type="button"
            onClick={sair}
            className="rounded-xl border border-laranja/40 px-4 py-2.5 text-sm font-medium text-laranja hover:bg-laranja/10"
          >
            Sair da conta
          </button>
        </div>
      </div>
    </AppShell>
  );
}
