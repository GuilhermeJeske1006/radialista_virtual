"use client";

import { useEffect, useState } from "react";
import AppShell from "../../components/AppShell";
import { apiFetch, ApiError } from "../../lib/api";
import { RADIO_PERFIL_VAZIO, RadioPerfil, TipoRadio } from "../../lib/types";
import { LocufySpin } from "../../components/LocufyLogo";

export default function ConfiguracoesPage() {
  const [radio, setRadio] = useState<RadioPerfil>(RADIO_PERFIL_VAZIO);
  const [tiposRadio, setTiposRadio] = useState<TipoRadio[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState("");
  const [mensagem, setMensagem] = useState("");

  useEffect(() => {
    Promise.all([apiFetch<RadioPerfil>("/config/radio"), apiFetch<TipoRadio[]>("/config/tipos-radio")])
      .then(([radioCarregado, tipos]) => {
        setRadio(radioCarregado);
        setTiposRadio(tipos);
      })
      .catch((err) => setErro(err instanceof ApiError ? err.message : "Erro ao carregar dados da rádio"))
      .finally(() => setCarregando(false));
  }, []);

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    setErro("");
    setMensagem("");
    setSalvando(true);
    try {
      const atualizado = await apiFetch<RadioPerfil>("/config/radio", {
        method: "PUT",
        body: JSON.stringify(radio),
      });
      setRadio(atualizado);
      setMensagem("Dados da rádio salvos.");
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao salvar dados da rádio");
    } finally {
      setSalvando(false);
    }
  }

  if (carregando) {
    return (
      <AppShell title="Configuração da Rádio">
        <p className="flex items-center gap-2 text-sm text-fg/65">
          <LocufySpin size={16} /> Carregando...
        </p>
      </AppShell>
    );
  }

  return (
    <AppShell title="Configuração da Rádio" maxWidthClassName="max-w-2xl">
      <form onSubmit={salvar} className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6">
        <h2 className="font-display text-base font-bold text-fg mb-1">Dados da rádio</h2>
        <p className="text-sm text-fg/65 mb-5">
          Essas informações valem pra conta inteira e são usadas pelos seus radialistas de IA quando um ouvinte
          pergunta sobre a rádio.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-fg/80 mb-1.5">Nome da rádio</label>
            <input
              type="text"
              required
              placeholder="Ex.: Rádio Cidade FM"
              value={radio.nome_radio}
              onChange={(e) => setRadio({ ...radio, nome_radio: e.target.value })}
              className="w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-fg/80 mb-1.5">Slogan</label>
            <input
              type="text"
              placeholder="Ex.: A rádio que toca pra você"
              value={radio.slogan}
              onChange={(e) => setRadio({ ...radio, slogan: e.target.value })}
              className="w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-fg/80 mb-1.5">Frequência</label>
            <input
              type="text"
              placeholder="Ex.: 98.5 FM"
              value={radio.frequencia}
              onChange={(e) => setRadio({ ...radio, frequencia: e.target.value })}
              className="w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-fg/80 mb-1.5">Telefone</label>
            <input
              type="text"
              placeholder="Ex.: (11) 4000-0000"
              value={radio.telefone}
              onChange={(e) => setRadio({ ...radio, telefone: e.target.value })}
              className="w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-fg/80 mb-1.5">Endereço</label>
            <input
              type="text"
              placeholder="Ex.: Av. Principal, 123 - Centro"
              value={radio.endereco}
              onChange={(e) => setRadio({ ...radio, endereco: e.target.value })}
              className="w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-fg/80 mb-1.5">Cidade</label>
            <input
              type="text"
              placeholder="Ex.: Porto Alegre"
              value={radio.cidade}
              onChange={(e) => setRadio({ ...radio, cidade: e.target.value })}
              className="w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
            />
            <p className="text-xs text-fg/65 mt-1">Usada pro locutor comentar o clima real no ar.</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-fg/80 mb-1.5">Tipo de rádio</label>
            <select
              value={radio.tipo_radio}
              onChange={(e) => setRadio({ ...radio, tipo_radio: e.target.value })}
              className="w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
            >
              <option value="">Não definido</option>
              {tiposRadio.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
            <p className="text-xs text-fg/65 mt-1">
              Usado como perfil padrão nas gerações com IA de radialistas e programas.
            </p>
          </div>
        </div>

        {erro && <p className="text-sm text-rust-text mt-4">{erro}</p>}
        {mensagem && <p className="text-sm text-teal-text mt-4">{mensagem}</p>}

        <button
          type="submit"
          disabled={salvando}
          className="mt-5 rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-ink hover:bg-brand-600 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {salvando ? "Salvando..." : "Salvar"}
        </button>
      </form>
    </AppShell>
  );
}
