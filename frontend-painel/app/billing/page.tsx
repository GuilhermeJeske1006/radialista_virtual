"use client";

import { useEffect, useState } from "react";
import AppShell from "../../components/AppShell";
import { apiFetch, ApiError } from "../../lib/api";

export default function BillingPage() {
  const [planoStatus, setPlanoStatus] = useState<string>("");
  const [carregando, setCarregando] = useState(true);
  const [redirecionando, setRedirecionando] = useState(false);
  const [erro, setErro] = useState("");

  useEffect(() => {
    apiFetch<{ plano_status: string }>("/billing/status")
      .then((res) => setPlanoStatus(res.plano_status))
      .catch((err) => setErro(err instanceof ApiError ? err.message : "Erro ao carregar plano"))
      .finally(() => setCarregando(false));
  }, []);

  async function assinar() {
    setRedirecionando(true);
    setErro("");
    try {
      const { url } = await apiFetch<{ url: string }>("/billing/checkout", { method: "POST" });
      window.location.href = url;
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao iniciar assinatura");
      setRedirecionando(false);
    }
  }

  const ativo = planoStatus === "ativo";

  return (
    <AppShell title="Assinatura">
      <div className="bg-white rounded-2xl border border-gray-200 shadow-theme-xs p-6 max-w-lg">
        <h2 className="text-base font-semibold text-gray-900 mb-4">Plano atual</h2>
        {carregando ? (
          <p className="text-sm text-gray-500">Carregando...</p>
        ) : (
          <>
            <div className="flex items-center gap-2 mb-4">
              <span className="text-sm text-gray-600">Status:</span>
              <span
                className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                  ativo ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
                }`}
              >
                {planoStatus}
              </span>
            </div>
            {!ativo && (
              <button
                onClick={assinar}
                disabled={redirecionando}
                className="rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {redirecionando ? "Redirecionando..." : "Assinar"}
              </button>
            )}
            {erro && <p className="text-sm text-red-600 mt-3">{erro}</p>}
          </>
        )}
      </div>
    </AppShell>
  );
}
