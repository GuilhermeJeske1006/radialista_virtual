"use client";

import { useEffect, useId, useState } from "react";
import { apiFetch } from "../lib/api";
import {
  CatalogoCombinacoes,
  Combinacao,
  HorarioPrograma,
  ModeloIA,
  consumoMensalEstimado,
  exibicoesPorMes,
  horasPorDia,
  nomeModelo,
  reais,
  reaisPreciso,
} from "../lib/combinacoes";

type Props = {
  value: string | null;
  onChange: (combinacao: Combinacao | null) => void;
  // Com o horário do programa, mostra a estimativa mensal dele; sem, o cenário de referência.
  programa?: HorarioPrograma | null;
  disabled?: boolean;
  // Catálogo já carregado pela tela (Assinatura) evita buscar de novo.
  catalogo?: CatalogoCombinacoes;
  // Na própria tela de Assinatura não faz sentido dizer "troque depois em Assinatura".
  dicaTroca?: boolean;
};

function Modelo({ id }: { id: string }) {
  return <span translate="no">{nomeModelo(id)}</span>;
}

function Estimativa({ c, programa, horasReferencia }: { c: Combinacao; programa?: HorarioPrograma | null; horasReferencia: number }) {
  if (programa) {
    return (
      <p className="text-xs font-medium text-fg tabular-nums">
        Este programa: ≈ {reais(consumoMensalEstimado(c, programa))}/mês de uso (
        {horasPorDia(programa).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} h ×{" "}
        {programa.data_especifica ? "1 exibição" : `~${Math.round(exibicoesPorMes(programa))} exibições`})
      </p>
    );
  }
  if (c.preco_mes_referencia_brl == null) return null;
  return (
    <p className="text-xs font-medium text-fg tabular-nums">
      Programa de 1 h por dia: ≈ {reais(c.preco_mes_referencia_brl)}/mês de uso ({horasReferencia} h no mês)
    </p>
  );
}

const FUNCOES = [
  { funcao: "texto", titulo: "Modelos de texto", papel: "escrevem o que o locutor fala" },
  { funcao: "voz", titulo: "Modelos de voz", papel: "transformam esse texto em áudio" },
] as const;

function GuiaModelos({ modelos }: { modelos: Record<string, ModeloIA> }) {
  const entradas = Object.entries(modelos);
  if (entradas.length === 0) return null;
  return (
    <div className="grid gap-3 rounded-xl bg-fg/5 p-3 text-xs @2xl:grid-cols-2">
      {FUNCOES.map(({ funcao, titulo, papel }) => {
        const lista = entradas.filter(([, m]) => m.funcao === funcao);
        if (lista.length === 0) return null;
        return (
          <div key={funcao}>
            <p className="font-semibold text-fg">
              {titulo} <span className="font-normal text-fg/65">— {papel}</span>
            </p>
            <dl className="mt-1 space-y-1">
              {lista.map(([id, m]) => (
                <div key={id}>
                  <dt className="font-medium text-fg">
                    <Modelo id={id} />
                  </dt>
                  <dd className="text-fg/75">{m.descricao}</dd>
                </div>
              ))}
            </dl>
          </div>
        );
      })}
    </div>
  );
}

function Custo({ c }: { c: Combinacao }) {
  const partes = c.custo_hora_brl;
  if (!partes && c.preco_mil_caracteres_brl == null) return null;
  return (
    <details className="group rounded-lg bg-fg/5 px-3 py-2 text-xs text-fg/80">
      <summary className="cursor-pointer font-medium text-fg hover:text-acento-claro">Ver composição do custo</summary>
      <div className="mt-2 space-y-2">
        {partes && (
          <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-0.5 tabular-nums">
            <dt>Texto do locutor (<Modelo id={c.modelo_texto} />)</dt>
            <dd className="text-right">{reais(partes.texto)}/h</dd>
            <dt>Classificações automáticas (tom, tema, músicas)</dt>
            <dd className="text-right">{reais(partes.classificacao)}/h</dd>
            <dt>Voz (<Modelo id={c.modelo_voz} />)</dt>
            <dd className="text-right">{reais(partes.voz)}/h</dd>
            <dt className="font-semibold text-fg">Total por hora de programa</dt>
            <dd className="text-right font-semibold text-fg">{reais(c.preco_hora_brl)}</dd>
          </dl>
        )}
        {c.preco_mil_caracteres_brl != null && (
          <p className="tabular-nums">Voz: {reais(c.preco_mil_caracteres_brl)} por mil caracteres (≈ 1 minuto de fala).</p>
        )}
      </div>
    </details>
  );
}

