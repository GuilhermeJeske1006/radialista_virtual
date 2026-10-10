import type { CSSProperties, FC } from "react";
import {
  AbsoluteFill,
  Audio,
  Img,
  OffthreadVideo,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { loadFont as carregarNunito } from "@remotion/google-fonts/Nunito";
import { loadFont as carregarFigtree } from "@remotion/google-fonts/Figtree";
import type { Cena, Legenda, Mensagem, ReelProps } from "./tipos";

const { fontFamily: NUNITO } = carregarNunito();
const { fontFamily: FIGTREE } = carregarFigtree();

// Cores do manual da marca Locufy.
const COR = {
  roxo: "#631BF6",
  ciano: "#00B4D8",
  azul: "#1B263B",
  laranja: "#FF8C00",
  preto: "#18181A",
  cinza: "#6C707B",
  branco: "#FFFFFF",
};
const GRADIENTE = "linear-gradient(150deg, #3E3A98 0%, #3D69BC 55%, #138FAE 100%)";
// Área segura do Instagram: nada importante nos 250 px de cima e de baixo.
const SEGURO = 250;

const useEntrada = (atraso = 0) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return spring({ frame: frame - atraso, fps, config: { damping: 200 } });
};

const Cartela: FC<{ titulo: string; icone: string }> = ({ titulo, icone }) => {
  const entrada = useEntrada();
  return (
    <AbsoluteFill style={{ background: GRADIENTE, justifyContent: "center", padding: 96 }}>
      <Img
        src={staticFile(icone)}
        style={{ position: "absolute", right: -160, bottom: 120, width: 760, opacity: 0.1 }}
      />
      <div
        style={{
          fontFamily: NUNITO,
          fontWeight: 900,
          fontSize: 108,
          lineHeight: 1.05,
          color: COR.branco,
          letterSpacing: -2,
          transform: `translateY(${interpolate(entrada, [0, 1], [60, 0])}px)`,
          opacity: entrada,
        }}
      >
        {titulo}
      </div>
    </AbsoluteFill>
  );
};

const Logo: FC<{ logo: string }> = ({ logo }) => {
  const entrada = useEntrada();
  const sub = useEntrada(12);
  return (
    <AbsoluteFill style={{ background: GRADIENTE, justifyContent: "center", alignItems: "center", gap: 64 }}>
      <Img src={staticFile(logo)} style={{ width: 760, transform: `scale(${interpolate(entrada, [0, 1], [0.9, 1])})`, opacity: entrada }} />
      <div
        style={{
          fontFamily: NUNITO,
          fontWeight: 900,
          fontSize: 56,
          color: COR.preto,
          background: COR.branco,
          borderRadius: 999,
          padding: "22px 48px",
          opacity: sub,
        }}
      >
        Link na bio
      </div>
    </AbsoluteFill>
  );
};

const Tela: FC<{ video: NonNullable<Cena["video"]>; icone: string }> = ({ video, icone }) => {
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ backgroundColor: COR.azul }}>
      <OffthreadVideo
        src={staticFile(video.arquivo)}
        startFrom={Math.round(video.inicio_s * fps)}
        muted
        style={{ width: "100%", height: "100%", objectFit: "cover" }}
      />
      <Img src={staticFile(icone)} style={{ position: "absolute", top: SEGURO - 120, right: 48, width: 64, opacity: 0.85 }} />
    </AbsoluteFill>
  );
};

const estiloBolha = (m: Mensagem): CSSProperties => {
  if (m.de === "sistema") {
    return {
      alignSelf: "center",
      background: "rgba(255,140,0,0.16)",
      color: "#8A4A00",
      border: `3px solid ${COR.laranja}`,
      borderRadius: 999,
      padding: "16px 28px",
      fontWeight: 700,
    };
  }
  const ouvinte = m.de === "ouvinte";
  return {
    alignSelf: ouvinte ? "flex-start" : "flex-end",
    maxWidth: "82%",
    background: ouvinte ? COR.branco : "#2E2A86",
    color: ouvinte ? COR.preto : COR.branco,
    borderRadius: ouvinte ? "10px 36px 36px 36px" : "36px 10px 36px 36px",
    padding: "24px 30px",
    boxShadow: "0 2px 0 rgba(0,0,0,0.08)",
  };
};

