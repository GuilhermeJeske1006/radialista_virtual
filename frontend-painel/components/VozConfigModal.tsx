"use client";

import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "../lib/api";
import { ConfiguracaoVoz } from "../lib/types";
import Modal from "./Modal";

export default function VozConfigModal({ vozId, onFechar, onAtualizada }: { vozId: string | null; onFechar: () => void; onAtualizada: () => void }) {
  const [config, setConfig] = useState<ConfiguracaoVoz | null>(null);
  const [pronuncias, setPronuncias] = useState("");
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const caminho = `/tts/configuracao-voz/${encodeURIComponent(vozId ?? "padrao")}`;
  useEffect(() => {
    let ativo = true;
    apiFetch<ConfiguracaoVoz>(caminho).then((dados) => {
      if (!ativo) return;
      setConfig(dados); setPronuncias(Object.entries(dados.pronuncias).map(([a, b]) => `${a} = ${b}`).join("\n"));
    }).catch((e) => { if (ativo) setErro(e instanceof ApiError ? e.message : "Falha ao carregar voz."); });
    return () => { ativo = false; };
  }, [caminho]);

  async function atualizar() {
    setOcupado(true); setErro("");
    try {
      const dados = await apiFetch<ConfiguracaoVoz>(`${caminho}?atualizar=true`);
      setConfig((atual) => atual ? { ...atual, categoria: dados.categoria, idioma: dados.idioma, sotaque: dados.sotaque, requer_verificacao: dados.requer_verificacao } : dados);
      onAtualizada();
    } catch (e) { setErro(e instanceof ApiError ? e.message : "Falha ao atualizar status."); }
    finally { setOcupado(false); }
  }

  async function salvar() {
    if (!config) return;
    setErro("");
    const mapa: Record<string, string> = {};
    for (const linha of pronuncias.split("\n").filter((l) => l.trim())) {
      const pos = linha.indexOf("=");
      const termo = linha.slice(0, pos).trim();
      const leitura = linha.slice(pos + 1).trim();
      if (pos < 1 || !termo || !leitura || Object.keys(mapa).some((k) => k.toLowerCase() === termo.toLowerCase())) {
        setErro("Use um termo único por linha no formato: termo = pronúncia."); return;
      }
      mapa[termo] = leitura;
    }
    setOcupado(true);
    try {
      await apiFetch(caminho, { method: "PATCH", body: JSON.stringify({ modelo: config.modelo, perfil: config.perfil, formato: config.formato, pronuncias: mapa }) });
      onAtualizada(); onFechar();
    } catch (e) { setErro(e instanceof ApiError ? e.message : "Falha ao salvar voz."); }
    finally { setOcupado(false); }
  }

  const campo = "mt-1 block w-full rounded-lg border border-border-strong bg-bg p-2 text-sm";
  return <Modal open onClose={() => { if (!ocupado) onFechar(); }} title="Ajustar voz" maxWidthClassName="max-w-xl">
    <div role="dialog" aria-label="Ajustar voz" aria-modal="true" className="space-y-4">
      {!config && !erro && <p role="status">Carregando…</p>}
      {config && <>
        <p className="text-sm text-fg/65">Tipo: {({ professional: "profissional", cloned: "clonagem instantânea", premade: "catálogo", generated: "criada por descrição" } as Record<string, string>)[config.categoria] ?? "não confirmado"}{config.idioma ? ` · ${config.idioma}` : ""}{config.sotaque ? ` · ${config.sotaque}` : ""}</p>
        {config.requer_verificacao && <p role="status" className="text-sm text-amber-text">Voz aguardando verificação. Conclua a verificação na ElevenLabs e atualize o status aqui.</p>}
        <button type="button" onClick={atualizar} disabled={ocupado} className="text-sm text-amber-text disabled:opacity-50">Atualizar status da voz</button>
        <label className="block text-sm">Modelo de voz
          <select className={campo} value={config.modelo ?? ""} disabled={ocupado} onChange={(e) => setConfig({ ...config, modelo: e.target.value || null })}>
            <option value="">Padrão do servidor</option><option value="eleven_v3">Eleven v3 · expressivo</option><option value="eleven_multilingual_v2">Multilingual v2 · consistente</option><option value="eleven_flash_v2_5">Flash v2.5 · geração rápida</option>
          </select>
        </label>
        <label className="block text-sm">Interpretação
          <select className={campo} value={config.perfil} disabled={ocupado} onChange={(e) => setConfig({ ...config, perfil: e.target.value as ConfiguracaoVoz["perfil"] })}>
            <option value="atual">Atual · acompanha o tipo de bloco</option><option value="natural">Neutra · ritmo normal e ajustes fixos</option>
          </select>
        </label>
        <label className="block text-sm">Qualidade do arquivo
          <select className={campo} value={config.formato} disabled={ocupado} onChange={(e) => setConfig({ ...config, formato: e.target.value as ConfiguracaoVoz["formato"] })}>
            <option value="mp3_44100_128">MP3 128 kbps · padrão</option><option value="mp3_44100_192">MP3 192 kbps · exige plano compatível na ElevenLabs</option>
          </select>
        </label>
        <label className="block text-sm">Pronúncias de nomes e marcas
          <textarea className={campo} rows={4} value={pronuncias} disabled={ocupado} onChange={(e) => setPronuncias(e.target.value)} placeholder={"Locufy = Locufai\nAC/DC = êi ci di ci"} />
        </label>
        <p className="text-xs text-fg/65">Até 30 termos, um por linha: termo = pronúncia. As substituições valem só para o áudio desta voz e desta conta. Ouça e compare antes de escolher a interpretação; a neutra é uma alternativa de teste.</p>
        <p className="text-xs text-fg/65">As mudanças valem para novas gerações. Reinicie o ao vivo para descartar áudios já preparados.</p>
        <button type="button" onClick={salvar} disabled={ocupado} className="rounded-lg bg-amber px-4 py-2 text-sm text-ink disabled:opacity-50">{ocupado ? "Aguarde…" : "Salvar ajustes"}</button>
      </>}
      {erro && <p role="alert" className="text-sm text-rust-text">{erro}</p>}
    </div>
  </Modal>;
}
