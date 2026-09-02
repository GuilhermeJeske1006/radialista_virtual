"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import AdminShell from "../../../../components/AdminShell";
import ConfirmDialog from "../../../../components/ConfirmDialog";
import { LocufySpin } from "../../../../components/LocufyLogo";
import { apiFetch, ApiError } from "../../../../lib/api";
import { PLANOS } from "../../../../lib/planos";
import { AdminEmpresaDetalhe } from "../../../../lib/types";

const STATUS_LABEL: Record<string, string> = {
  trial: "Trial",
  ativo: "Ativo",
  inadimplente: "Inadimplente",
  cancelado: "Cancelado",
};

const inputClass =
  "w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20";

function formatarData(iso: string): string {
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "short", year: "numeric" });
}

export default function AdminEmpresaDetalhePage() {
  const params = useParams<{ id: string }>();
  const accountId = Number(params.id);

  const [empresa, setEmpresa] = useState<AdminEmpresaDetalhe | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");
  const [mensagem, setMensagem] = useState("");

  const [planoSelecionado, setPlanoSelecionado] = useState("");
  const [statusSelecionado, setStatusSelecionado] = useState("");
  const [confirmando, setConfirmando] = useState(false);
  const [salvando, setSalvando] = useState(false);

  function carregar() {
    setCarregando(true);
    setErro("");
    apiFetch<AdminEmpresaDetalhe>(`/admin/empresas/${accountId}`)
      .then((dados) => {
        setEmpresa(dados);
        setPlanoSelecionado(dados.plano);
        setStatusSelecionado(dados.plano_status);
      })
      .catch((err) => setErro(err instanceof ApiError ? err.message : "Erro ao carregar empresa"))
      .finally(() => setCarregando(false));
  }

  useEffect(() => {
    if (Number.isFinite(accountId)) carregar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accountId]);

  async function salvar() {
    setSalvando(true);
    setErro("");
    setMensagem("");
    try {
      const atualizada = await apiFetch<AdminEmpresaDetalhe>(`/admin/empresas/${accountId}`, {
        method: "PATCH",
        body: JSON.stringify({ plano: planoSelecionado, plano_status: statusSelecionado }),
      });
      setEmpresa(atualizada);
      setMensagem("Empresa atualizada.");
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao atualizar empresa");
    } finally {
      setSalvando(false);
      setConfirmando(false);
    }
  }

  if (carregando) {
    return (
      <AdminShell title="Empresa">
        <p className="flex items-center gap-2 text-sm text-fg/65">
          <LocufySpin size={16} /> Carregando...
        </p>
      </AdminShell>
    );
  }

  if (!empresa) {
    return (
      <AdminShell title="Empresa">
        <p className="text-sm text-rust-text">{erro || "Empresa não encontrada."}</p>
      </AdminShell>
    );
  }

  const houveMudanca = planoSelecionado !== empresa.plano || statusSelecionado !== empresa.plano_status;

  return (
    <AdminShell title={empresa.nome_radio || `Empresa #${empresa.id}`} maxWidthClassName="max-w-3xl">
      <Link href="/admin" className="text-sm text-amber-text hover:underline mb-4 inline-block">
        ← Todas as empresas
      </Link>

      <div className="space-y-5">
        {erro && <p className="text-sm text-rust-text">{erro}</p>}
        {mensagem && <p className="text-sm text-teal-text">{mensagem}</p>}

        <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6">
          <h2 className="font-display text-base font-bold text-fg mb-4">Dados da rádio</h2>
          <dl className="grid sm:grid-cols-2 gap-3 text-sm">
            <Campo rotulo="Slogan" valor={empresa.slogan || "—"} />
            <Campo rotulo="Frequência" valor={empresa.frequencia || "—"} />
            <Campo rotulo="Cidade" valor={empresa.cidade || "—"} />
            <Campo rotulo="Tipo de rádio" valor={empresa.tipo_radio || "—"} />
            <Campo rotulo="Criada em" valor={formatarData(empresa.criado_em)} />
            <Campo rotulo="Tokens do WhatsApp no mês" valor={String(empresa.mensagens_mes)} />
            <Campo rotulo="Agentes" valor={String(empresa.agentes)} />
            <Campo rotulo="Usuários ativos" valor={String(empresa.usuarios_ativos)} />
          </dl>
        </div>

        <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6">
          <h2 className="font-display text-base font-bold text-fg mb-1">Plano e assinatura</h2>
          <p className="text-sm text-fg/65 mb-4">
            Mudar aqui altera só o registro local — não mexe na assinatura do Stripe. Use pra correções manuais.
          </p>
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="flex-1">
              <label className="block text-xs font-medium text-fg/65 mb-1">Plano</label>
              <select
                value={planoSelecionado}
                onChange={(e) => setPlanoSelecionado(e.target.value)}
                className={inputClass}
              >
                {PLANOS.map((plano) => (
                  <option key={plano.id} value={plano.id}>
                    {plano.nome}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex-1">
              <label className="block text-xs font-medium text-fg/65 mb-1">Status</label>
              <select
                value={statusSelecionado}
                onChange={(e) => setStatusSelecionado(e.target.value)}
                className={inputClass}
              >
                {Object.entries(STATUS_LABEL).map(([valor, label]) => (
                  <option key={valor} value={valor}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="mt-4 flex justify-end">
            <button
              type="button"
              disabled={!houveMudanca || salvando}
              onClick={() => setConfirmando(true)}
              className="rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-ink hover:bg-brand-600 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              Salvar alterações
            </button>
          </div>
        </div>

        <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6">
          <h2 className="font-display text-base font-bold text-fg mb-4">Usuários</h2>
          <div className="space-y-2">
            {empresa.usuarios.map((usuario) => (
              <div key={usuario.id} className="flex items-center justify-between gap-3 rounded-lg border border-border px-4 py-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-fg truncate">{usuario.nome || usuario.email}</p>
                  <p className="text-xs text-fg/65 truncate">{usuario.email}</p>
                </div>
                <div className="flex items-center gap-2 shrink-0 text-xs text-fg/65">
                  <span className="capitalize">{usuario.role}</span>
                  {!usuario.ativo && <span className="rounded-full bg-paper px-2 py-0.5">Inativo</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <ConfirmDialog
        open={confirmando}
        title="Atualizar plano/status"
        mensagem={`Aplicar plano "${planoSelecionado}" e status "${STATUS_LABEL[statusSelecionado]}" para ${empresa.nome_radio || `empresa #${empresa.id}`}? Isso pode ativar ou desativar os agentes da rádio na hora.`}
        confirmarLabel="Aplicar"
        onConfirmar={salvar}
        onCancelar={() => setConfirmando(false)}
      />
    </AdminShell>
  );
}

function Campo({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <div>
      <dt className="text-xs text-fg/65">{rotulo}</dt>
      <dd className="text-fg font-medium">{valor}</dd>
    </div>
  );
}