const Celular: FC<{ conversa: Mensagem[]; duracao: number }> = ({ conversa, duracao }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const passo = Math.max(fps * 0.8, duracao / (conversa.length + 1));
  return (
    <AbsoluteFill style={{ background: GRADIENTE, justifyContent: "center", alignItems: "center" }}>
      <div
        style={{
          width: 900,
          height: 1400,
          marginTop: 40,
          borderRadius: 72,
          background: "#ECE5DD",
          border: `14px solid ${COR.preto}`,
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
          fontFamily: FIGTREE,
        }}
      >
        <div style={{ background: "#075E54", color: COR.branco, padding: "48px 40px 28px", display: "flex", alignItems: "center", gap: 24 }}>
          <div style={{ width: 84, height: 84, borderRadius: "50%", background: GRADIENTE }} />
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <span style={{ fontWeight: 700, fontSize: 38 }}>Rádio Cidade FM</span>
            <span style={{ fontSize: 26, opacity: 0.85 }}>online</span>
          </div>
        </div>
        <div style={{ flex: 1, padding: 36, display: "flex", flexDirection: "column", gap: 22, fontSize: 36, lineHeight: 1.35 }}>
          {conversa.map((m, i) => {
            const aparece = spring({ frame: frame - i * passo, fps, config: { damping: 200 } });
            if (frame < i * passo) return null;
            return (
              <div key={i} style={{ ...estiloBolha(m), opacity: aparece, transform: `translateY(${interpolate(aparece, [0, 1], [30, 0])}px)` }}>
                {m.texto}
                {m.hora ? <span style={{ display: "block", textAlign: "right", fontSize: 22, opacity: 0.6, marginTop: 6 }}>{m.hora}</span> : null}
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};

const Chamada: FC<{ texto: string }> = ({ texto }) => {
  const entrada = useEntrada(4);
  return (
    <AbsoluteFill style={{ justifyContent: "flex-start", alignItems: "center", paddingTop: SEGURO + 20 }}>
      <div
        style={{
          maxWidth: 940,
          background: "rgba(27,38,59,0.88)",
          color: COR.branco,
          fontFamily: NUNITO,
          fontWeight: 900,
          fontSize: 58,
          lineHeight: 1.12,
          textAlign: "center",
          borderRadius: 32,
          padding: "28px 40px",
          opacity: entrada,
        }}
      >
        {texto}
      </div>
    </AbsoluteFill>
  );
};

const Legendas: FC<{ legendas: Legenda[] }> = ({ legendas }) => {
  const frame = useCurrentFrame();
  const atual = legendas.find((l) => frame >= l.inicio_f && frame < l.fim_f);
  if (!atual) return null;
  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: SEGURO + 40 }}>
      {atual.quem ? (
        <div style={{ fontFamily: NUNITO, fontWeight: 900, fontSize: 34, color: COR.laranja, marginBottom: 8, textShadow: "0 2px 8px rgba(0,0,0,.6)" }}>
          {atual.quem}
        </div>
      ) : null}
      <div
        style={{
          maxWidth: 960,
          fontFamily: FIGTREE,
          fontWeight: 700,
          fontSize: 54,
          lineHeight: 1.2,
          textAlign: "center",
          color: COR.branco,
          WebkitTextStroke: `10px ${COR.preto}`,
          paintOrder: "stroke fill",
        }}
      >
        {atual.texto}
      </div>
    </AbsoluteFill>
  );
};

const ConteudoCena: FC<{ cena: Cena; logo: string; icone: string }> = ({ cena, logo, icone }) => {
  if (cena.tipo === "tela" && cena.video) return <Tela video={cena.video} icone={icone} />;
  if (cena.tipo === "celular") return <Celular conversa={cena.conversa ?? []} duracao={cena.dur_f} />;
  if (cena.tipo === "logo") return <Logo logo={logo} />;
  return <Cartela titulo={cena.titulo ?? ""} icone={icone} />;
};

export const Reel: FC<ReelProps> = ({ montagem }) => {
  const { fps } = useVideoConfig();
  if (!montagem) return <AbsoluteFill style={{ background: GRADIENTE }} />;
  return (
    <AbsoluteFill style={{ backgroundColor: COR.azul }}>
      {montagem.cenas.map((cena) => (
        <Sequence key={cena.n} from={cena.inicio_f} durationInFrames={cena.dur_f} name={`Cena ${cena.n} · ${cena.tipo}`}>
          <ConteudoCena cena={cena} logo={montagem.logo} icone={montagem.icone} />
          {cena.chamada ? <Chamada texto={cena.chamada} /> : null}
          {cena.audios.map((a, i) => (
            <Sequence key={i} from={Math.round(a.inicio_s * fps)}>
              <Audio src={staticFile(a.arquivo)} volume={a.volume} />
            </Sequence>
          ))}
        </Sequence>
      ))}
      <Legendas legendas={montagem.legendas} />
      {montagem.trilha ? <Audio src={staticFile(montagem.trilha)} volume={0.1} loop /> : null}
    </AbsoluteFill>
  );
};
