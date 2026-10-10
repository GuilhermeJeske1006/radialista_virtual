import type { FC } from "react";
import { Composition, staticFile } from "remotion";
import { Reel } from "./Reel";
import type { Montagem, ReelProps } from "./tipos";

const padrao: ReelProps = { id: "V1", montagem: null };

export const RemotionRoot: FC = () => (
  <Composition
    id="Reel"
    component={Reel}
    width={1080}
    height={1920}
    fps={30}
    durationInFrames={300}
    defaultProps={padrao}
    calculateMetadata={async ({ props }) => {
      const resposta = await fetch(staticFile(`${props.id}/montagem.json`));
      if (!resposta.ok) {
        throw new Error(`montagem.json do ${props.id} não encontrado: rode node preparar.mjs ${props.id}`);
      }
      const montagem = (await resposta.json()) as Montagem;
      return {
        durationInFrames: Math.max(1, montagem.total_frames),
        fps: montagem.fps,
        width: montagem.largura,
        height: montagem.altura,
        props: { ...props, montagem },
      };
    }}
  />
);
