import { ImageResponse } from "next/og";
import { MarcaIcone } from "../marca-icone";

export const dynamic = "force-static";

export async function GET() {
  return new ImageResponse(<MarcaIcone canvas={192} mark={132} />, {
    width: 192,
    height: 192,
  });
}