export default function CombinacaoSelect({ value, onChange, programa, disabled, catalogo: catalogoInicial, dicaTroca = true }: Props) {
  const [catalogo, setCatalogo] = useState<CatalogoCombinacoes | null>(catalogoInicial ?? null);
  const [erro, setErro] = useState(false);
  // Grupo de rádio próprio por instância: duas listas na mesma tela não se misturam.
  const grupo = useId();

  useEffect(() => {
    let ativo = true;
    function carregado(c: CatalogoCombinacoes) {
      setCatalogo(c);
      // Sem escolha prévia, parte da recomendada; catálogo vazio mantém os modelos padrão.
      if (!c.combinacoes.some((item) => item.id === value)) {
        onChange(c.combinacoes.find((item) => item.recomendada) ?? c.combinacoes[0] ?? null);
      }
    }
    if (catalogoInicial) {
      carregado(catalogoInicial);
      return;
    }
    apiFetch<CatalogoCombinacoes>("/billing/combinacoes")
      .then((c) => ativo && carregado(c))
      .catch(() => ativo && setErro(true));
    return () => {
      ativo = false;
    };
    // Carrega uma vez; value inicial só decide a pré-seleção.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (erro) {
    return (
      <p role="status" className="text-xs text-fg/65">
        Não foi possível carregar as combinações de modelos. O locutor será gerado com a configuração padrão.
      </p>
    );
  }
  if (!catalogo) {
    return <p role="status" className="text-xs text-fg/65">Carregando combinações de modelos…</p>;
  }
  if (catalogo.combinacoes.length === 0) {
    return (
      <p role="status" className="text-xs text-fg/65">
        As combinações de modelos ficam disponíveis após a publicação das tarifas. O locutor usa a configuração padrão.
      </p>
    );
  }

  const horasReferencia = catalogo.horas_mes_referencia ?? 30;
  // Exemplos gravados com o mesmo pedido: mostra uma vez só, acima dos cards.
  const pedidos = new Set(catalogo.combinacoes.flatMap((c) => (c.exemplo ? [c.exemplo.pedido] : [])));
  const pedidoComum = pedidos.size === 1 ? [...pedidos][0] : null;
  return (
    <fieldset disabled={disabled} className="@container space-y-2">
      <legend className="text-sm font-medium text-fg">Como seu locutor escreve e fala</legend>
      <p className="text-xs text-fg/65 mb-1">
        Seu locutor usa dois modelos de IA: um de texto, que escreve o que ele fala, e um de voz, que transforma esse
        texto em áudio. Cada combinação junta um de cada.{dicaTroca && " Dá pra trocar depois, por programa, em Assinatura."}
      </p>
      {catalogo.modelos && <GuiaModelos modelos={catalogo.modelos} />}
      {pedidoComum && (
        <p className="text-xs text-fg/80">
          Para comparar, todas receberam o mesmo pedido: <span className="italic">“{pedidoComum}”</span> Ouça o áudio e
          leia o texto que cada uma escreveu antes de escolher.
        </p>
      )}
      {/* Duas colunas quando o espaço permite comparar lado a lado (onboarding, página de assinatura). */}
      <div className="grid gap-2 @2xl:grid-cols-2">
        {catalogo.combinacoes.map((c) => {
          const selecionada = c.id === value;
          return (
            <div
              key={c.id}
              className={`space-y-2 rounded-xl border p-3 ${
                selecionada ? "border-acento-claro bg-acento/5" : "border-border-strong hover:border-acento-claro/40"
              }`}
            >
              <label className="flex cursor-pointer items-start gap-2 rounded-lg focus-within:ring-2 focus-within:ring-acento-claro/40">
                <input
                  type="radio"
                  name={grupo}
                  value={c.id}
                  checked={selecionada}
                  onChange={() => onChange(c)}
                  className="accent-brand-500 mt-1 h-4 w-4 shrink-0"
                />
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-baseline justify-between gap-x-3">
                    <span className="text-sm font-semibold text-fg">
                      {c.nome}
                      {c.recomendada && (
                        <span className="ml-2 rounded-full bg-acento/15 px-2 py-0.5 text-[11px] font-medium text-acento-claro">
                          Recomendada
                        </span>
                      )}
                    </span>
                    <span className="text-sm font-semibold text-fg tabular-nums">≈ {reais(c.preco_hora_brl)} / hora de programa</span>
                  </span>
                  <span className="block text-xs text-fg/65 mt-0.5">
                    Texto: <Modelo id={c.modelo_texto} /> · Voz: <Modelo id={c.modelo_voz} />
                  </span>
                  <span className="block text-xs text-fg/80 mt-1">{c.descricao}</span>
                </span>
              </label>
              <div className="space-y-2 pl-6">
                {c.exemplo && (
                  <div className="space-y-1.5">
                    <audio
                      controls
                      preload="none"
                      src={c.exemplo.audio_url}
                      className="h-9 w-full"
                      aria-label={`Exemplo da combinação ${c.nome}`}
                    />
                    <p className="text-xs text-fg/65 tabular-nums">
                      Exemplo: anúncio de música pedida por ouvinte · {Math.round(c.exemplo.duracao_segundos)} s · custaria{" "}
                      {reaisPreciso(c.exemplo.preco_brl)}
                    </p>
                    {!pedidoComum && <p className="text-xs text-fg/65">Pedido: {c.exemplo.pedido}</p>}
                    <blockquote className="whitespace-pre-wrap break-words border-l-2 border-acento-claro/40 pl-3 text-xs italic text-fg">
                      “{c.exemplo.texto}”
                    </blockquote>
                  </div>
                )}
                <Estimativa c={c} programa={programa} horasReferencia={horasReferencia} />
                <Custo c={c} />
                <p className="text-xs text-fg/60">Limitações: {c.limitacoes}</p>
              </div>
            </div>
          );
        })}
      </div>
      <p className="text-xs text-fg/60">
        {catalogo.premissas} Exemplos gravados com a voz padrão do Locufy; o seu locutor pode usar outra voz. Ouvir os
        exemplos é gratuito. Mensalidade de {reais(catalogo.mensalidade_brl)} à parte.
      </p>
    </fieldset>
  );
}
