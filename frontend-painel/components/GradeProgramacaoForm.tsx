"use client";

import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "../lib/api";
import { CategoriaVinheta, normalizarPrograma, Patrocinador, Programa } from "../lib/types";
import { janelaSegundos } from "../lib/duracaoBloco";
import { BibliotecaAudioItem } from "../lib/bibliotecaAudio";
import RadialistasProgramaSection from "./RadialistasProgramaSection";
import RoteiroBlocosEditor from "./RoteiroBlocosEditor";
import { LocufySpin } from "./LocufyLogo";

function semCamposSistema(p: Programa) {
  const { id, radio_config_id, ...dados } = p;
  return dados;
}

type Props = {
  programaId: number;
};

export default function GradeProgramacaoForm({ programaId }: Props) {
  const [programa, setPrograma] = useState<Programa | null>(null);
  const [patrocinadores, setPatrocinadores] = useState<Patrocinador[]>([]);
  const [vinhetas, setVinhetas] = useState<BibliotecaAudioItem[]>([]);
  const [categorias, setCategorias] = useState<CategoriaVinheta[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [mensagem, setMensagem] = useState("");
  const [erro, setErro] = useState("");

  useEffect(() => {
    setCarregando(true);
    apiFetch<Programa>(`/config/programas/${programaId}`)
      .then((dados) => setPrograma(normalizarPrograma(dados)))
      .catch((err) => setErro(err instanceof ApiError ? err.message : "Erro ao carregar programa"))
      .finally(() => setCarregando(false));
    apiFetch<Patrocinador[]>("/patrocinadores")
      .then(setPatrocinadores)
      .catch(() => setPatrocinadores([]));
    apiFetch<BibliotecaAudioItem[]>("/biblioteca-audio")
      .then(setVinhetas)
      .catch(() => setVinhetas([]));
    apiFetch<CategoriaVinheta[]>("/categorias-vinheta")
      .then(setCategorias)
      .catch(() => setCategorias([]));
  }, [programaId]);

  function atualizarBlocos(blocos: string[]) {
    if (!programa) return;
    setPrograma({ ...programa, estrutura_blocos: blocos });
  }

  async function salvar() {
    if (!programa) return;
    setSalvando(true);
    setErro("");
    setMensagem("");
    try {
      const atualizado = await apiFetch<Programa>(`/config/programas/${programaId}`, {
        method: "PUT",
        body: JSON.stringify(semCamposSistema(programa)),
      });
      setPrograma(normalizarPrograma(atualizado));
      setMensagem("Programação salva.");
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Erro ao salvar");
    } finally {
      setSalvando(false);
    }
  }

  if (carregando) {
    return (
      <p className="flex items-center gap-2 text-sm text-fg/65">
        <LocufySpin size={16} /> Carregando...
      </p>
    );
  }

  if (!programa) {
    return <p className="text-sm text-rust-text">{erro || "Programa não encontrado."}</p>;
  }

  return (
    <div className="bg-surface rounded-2xl border border-border-strong shadow-theme-xs p-6">
      <h2 className="font-display text-lg font-bold text-fg mb-1">Roteiro do programa · {programa.nome}</h2>
      <p className="text-sm text-fg/65 mb-5">
        Arraste vinhetas, propagandas e blocos automáticos da paleta pra sequência (ou clique pra adicionar no
        fim). O ao vivo segue essa sequência em loop. Durações abaixo são estimativas -- o motor real varia por
        prosódia e a IA pode inserir blocos extra.
      </p>

      {erro && <p className="text-sm text-rust-text mb-4">{erro}</p>}
      {mensagem && <p className="text-sm text-teal-text mb-4">{mensagem}</p>}

      <RoteiroBlocosEditor
        blocos={programa.estrutura_blocos}
        onChange={atualizarBlocos}
        patrocinadores={patrocinadores}
        vinhetas={vinhetas}
        categorias={categorias}
        janelaSegundos={janelaSegundos(programa.horario_inicio, programa.horario_fim)}
      />

      <button
        type="button"
        onClick={salvar}
        disabled={salvando}
        className="mt-4 rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-ink hover:bg-brand-600 disabled:opacity-60"
      >
        {salvando ? "Salvando..." : "Salvar programação"}
      </button>

      <hr className="border-border my-5" />
      <section>
        <h3 className="font-mono text-xs uppercase tracking-wide text-amber-text mb-2">Elenco do programa</h3>
        <p className="text-xs text-fg/65 mb-2">
          Quem participa do diálogo -- o motor já monta a conversa entre todos automaticamente, sem precisar
          apontar radialista por bloco.
        </p>
        <RadialistasProgramaSection programaId={programaId} />
      </section>
    </div>
  );
}
