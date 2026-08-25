"use client";

import { useEffect, useState } from "react";
import AppShell from "../../components/AppShell";
import Modal from "../../components/Modal";
import EditarRadialistaForm from "../../components/EditarRadialistaForm";
import EditarProgramaForm from "../../components/EditarProgramaForm";
import ProgramaSelector from "../../components/live/ProgramaSelector";
import PlaylistCentral from "../../components/live/PlaylistCentral";
import BibliotecaAudioPanel from "../../components/live/BibliotecaAudioPanel";
import CartwallPanel from "../../components/live/CartwallPanel";
import InteracoesPanel from "../../components/live/InteracoesPanel";
import { apiFetch, ApiError } from "../../lib/api";
import { BibliotecaAudioItem } from "../../lib/bibliotecaAudio";
import { CategoriaVinheta } from "../../lib/types";
import { useLiveEngine } from "../../hooks/useLiveEngine";

export default function LivePage() {
  const engine = useLiveEngine();

  const [pulso, setPulso] = useState(false);
  const [bibliotecaItens, setBibliotecaItens] = useState<BibliotecaAudioItem[]>([]);
  const [carregandoBiblioteca, setCarregandoBiblioteca] = useState(true);
  const [erroBiblioteca, setErroBiblioteca] = useState("");
  const [categorias, setCategorias] = useState<CategoriaVinheta[]>([]);
  const [modalRadialistaId, setModalRadialistaId] = useState<number | null>(null);
  const [modalPrograma, setModalPrograma] = useState<{ radialistaId: number; programaId: number | null } | null>(
    null
  );

  function carregarBiblioteca() {
    setCarregandoBiblioteca(true);
    apiFetch<BibliotecaAudioItem[]>("/biblioteca-audio")
      .then(setBibliotecaItens)
      .catch((err) => setErroBiblioteca(err instanceof ApiError ? err.message : "Erro ao carregar biblioteca"))
      .finally(() => setCarregandoBiblioteca(false));
  }

  useEffect(() => {
    carregarBiblioteca();
    apiFetch<CategoriaVinheta[]>("/categorias-vinheta")
      .then(setCategorias)
      .catch(() => setCategorias([]));
  }, []);

  function avisarNovaInteracao() {
    setPulso(true);
    setTimeout(() => setPulso(false), 700);
  }

  const nomeLocutor = engine.radialistaSelecionado?.nome_locutor || "Locutor";

  return (
    <AppShell title="Ao Vivo" maxWidthClassName="max-w-[1600px]">
      <div id="yt-live-player" className="pointer-events-none fixed left-[-9999px] top-0 h-px w-px overflow-hidden" />
      <div id="yt-bg-player" className="pointer-events-none fixed left-[-9999px] top-0 h-px w-px overflow-hidden" />

      {(engine.erro || erroBiblioteca || engine.abaEmSegundoPlano || engine.avisoGravacao) && (
        <div className="space-y-2 mb-4">
          {engine.erro && <p className="text-sm text-rust">{engine.erro}</p>}
          {erroBiblioteca && <p className="text-sm text-rust">{erroBiblioteca}</p>}
          {engine.abaEmSegundoPlano && (
            <p className="text-sm text-rust">
              Aba em segundo plano -- o navegador pode pausar o ao vivo. Mantenha esta aba aberta e em foco pra
              transmissao nao parar.
            </p>
          )}
          {engine.avisoGravacao && <p className="text-sm text-teal">{engine.avisoGravacao}</p>}
        </div>
      )}

      <div className="sticky top-16 z-20 -mx-4 sm:-mx-6 px-4 sm:px-6 py-3 bg-bg/95 backdrop-blur">
        <ProgramaSelector
          radialistas={engine.radialistas}
          programasTodos={engine.programasTodos}
          carregandoProgramas={engine.carregandoProgramas}
          programaId={engine.programaId}
          programaAtivo={engine.programaAtivo}
          gerandoFala={engine.gerandoFala}
          aoVivoAtivo={engine.aoVivoAtivo}
          programaSelecionado={engine.programaSelecionado}
          radialistaSelecionado={engine.radialistaSelecionado}
          programaSelecionadoNoAr={engine.programaSelecionadoNoAr}
          onSelecionar={(opcao) => engine.selecionarPrograma(opcao)}
          onIniciar={engine.iniciarPrograma}
          onPausar={() => engine.pausarPrograma(true)}
          onEditarRadialista={setModalRadialistaId}
          onEditarPrograma={(radialistaId, programaId) => setModalPrograma({ radialistaId, programaId })}
        />
      </div>

      {!engine.programaId ? (
        <section className="mt-5 bg-surface rounded-2xl border border-dashed border-border-strong p-10 text-center">
          <p className="text-sm text-fg/55">
            Selecione um programa acima para carregar os dados do locutor e liberar a transmissao.
          </p>
        </section>
      ) : (
        <div className="mt-5 grid grid-cols-1 xl:grid-cols-[280px_minmax(0,1fr)_340px] gap-5 items-start">
          <div className="space-y-5">
            <BibliotecaAudioPanel
              itens={bibliotecaItens}
              categorias={categorias}
              carregando={carregandoBiblioteca}
              onRecarregar={carregarBiblioteca}
              programaAtivo={engine.programaAtivo}
              onInserirNaTransmissao={engine.inserirNaTransmissao}
            />
          </div>

          <div className="space-y-5">
            <PlaylistCentral
              programaAtivo={engine.programaAtivo}
              musicaAtual={engine.musicaAtual}
              musicaFimSegundos={engine.musicaFimSegundos}
              estagioAtual={engine.estagioAtual}
              gerandoFala={engine.gerandoFala}
              falasPrograma={engine.falasPrograma}
              onProximaFala={engine.pularFala}
              musicPlayerRef={engine.musicPlayerRef}
              audioFalaRef={engine.audioFalaRef}
              programa={engine.programaSelecionado}
              totalFalas={engine.totalFalas}
            />
          </div>

          <div className="space-y-5">
            <CartwallPanel
              itens={bibliotecaItens.filter((i) => i.ativo)}
              duckMusicaFundo={engine.duckMusicaFundo}
              programaAtivo={engine.programaAtivo}
              onInserirNaTransmissao={engine.inserirNaTransmissao}
            />
            <InteracoesPanel
              radialistaId={engine.radialistaId}
              nomeLocutor={nomeLocutor}
              pulso={pulso}
              onNovaInteracao={avisarNovaInteracao}
            />
          </div>
        </div>
      )}

      <Modal open={modalRadialistaId !== null} onClose={() => setModalRadialistaId(null)} title="Editar radialista" maxWidthClassName="max-w-4xl">
        {modalRadialistaId !== null && (
          <EditarRadialistaForm
            radialistaId={modalRadialistaId}
            onSalvo={() => engine.carregarRadialistasEProgramas()}
            onAbrirPrograma={(progId) => {
              setModalPrograma({ radialistaId: modalRadialistaId, programaId: progId });
              setModalRadialistaId(null);
            }}
            onExcluido={() => {
              const excluidoId = modalRadialistaId;
              setModalRadialistaId(null);
              engine.carregarRadialistasEProgramas();
              if (engine.radialistaId === excluidoId) engine.limparRadialistaEPrograma();
            }}
          />
        )}
      </Modal>

      <Modal open={modalPrograma !== null} onClose={() => setModalPrograma(null)} title="Editar programa" maxWidthClassName="max-w-4xl">
        {modalPrograma !== null && (
          <EditarProgramaForm
            programaId={modalPrograma.programaId}
            radioConfigId={modalPrograma.radialistaId}
            onSalvo={() => engine.carregarRadialistasEProgramas()}
            onExcluido={() => {
              const excluidoId = modalPrograma.programaId;
              setModalPrograma(null);
              engine.carregarRadialistasEProgramas();
              if (excluidoId !== null && engine.programaId === excluidoId) engine.limparPrograma();
            }}
          />
        )}
      </Modal>
    </AppShell>
  );
}
