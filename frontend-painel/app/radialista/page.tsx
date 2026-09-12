"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "../../components/AppShell";
import CheckoutModal from "../../components/CheckoutModal";
import TagInput from "../../components/TagInput";
import VoiceSelect from "../../components/VoiceSelect";
import { apiFetch, ApiError } from "../../lib/api";
import {
  ConfiguracaoIA,
  ConfiguracaoIAPreview,
  DIAS_SEMANA_LABEL,
  Programa,
  Radialista,
  RadioPerfil,
  rotuloBloco,
  TipoRadio,
} from "../../lib/types";
import { setRadialistaAtualId } from "../../lib/radialistas";
import { LocufySpin } from "../../components/LocufyLogo";
import { PRECO_AGENTE_ADICIONAL, formatarReais } from "../../lib/planos";

type RadialistaProposto = ConfiguracaoIAPreview["radialista"];
type ProgramaProposto = ConfiguracaoIAPreview["programa"];

function alternarDia(dias: number[], dia: number): number[] {
  return dias.includes(dia) ? dias.filter((d) => d !== dia) : [...dias, dia].sort();
}

// Briefing guiado (ver Fase 8 do plano de melhoria) -- chips que so' compoem o texto livre da
// descricao, nao viram campo estruturado a parte: mais rapido que digitar do zero, sem exigir
// um formulario novo nem mudar o contrato da API (ainda e' so' uma string de descricao).
const CHIPS_GENERO = ["Sertanejo", "Gospel", "Pop nacional", "Forró", "MPB", "Pagode", "Rock"];
const CHIPS_PERIODO = ["Manhã", "Tarde", "Noite", "Madrugada"];
const CHIPS_PUBLICO = ["Jovem", "Família", "Trabalhador rural", "Adulto/idoso"];

function adicionarChip(descricaoAtual: string, chip: string): string {
  const texto = chip.toLowerCase();
  if (descricaoAtual.toLowerCase().includes(texto)) return descricaoAtual;
  return descricaoAtual ? `${descricaoAtual}, ${texto}` : texto;
}

