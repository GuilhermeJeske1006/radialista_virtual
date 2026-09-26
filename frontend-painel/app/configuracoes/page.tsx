"use client";

import { useEffect, useState } from "react";
import AppShell from "../../components/AppShell";
import { apiFetch, ApiError } from "../../lib/api";
import { RADIO_PERFIL_VAZIO, RadioPerfil, TipoRadio } from "../../lib/types";
import { LocufySpin } from "../../components/LocufyLogo";
import TagInput from "../../components/TagInput";
import WhatsAppConexao from "../../components/WhatsAppConexao";
import { useAvisoAlteracoes } from "../../lib/useAvisoAlteracoes";

export default function ConfiguracoesPage() {
  const [radio, setRadio] = useState<RadioPerfil>(RADIO_PERFIL_VAZIO);
  const [tiposRadio, setTiposRadio] = useState<TipoRadio[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState("");
  const [mensagem, setMensagem] = useState("");
  const [original, setOriginal] = useState("");

  useEffect(() => {
    Promise.all([apiFetch<RadioPerfil>("/config/radio"), apiFetch<TipoRadio[]>("/config/tipos-radio")])
      .then(([radioCarregado, tipos]) => {
        setRadio(radioCarregado);
        setOriginal(JSON.stringify(radioCarregado));
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
      setOriginal(JSON.stringify(atualizado));
      setMensagem("Dados da rádio salvos.");
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao salvar dados da rádio");
    } finally {
      setSalvando(false);
    }
  }

  const alteracoesPendentes = original !== "" && JSON.stringify(radio) !== original;
  useAvisoAlteracoes(alteracoesPendentes);

  if (carregando) {
    return (
      <AppShell title="Configuração">
        <p className="flex items-center gap-2 text-sm text-fg/65">
          <LocufySpin size={16} /> Carregando…
        </p>
      </AppShell>
    );
  }

  return (
    <AppShell title="Configuração" maxWidthClassName="max-w-2xl">
      <section
        id="whatsapp"
        aria-labelledby="whatsapp-titulo"
        className="mb-6 scroll-mt-24 bg-surface rounded-3xl border border-border-strong shadow-theme-xs p-6"
      >
        <h2 id="whatsapp-titulo" className="font-display text-base font-bold text-fg mb-1">
          WhatsApp da rádio
        </h2>
        <p className="text-sm text-fg/65 mb-4">
          Um número para todos os radialistas. É por ele que os ouvintes mandam recados e pedidos.
        </p>
        <WhatsAppConexao />
      </section>

      <form onSubmit={salvar} className="bg-surface rounded-3xl border border-border-strong shadow-theme-xs p-6">
        <h2 className="font-display text-base font-bold text-fg mb-1">Dados da rádio</h2>
        <p className="text-sm text-fg/65 mb-5">
          Essas informações valem para a conta inteira e são usadas pelos seus radialistas de IA quando um ouvinte
          pergunta sobre a rádio.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label htmlFor="configuracoes-nome-da-radio" className="block text-sm font-medium text-fg/80 mb-1.5">Nome da rádio</label>
            <input
              id="configuracoes-nome-da-radio"
              type="text"
              required
              placeholder="Ex.: Rádio Cidade FM"
              value={radio.nome_radio}
              onChange={(e) => setRadio({ ...radio, nome_radio: e.target.value })}
              className="w-full rounded-xl border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-acento-claro/50 focus:ring-2 focus:ring-acento-claro/20"
            />
          </div>
          <div>
            <label htmlFor="configuracoes-slogan" className="block text-sm font-medium text-fg/80 mb-1.5">Slogan</label>
            <input
              id="configuracoes-slogan"
              type="text"
              placeholder="Ex.: A rádio que toca pra você"
              value={radio.slogan}
              onChange={(e) => setRadio({ ...radio, slogan: e.target.value })}
              className="w-full rounded-xl border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-acento-claro/50 focus:ring-2 focus:ring-acento-claro/20"
            />
          </div>
          <div>
            <label htmlFor="configuracoes-frequencia" className="block text-sm font-medium text-fg/80 mb-1.5">Frequência</label>
            <input
              id="configuracoes-frequencia"
              type="text"
              placeholder="Ex.: 98.5 FM"
              value={radio.frequencia}
              onChange={(e) => setRadio({ ...radio, frequencia: e.target.value })}
              className="w-full rounded-xl border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-acento-claro/50 focus:ring-2 focus:ring-acento-claro/20"
            />
          </div>
          <div>
            <label htmlFor="configuracoes-telefone" className="block text-sm font-medium text-fg/80 mb-1.5">Telefone</label>
            <input
              id="configuracoes-telefone"
              type="text"
              placeholder="Ex.: (11) 4000-0000"
              value={radio.telefone}
              onChange={(e) => setRadio({ ...radio, telefone: e.target.value })}
              className="w-full rounded-xl border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-acento-claro/50 focus:ring-2 focus:ring-acento-claro/20"
            />
          </div>
          <div>
            <label htmlFor="configuracoes-endereco" className="block text-sm font-medium text-fg/80 mb-1.5">Endereço</label>
            <input
              id="configuracoes-endereco"
              type="text"
              placeholder="Ex.: Av. Principal, 123 - Centro"
              value={radio.endereco}
              onChange={(e) => setRadio({ ...radio, endereco: e.target.value })}
              className="w-full rounded-xl border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-acento-claro/50 focus:ring-2 focus:ring-acento-claro/20"
            />
          </div>
          <div>
            <label htmlFor="configuracoes-cidade" className="block text-sm font-medium text-fg/80 mb-1.5">Cidade</label>
            <input
              id="configuracoes-cidade"
              type="text"
              placeholder="Ex.: Porto Alegre"
              value={radio.cidade}
              onChange={(e) => setRadio({ ...radio, cidade: e.target.value })}
              className="w-full rounded-xl border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-acento-claro/50 focus:ring-2 focus:ring-acento-claro/20"
            />
            <p className="text-xs text-fg/65 mt-1">Usada pelo radialista para comentar o clima real no ar.</p>
          </div>
          <div>
            <label htmlFor="configuracoes-tipo-de-radio" className="block text-sm font-medium text-fg/80 mb-1.5">Tipo de rádio</label>
            <select
              id="configuracoes-tipo-de-radio"
              value={radio.tipo_radio}
              onChange={(e) => setRadio({ ...radio, tipo_radio: e.target.value })}
              className="w-full rounded-xl border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-acento-claro/50 focus:ring-2 focus:ring-acento-claro/20"
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

        <hr className="border-border my-5" />
        <h2 className="font-display text-base font-bold text-fg mb-1">Conhecimento local</h2>
        <p className="text-sm text-fg/65 mb-5">
          Bairro, ponto de referência, evento tradicional, gíria da região — coisas que só quem é
          daqui sabe de verdade. Preencha manualmente; não é gerado por IA, pra não inventar lugar
          ou fato errado.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="sm:col-span-2">
            <label htmlFor="configuracoes-gentilico" className="block text-sm font-medium text-fg/80 mb-1.5">Gentílico</label>
            <input
              id="configuracoes-gentilico"
              type="text"
              placeholder="Ex.: porto-alegrense"
              value={radio.conhecimento_local.gentilico}
              onChange={(e) =>
                setRadio({
                  ...radio,
                  conhecimento_local: { ...radio.conhecimento_local, gentilico: e.target.value },
                })
              }
              className="w-full rounded-xl border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-acento-claro/50 focus:ring-2 focus:ring-acento-claro/20"
            />
          </div>
        </div>
        <TagInput
          label="Bairros"
          tags={radio.conhecimento_local.bairros}
          onChange={(tags) =>
            setRadio({ ...radio, conhecimento_local: { ...radio.conhecimento_local, bairros: tags } })
          }
        />
        <TagInput
          label="Pontos de referência"
          tags={radio.conhecimento_local.pontos_referencia}
          onChange={(tags) =>
            setRadio({
              ...radio,
              conhecimento_local: { ...radio.conhecimento_local, pontos_referencia: tags },
            })
          }
        />
        <TagInput
          label="Eventos recorrentes da cidade"
          tags={radio.conhecimento_local.eventos_recorrentes}
          onChange={(tags) =>
            setRadio({
              ...radio,
              conhecimento_local: { ...radio.conhecimento_local, eventos_recorrentes: tags },
            })
          }
        />
        <TagInput
          label="Gírias e expressões regionais"
          tags={radio.conhecimento_local.expressoes_regionais}
          onChange={(tags) =>
            setRadio({
              ...radio,
              conhecimento_local: { ...radio.conhecimento_local, expressoes_regionais: tags },
            })
          }
        />

        <hr className="border-border my-5" />
        <h2 className="font-display text-base font-bold text-fg mb-1">Bíblia da rádio</h2>
        <p className="text-sm text-fg/65 mb-5">
          História, rotina real e outros programas da grade — o que faz a rádio parecer um lugar
          de trabalho de verdade, não só um nome. Preencha manualmente; não é gerado por IA.
        </p>
        <div>
          <label htmlFor="configuracoes-historia-da-radio" className="block text-sm font-medium text-fg/80 mb-1.5">História da rádio</label>
          <textarea
            id="configuracoes-historia-da-radio"
            rows={4}
            placeholder="Ex.: Fundada em 1998 por seu Zé, começou como rádio comunitária de bairro e hoje é referência na cidade."
            value={radio.biblia_radio.historia}
            onChange={(e) =>
              setRadio({ ...radio, biblia_radio: { ...radio.biblia_radio, historia: e.target.value } })
            }
            className="w-full rounded-xl border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-acento-claro/50 focus:ring-2 focus:ring-acento-claro/20 mb-4"
          />
        </div>
        <TagInput
          label="Rotina real (parcerias, transmissões fixas, etc.)"
          tags={radio.biblia_radio.rotina}
          onChange={(tags) => setRadio({ ...radio, biblia_radio: { ...radio.biblia_radio, rotina: tags } })}
        />
        <TagInput
          label="Outros programas da grade (mesmo que não sejam de IA)"
          tags={radio.biblia_radio.programas_grade}
          onChange={(tags) =>
            setRadio({ ...radio, biblia_radio: { ...radio.biblia_radio, programas_grade: tags } })
          }
        />
        <TagInput
          label="Equipe (colegas que existem na rádio mas não estão ao vivo: técnico de som, comercial, etc.)"
          tags={radio.biblia_radio.equipe}
          onChange={(tags) => setRadio({ ...radio, biblia_radio: { ...radio.biblia_radio, equipe: tags } })}
        />
        <TagInput
          label="Hábitos de trabalho reais (ex.: 'confere o trânsito antes de entrar no ar')"
          tags={radio.biblia_radio.habitos_trabalho}
          onChange={(tags) =>
            setRadio({ ...radio, biblia_radio: { ...radio.biblia_radio, habitos_trabalho: tags } })
          }
        />

        {erro && <p role="alert" className="text-sm text-laranja mt-4">{erro}</p>}

        <div className="sticky bottom-0 z-10 -mx-6 -mb-6 mt-5 flex flex-wrap items-center gap-3 rounded-b-3xl border-t border-border bg-surface/95 px-6 py-3 backdrop-blur">
          <button
            type="submit"
            disabled={salvando}
            className="rounded-xl bg-brand-500 px-4 py-2.5 text-sm font-medium text-on-brand hover:bg-brand-600 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {salvando ? "Salvando…" : "Salvar dados da rádio"}
          </button>
          {alteracoesPendentes && <span className="text-xs text-laranja">Alterações não salvas</span>}
          {mensagem && !alteracoesPendentes && <span role="status" className="text-xs text-ciano">{mensagem}</span>}
        </div>
      </form>
    </AppShell>
  );
}
