"use client";

import { useEffect, useState } from "react";
import AppShell from "../../components/AppShell";
import ConfirmDialog from "../../components/ConfirmDialog";
import { OndaSpin } from "../../components/OndaLogo";
import { apiFetch, ApiError } from "../../lib/api";
import { Conta, ConviteEquipe, UsuarioEquipe } from "../../lib/types";

const inputClass =
  "w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg placeholder:text-fg/35 focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20";

function formatarData(iso: string): string {
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "short", year: "numeric" });
}

export default function EquipePage() {
  const [conta, setConta] = useState<Conta | null>(null);
  const [usuarios, setUsuarios] = useState<UsuarioEquipe[]>([]);
  const [convites, setConvites] = useState<ConviteEquipe[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");

  const [emailConvite, setEmailConvite] = useState("");
  const [roleConvite, setRoleConvite] = useState<"admin" | "membro">("membro");
  const [convidando, setConvidando] = useState(false);
  const [erroConvite, setErroConvite] = useState("");

  const [paraRemover, setParaRemover] = useState<UsuarioEquipe | null>(null);
  const [paraRevogar, setParaRevogar] = useState<ConviteEquipe | null>(null);

  function carregar() {
    setCarregando(true);
    setErro("");
    Promise.all([
      apiFetch<Conta>("/auth/me"),
      apiFetch<UsuarioEquipe[]>("/equipe"),
      apiFetch<ConviteEquipe[]>("/equipe/convites"),
    ])
      .then(([contaResp, usuariosResp, convitesResp]) => {
        setConta(contaResp);
        setUsuarios(usuariosResp);
        setConvites(convitesResp);
      })
      .catch((err) => setErro(err instanceof ApiError ? err.message : "Erro ao carregar equipe"))
      .finally(() => setCarregando(false));
  }

  useEffect(() => {
    carregar();
  }, []);

  async function convidar(e: React.FormEvent) {
    e.preventDefault();
    setErroConvite("");
    setConvidando(true);
    try {
      await apiFetch("/equipe/convites", {
        method: "POST",
        body: JSON.stringify({ email: emailConvite.trim(), role: roleConvite }),
      });
      setEmailConvite("");
      setRoleConvite("membro");
      carregar();
    } catch (err) {
      setErroConvite(err instanceof ApiError ? err.message : "Erro ao enviar convite");
    } finally {
      setConvidando(false);
    }
  }

  async function alterarRole(usuario: UsuarioEquipe, role: "admin" | "membro") {
    setErro("");
    try {
      await apiFetch(`/equipe/${usuario.id}/role`, { method: "PATCH", body: JSON.stringify({ role }) });
      carregar();
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao alterar permissão");
    }
  }

  async function remover(usuario: UsuarioEquipe) {
    setErro("");
    try {
      await apiFetch(`/equipe/${usuario.id}`, { method: "DELETE" });
      carregar();
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao remover usuário");
    } finally {
      setParaRemover(null);
    }
  }

  async function reenviar(convite: ConviteEquipe) {
    setErro("");
    try {
      await apiFetch(`/equipe/convites/${convite.id}/reenviar`, { method: "POST" });
      carregar();
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao reenviar convite");
    }
  }

  async function revogar(convite: ConviteEquipe) {
    setErro("");
    try {
      await apiFetch(`/equipe/convites/${convite.id}`, { method: "DELETE" });
      carregar();
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao revogar convite");
    } finally {
      setParaRevogar(null);
    }
  }

  if (carregando) {
    return (
      <AppShell title="Equipe">
        <p className="flex items-center gap-2 text-sm text-fg/55">
          <OndaSpin size={16} /> Carregando...
        </p>
      </AppShell>
    );
  }

  const usuariosAtivos = usuarios.filter((u) => u.ativo);

  return (
    <AppShell title="Equipe" maxWidthClassName="max-w-3xl">
      <div className="space-y-5">
        {erro && <p className="text-sm text-rust">{erro}</p>}

        <form onSubmit={convidar} className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6">
          <h2 className="font-display text-base font-bold text-fg mb-1">Convidar</h2>
          <p className="text-sm text-fg/55 mb-4">A pessoa recebe um link por e-mail para criar a senha e entrar na equipe.</p>
          <div className="flex flex-col sm:flex-row items-start gap-3">
            <input
              type="email"
              required
              placeholder="email@dominio.com"
              value={emailConvite}
              onChange={(e) => setEmailConvite(e.target.value)}
              className={`${inputClass} sm:flex-1`}
            />
            <select
              value={roleConvite}
              onChange={(e) => setRoleConvite(e.target.value as "admin" | "membro")}
              className={`${inputClass} sm:w-40`}
            >
              <option value="membro">Membro</option>
              <option value="admin">Admin</option>
            </select>
            <button
              type="submit"
              disabled={convidando}
              className="rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-ink hover:bg-brand-600 disabled:opacity-60 disabled:cursor-not-allowed whitespace-nowrap"
            >
              {convidando ? "Enviando..." : "Enviar convite"}
            </button>
          </div>
          {erroConvite && <p className="mt-3 text-sm text-rust">{erroConvite}</p>}
        </form>

        <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6">
          <h2 className="font-display text-base font-bold text-fg mb-4">Membros</h2>
          <div className="space-y-2">
            {usuariosAtivos.map((usuario) => (
              <div
                key={usuario.id}
                className="flex items-center justify-between gap-3 rounded-lg border border-border px-4 py-3"
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium text-fg truncate">{usuario.nome || usuario.email}</p>
                  <p className="text-xs text-fg/55 truncate">{usuario.email}</p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <select
                    value={usuario.role}
                    onChange={(e) => alterarRole(usuario, e.target.value as "admin" | "membro")}
                    disabled={usuario.id === conta?.id}
                    className="rounded-lg border border-border-strong bg-bg px-2.5 py-1.5 text-xs font-medium text-fg disabled:opacity-50"
                  >
                    <option value="membro">Membro</option>
                    <option value="admin">Admin</option>
                  </select>
                  <button
                    type="button"
                    onClick={() => setParaRemover(usuario)}
                    disabled={usuario.id === conta?.id}
                    title={usuario.id === conta?.id ? "Você não pode remover sua própria conta" : "Remover"}
                    className="rounded-lg border border-rust/40 px-3 py-1.5 text-xs font-medium text-rust hover:bg-rust/10 disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    Remover
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {convites.length > 0 && (
          <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6">
            <h2 className="font-display text-base font-bold text-fg mb-4">Convites pendentes</h2>
            <div className="space-y-2">
              {convites.map((convite) => (
                <div
                  key={convite.id}
                  className="flex items-center justify-between gap-3 rounded-lg border border-border px-4 py-3"
                >
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-fg truncate">{convite.email}</p>
                    <p className="text-xs text-fg/55">
                      {convite.role === "admin" ? "Admin" : "Membro"} · expira em {formatarData(convite.expira_em)}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      type="button"
                      onClick={() => reenviar(convite)}
                      className="rounded-lg border border-border-strong px-3 py-1.5 text-xs font-medium text-fg hover:bg-paper/5"
                    >
                      Reenviar
                    </button>
                    <button
                      type="button"
                      onClick={() => setParaRevogar(convite)}
                      className="rounded-lg border border-rust/40 px-3 py-1.5 text-xs font-medium text-rust hover:bg-rust/10"
                    >
                      Revogar
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={paraRemover !== null}
        title="Remover da equipe"
        mensagem={`Remover ${paraRemover?.email} da equipe? A pessoa perde o acesso imediatamente.`}
        confirmarLabel="Remover"
        onConfirmar={() => paraRemover && remover(paraRemover)}
        onCancelar={() => setParaRemover(null)}
      />
      <ConfirmDialog
        open={paraRevogar !== null}
        title="Revogar convite"
        mensagem={`Revogar o convite enviado para ${paraRevogar?.email}?`}
        confirmarLabel="Revogar"
        onConfirmar={() => paraRevogar && revogar(paraRevogar)}
        onCancelar={() => setParaRevogar(null)}
      />
    </AppShell>
  );
}