export default function RadialistasPage() {
  const [radialistas, setRadialistas] = useState<Radialista[]>([]);
  const [programasPorRadialista, setProgramasPorRadialista] = useState<Record<number, Programa[]>>({});
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");
  const [mensagemUpgrade, setMensagemUpgrade] = useState("");
  const [modalIAAberto, setModalIAAberto] = useState(false);
  const [descricaoIA, setDescricaoIA] = useState("");
  const [gerandoIA, setGerandoIA] = useState(false);
  const [erroIA, setErroIA] = useState("");
  const [checkoutAgenteExtraAberto, setCheckoutAgenteExtraAberto] = useState(false);
  // Nao nulo = geracao ja voltou do preview e esta na tela de revisao (nada gravado ainda,
  // ver Fase 2 do plano de melhoria) -- radialistaEdit/programaEdit sao a copia editavel.
  const [proposta, setProposta] = useState<ConfiguracaoIAPreview | null>(null);
  const [radialistaEdit, setRadialistaEdit] = useState<RadialistaProposto | null>(null);
  const [programaEdit, setProgramaEdit] = useState<ProgramaProposto | null>(null);
  const [geracaoId, setGeracaoId] = useState<number | null>(null);
  const [criandoFinal, setCriandoFinal] = useState(false);
  const [processandoRefinamento, setProcessandoRefinamento] = useState(false);
  const [instrucaoAjuste, setInstrucaoAjuste] = useState("");
  const [tipoRadioConta, setTipoRadioConta] = useState("");
  const [tiposRadio, setTiposRadio] = useState<TipoRadio[]>([]);
  const [radioPerfil, setRadioPerfil] = useState<RadioPerfil | null>(null);

  useEffect(() => {
    apiFetch<RadioPerfil>("/config/radio")
      .then((radio) => {
        setTipoRadioConta(radio.tipo_radio);
        setRadioPerfil(radio);
      })
      .catch(() => {});
    apiFetch<TipoRadio[]>("/config/tipos-radio")
      .then(setTiposRadio)
      .catch(() => {});
  }, []);

  const labelTipoRadioConta = tiposRadio.find((t) => t.value === tipoRadioConta)?.label;

  function carregar() {
    setCarregando(true);
    apiFetch<Radialista[]>("/config/radialistas")
      .then(async (lista) => {
        setRadialistas(lista);
        const entradas = await Promise.all(
          lista.map(async (r) => {
            try {
              const programas = await apiFetch<Programa[]>(`/config/radialistas/${r.id}/programas`);
              return [r.id, programas] as const;
            } catch {
              return [r.id, []] as const;
            }
          })
        );
        setProgramasPorRadialista(Object.fromEntries(entradas));
      })
      .catch((err) => setErro(err instanceof ApiError ? err.message : "Erro ao carregar radialistas"))
      .finally(() => setCarregando(false));
  }

  useEffect(() => {
    carregar();
  }, []);

  async function gerarPreview() {
    if (!descricaoIA.trim() && !tipoRadioConta) return;
    setGerandoIA(true);
    setErroIA("");
    try {
      const preview = await apiFetch<ConfiguracaoIAPreview>("/config/radialistas/gerar-ia/preview", {
        method: "POST",
        body: JSON.stringify({ descricao: descricaoIA.trim() }),
      });
      setProposta(preview);
      setRadialistaEdit(preview.radialista);
      setProgramaEdit(preview.programa);
      setGeracaoId(preview.geracao_id);
    } catch (err) {
      setErroIA(err instanceof ApiError ? err.message : "Erro ao gerar configuração com IA");
    } finally {
      setGerandoIA(false);
    }
  }

  function fecharModalIA() {
    setModalIAAberto(false);
    setProposta(null);
    setRadialistaEdit(null);
    setProgramaEdit(null);
    setGeracaoId(null);
    setInstrucaoAjuste("");
  }

  async function refinar(escopo: "persona" | "programa" | "ajuste", instrucao?: string) {
    if (!radialistaEdit || !programaEdit) return;
    setProcessandoRefinamento(true);
    setErroIA("");
    try {
      const preview = await apiFetch<ConfiguracaoIAPreview>("/config/radialistas/gerar-ia/refinar", {
        method: "POST",
        body: JSON.stringify({
          descricao: descricaoIA.trim(),
          escopo,
          instrucao: instrucao ?? "",
          radialista: radialistaEdit,
          programa: programaEdit,
        }),
      });
      setProposta(preview);
      setRadialistaEdit(preview.radialista);
      setProgramaEdit(preview.programa);
      setGeracaoId(preview.geracao_id);
      if (escopo === "ajuste") setInstrucaoAjuste("");
    } catch (err) {
      setErroIA(err instanceof ApiError ? err.message : "Erro ao refinar com IA");
    } finally {
      setProcessandoRefinamento(false);
    }
  }

  async function confirmarCriacao() {
    if (!radialistaEdit || !programaEdit) return;
    setCriandoFinal(true);
    setErroIA("");
    try {
      const criado = await apiFetch<ConfiguracaoIA>("/config/radialistas/gerar-ia/commit", {
        method: "POST",
        body: JSON.stringify({ radialista: radialistaEdit, programa: programaEdit, geracao_id: geracaoId }),
      });
      setRadialistaAtualId(criado.radialista.id);
      window.location.href = `/radialista/${criado.radialista.id}`;
    } catch (err) {
      if (err instanceof ApiError && err.status === 402) {
        fecharModalIA();
        setMensagemUpgrade(err.message);
      } else {
        setErroIA(err instanceof ApiError ? err.message : "Erro ao criar radialista");
      }
      setCriandoFinal(false);
    }
  }

  return (
    <AppShell title="Radialistas" maxWidthClassName="max-w-4xl">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-5">
        <p className="text-sm text-fg/65">
          Seus locutores de IA. Clique num deles pra editar a persona, a voz e os programas.
        </p>
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={() => {
              setErroIA("");
              setDescricaoIA("");
              setModalIAAberto(true);
            }}
            className="rounded-lg border border-amber/40 px-4 py-2.5 text-sm font-medium text-amber-text hover:bg-amber/10 whitespace-nowrap"
          >
            ✨ Gerar com IA
          </button>
          <Link
            href="/radialista/novo"
            className="rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-ink hover:bg-brand-600 whitespace-nowrap"
          >
            + Novo radialista
          </Link>
        </div>
      </div>

      {erro && <p className="text-sm text-rust-text mb-4">{erro}</p>}

      {carregando ? (
        <p className="flex items-center gap-2 text-sm text-fg/65">
          <LocufySpin size={16} /> Carregando...
        </p>
      ) : radialistas.length === 0 ? (
        <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6">
          <p className="text-sm text-fg/65">Nenhum radialista ainda. Crie o primeiro para começar.</p>
          <p className="text-sm text-fg/65 mt-1">Depois, você cria os programas dele e conecta o WhatsApp.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {radialistas.map((r) => {
            const programas = programasPorRadialista[r.id] ?? [];
            const ativos = programas.filter((p) => p.ativo).length;
            return (
              <Link
                key={r.id}
                href={`/radialista/${r.id}`}
                onClick={() => setRadialistaAtualId(r.id)}
                className="flex items-center justify-between gap-3 bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-5 hover:border-amber/40 transition-colors"
              >
                <div>
                  <h2 className="font-display text-base font-bold text-fg">{r.nome_locutor || `Radialista #${r.id}`}</h2>
                  <p className="text-xs text-fg/65 mt-1">
                    Atende pelo WhatsApp da rádio ·{" "}
                    {programas.length === 0
                      ? "nenhum programa cadastrado"
                      : `${ativos} programa${ativos === 1 ? "" : "s"} ativo${ativos === 1 ? "" : "s"}${
                          programas.length > ativos ? ` (${programas.length - ativos} pausado${programas.length - ativos === 1 ? "" : "s"})` : ""
                        }`}
                  </p>
                </div>
                <span className="text-xs font-medium text-amber-text shrink-0">Editar →</span>
              </Link>
            );
          })}
        </div>
      )}

      {modalIAAberto && !proposta && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/50 px-4"
          onClick={() => !gerandoIA && fecharModalIA()}
        >
          <div
            className="w-full max-w-lg rounded-2xl border border-border-strong bg-surface p-6 shadow-theme-xs"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="font-display text-base font-bold text-fg mb-2">Gerar radialista com IA</h2>
            <p className="text-sm text-fg/70 mb-4">
              Descreva o gênero musical, o tom e o público do programa. A IA preenche a persona do
              locutor, os tópicos, a estrutura de blocos e todo o resto — depois é só revisar e ajustar,
              nada é criado ainda.
            </p>
            {tipoRadioConta ? (
              <p className="text-xs font-medium text-amber-text bg-amber/10 rounded-lg px-3 py-2 mb-3">
                Baseado no perfil: {labelTipoRadioConta ?? tipoRadioConta}
              </p>
            ) : (
              <p className="text-xs text-fg/65 bg-paper/5 rounded-lg px-3 py-2 mb-3">
                Nenhum tipo de rádio configurado — a IA vai depender só da descrição.{" "}
                <Link href="/configuracoes" className="font-medium text-amber-text hover:underline">
                  Configurar tipo de rádio →
                </Link>
              </p>
            )}
            <textarea
              value={descricaoIA}
              onChange={(e) => setDescricaoIA(e.target.value)}
              disabled={gerandoIA}
              rows={4}
              placeholder="Descrição (opcional). Ex: programa de manhã, mais animado, com bloco de recado"
              className="w-full rounded-lg border border-border-strong bg-bg px-3 py-2.5 text-sm text-fg placeholder:text-fg/65 focus:outline-none focus:ring-2 focus:ring-amber/40 disabled:opacity-60"
            />
            <div className="mt-2 space-y-1.5">
              {[
                ["Gênero", CHIPS_GENERO],
                ["Período", CHIPS_PERIODO],
                ["Público", CHIPS_PUBLICO],
              ].map(([grupo, chips]) => (
                <div key={grupo as string} className="flex flex-wrap items-center gap-1.5">
                  <span className="text-xs text-fg/50 shrink-0">{grupo}:</span>
                  {(chips as string[]).map((chip) => (
                    <button
                      key={chip}
                      type="button"
                      disabled={gerandoIA}
                      onClick={() => setDescricaoIA((atual) => adicionarChip(atual, chip))}
                      className="rounded-full border border-border-strong px-2.5 py-0.5 text-xs text-fg/70 hover:border-amber/40 hover:text-amber-text disabled:opacity-60"
                    >
                      {chip}
                    </button>
                  ))}
                </div>
              ))}
            </div>
            {(radioPerfil?.nome_radio || radioPerfil?.frequencia || radioPerfil?.cidade) && (
              <p className="text-xs text-fg/50 mt-3">
                Vou considerar: {[radioPerfil.nome_radio, radioPerfil.frequencia, radioPerfil.cidade]
                  .filter(Boolean)
                  .join(", ")}
                {radialistas.length > 0 &&
                  ` e ${radialistas.length} radialista${radialistas.length === 1 ? "" : "s"} já cadastrado${radialistas.length === 1 ? "" : "s"}`}
                .
              </p>
            )}
            {erroIA && <p className="text-sm text-rust-text mt-2">{erroIA}</p>}
            <div className="flex justify-end gap-3 mt-5">
              <button
                type="button"
                onClick={fecharModalIA}
                disabled={gerandoIA}
                className="rounded-lg px-4 py-2.5 text-sm font-medium text-fg/60 hover:text-fg disabled:opacity-60"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={gerarPreview}
                disabled={gerandoIA || (!descricaoIA.trim() && !tipoRadioConta)}
                className="rounded-lg bg-amber px-4 py-2.5 text-sm font-medium text-ink hover:bg-amber/90 disabled:opacity-60"
              >
                {gerandoIA ? "Gerando..." : "Gerar"}
              </button>
            </div>
          </div>
        </div>
      )}

      {modalIAAberto && proposta && radialistaEdit && programaEdit && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/50 px-4 py-8">
          <div
            className="w-full max-w-2xl max-h-full overflow-y-auto rounded-2xl border border-border-strong bg-surface p-6 shadow-theme-xs"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="font-display text-base font-bold text-fg mb-1">Revise antes de criar</h2>
            <p className="text-sm text-fg/70 mb-4">
              Nada foi criado ainda. Ajuste o que quiser e confirme -- o roteiro completo do programa
              (estrutura de blocos, tópicos, notícias etc.) você continua editando depois de criar.
            </p>

            {proposta.campos_corrigidos.length > 0 && (
              <p className="text-xs font-medium text-amber-text bg-amber/10 rounded-lg px-3 py-2 mb-4">
                Estes campos vieram com erro e usaram um valor padrão -- confira:{" "}
                {proposta.campos_corrigidos.join(", ")}
              </p>
            )}
            {proposta.avisos.length > 0 && (
              <ul className="text-xs font-medium text-rust-text bg-rust/10 rounded-lg px-3 py-2 mb-4 list-disc list-inside space-y-0.5">
                {proposta.avisos.map((aviso, i) => (
                  <li key={i}>{aviso}</li>
                ))}
              </ul>
            )}

            <h3 className="font-mono text-xs uppercase tracking-wide text-amber-text mb-2">Locutor</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-fg/80 mb-1.5">Nome do locutor</label>
                <input
                  className="w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
                  value={radialistaEdit.nome_locutor}
                  onChange={(e) => setRadialistaEdit({ ...radialistaEdit, nome_locutor: e.target.value })}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-fg/80 mb-1.5">Voz</label>
                <VoiceSelect
                  value={radialistaEdit.voz_id}
                  onChange={(vozId) => setRadialistaEdit({ ...radialistaEdit, voz_id: vozId })}
                />
              </div>
            </div>
            <div className="mb-5">
              <label className="block text-sm font-medium text-fg/80 mb-1.5">Personalidade</label>
              <textarea
                rows={3}
                className="w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
                value={radialistaEdit.personalidade}
                onChange={(e) => setRadialistaEdit({ ...radialistaEdit, personalidade: e.target.value })}
              />
            </div>

            <hr className="border-border mb-4" />
            <h3 className="font-mono text-xs uppercase tracking-wide text-amber-text mb-2">Programa</h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-fg/80 mb-1.5">Nome do programa</label>
                <input
                  className="w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
                  value={programaEdit.nome}
                  onChange={(e) => setProgramaEdit({ ...programaEdit, nome: e.target.value })}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-fg/80 mb-1.5">Início</label>
                <input
                  type="time"
                  className="w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
                  value={programaEdit.horario_inicio.slice(0, 5)}
                  onChange={(e) => setProgramaEdit({ ...programaEdit, horario_inicio: `${e.target.value}:00` })}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-fg/80 mb-1.5">Fim</label>
                <input
                  type="time"
                  className="w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
                  value={programaEdit.horario_fim.slice(0, 5)}
                  onChange={(e) => setProgramaEdit({ ...programaEdit, horario_fim: `${e.target.value}:00` })}
                />
              </div>
            </div>
            <div className="mb-4">
              <label className="block text-sm font-medium text-fg/80 mb-1.5">Dias</label>
              <div className="flex flex-wrap gap-1.5">
                {DIAS_SEMANA_LABEL.map((label, dia) => (
                  <button
                    key={label}
                    type="button"
                    onClick={() =>
                      setProgramaEdit({ ...programaEdit, dias_semana: alternarDia(programaEdit.dias_semana, dia) })
                    }
                    className={`rounded-full px-3 py-1 text-xs font-medium border ${
                      programaEdit.dias_semana.includes(dia)
                        ? "bg-brand-500 text-ink border-brand-500"
                        : "bg-transparent text-fg/65 border-border-strong"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <p className="text-xs text-fg/65 mt-1">Nenhum dia marcado = todos os dias.</p>
            </div>
            <div className="mb-4">
              <label className="block text-sm font-medium text-fg/80 mb-1.5">Tom</label>
              <textarea
                rows={2}
                className="w-full rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20"
                value={programaEdit.tom}
                onChange={(e) => setProgramaEdit({ ...programaEdit, tom: e.target.value })}
              />
            </div>
            <TagInput
              label="Tópicos permitidos"
              tags={programaEdit.topicos_permitidos}
              onChange={(tags) => setProgramaEdit({ ...programaEdit, topicos_permitidos: tags })}
            />
            <TagInput
              label="Gêneros musicais"
              tags={programaEdit.generos_musicais}
              onChange={(tags) => setProgramaEdit({ ...programaEdit, generos_musicais: tags })}
            />
            {programaEdit.estrutura_blocos.length > 0 && (
              <div className="mb-4">
                <label className="block text-sm font-medium text-fg/80 mb-1.5">
                  Roteiro sugerido (dá pra ajustar depois de criar)
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {programaEdit.estrutura_blocos.map((bloco, i) => (
                    <span
                      key={`${bloco}-${i}`}
                      className="inline-flex items-center rounded-full bg-amber/10 text-amber-text border border-amber/25 px-2.5 py-0.5 text-xs"
                    >
                      {rotuloBloco(bloco)}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <hr className="border-border mb-4" />
            <h3 className="font-mono text-xs uppercase tracking-wide text-amber-text mb-2">Refinar (opcional)</h3>
            <div className="flex flex-wrap gap-2 mb-3">
              <button
                type="button"
                onClick={() => refinar("persona")}
                disabled={processandoRefinamento || criandoFinal}
                className="rounded-lg border border-border-strong px-3 py-1.5 text-xs font-medium text-fg hover:bg-paper/10 disabled:opacity-60"
              >
                Gerar outro nome/voz
              </button>
              <button
                type="button"
                onClick={() => refinar("programa")}
                disabled={processandoRefinamento || criandoFinal}
                className="rounded-lg border border-border-strong px-3 py-1.5 text-xs font-medium text-fg hover:bg-paper/10 disabled:opacity-60"
              >
                Gerar outra grade
              </button>
            </div>
            <div className="flex flex-wrap gap-2 mb-4">
              <input
                type="text"
                value={instrucaoAjuste}
                onChange={(e) => setInstrucaoAjuste(e.target.value)}
                disabled={processandoRefinamento || criandoFinal}
                placeholder="Ex.: mais sério, tira o bloco de notícia, começa às seis"
                className="flex-1 min-w-[220px] rounded-lg border border-border-strong bg-bg px-3 py-2 text-sm text-fg placeholder:text-fg/65 focus:outline-none focus:border-amber/50 focus:ring-2 focus:ring-amber/20 disabled:opacity-60"
              />
              <button
                type="button"
                onClick={() => refinar("ajuste", instrucaoAjuste)}
                disabled={processandoRefinamento || criandoFinal || !instrucaoAjuste.trim()}
                className="rounded-lg border border-border-strong px-3 py-2 text-sm font-medium text-fg hover:bg-paper/10 disabled:opacity-60"
              >
                {processandoRefinamento ? "Ajustando..." : "Ajustar"}
              </button>
            </div>

            {erroIA && <p className="text-sm text-rust-text mt-2">{erroIA}</p>}
            <div className="flex flex-wrap justify-end gap-3 mt-5">
              <button
                type="button"
                onClick={fecharModalIA}
                disabled={criandoFinal}
                className="rounded-lg px-4 py-2.5 text-sm font-medium text-fg/60 hover:text-fg disabled:opacity-60"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={() => {
                  setProposta(null);
                  setRadialistaEdit(null);
                  setProgramaEdit(null);
                  gerarPreview();
                }}
                disabled={gerandoIA || criandoFinal || processandoRefinamento}
                className="rounded-lg border border-border-strong px-4 py-2.5 text-sm font-medium text-fg hover:bg-paper/10 disabled:opacity-60"
              >
                {gerandoIA ? "Gerando..." : "Gerar tudo de novo"}
              </button>
              <button
                type="button"
                onClick={confirmarCriacao}
                disabled={criandoFinal || gerandoIA || processandoRefinamento}
                className="rounded-lg bg-amber px-4 py-2.5 text-sm font-medium text-ink hover:bg-amber/90 disabled:opacity-60"
              >
                {criandoFinal ? "Criando..." : "Criar radialista e programa"}
              </button>
            </div>
          </div>
        </div>
      )}

      {mensagemUpgrade && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/50 px-4"
          onClick={() => setMensagemUpgrade("")}
        >
          <div
            className="w-full max-w-sm rounded-2xl border border-border-strong bg-surface p-6 shadow-theme-xs"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="font-display text-base font-bold text-fg mb-2">Limite de agentes atingido</h2>
            <p className="text-sm text-fg/70 mb-5">{mensagemUpgrade}</p>
            <p className="text-sm text-fg/70 mb-5">
              Adicione este agente agora por{" "}
              <span className="font-semibold text-fg">R$ {formatarReais(PRECO_AGENTE_ADICIONAL)}/mês</span>, sem
              trocar de plano — ele entra no ar assim que o pagamento confirmar.
            </p>
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setMensagemUpgrade("")}
                className="rounded-lg px-4 py-2.5 text-sm font-medium text-fg/60 hover:text-fg"
              >
                Fechar
              </button>
              <Link
                href="/billing"
                className="rounded-lg border border-border-strong px-4 py-2.5 text-sm font-medium text-fg hover:bg-paper/10"
              >
                Ver planos
              </Link>
              <button
                type="button"
                onClick={() => setCheckoutAgenteExtraAberto(true)}
                className="rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-ink hover:bg-brand-600"
              >
                Adicionar agente extra
              </button>
            </div>
          </div>
        </div>
      )}

      {checkoutAgenteExtraAberto && (
        <CheckoutModal
          open
          endpoint="/billing/agentes-extras/checkout"
          onClose={() => setCheckoutAgenteExtraAberto(false)}
          onSuccess={() => {
            setCheckoutAgenteExtraAberto(false);
            setMensagemUpgrade("");
            carregar();
          }}
        />
      )}
    </AppShell>
  );
}
