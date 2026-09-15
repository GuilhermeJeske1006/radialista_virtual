import { ImageResponse } from "next/og";
import { MarcaIcone } from "../marca-icone";

export const dynamic = "force-static";

export async function GET() {
  return new ImageResponse(<MarcaIcone canvas={512} mark={256} />, {
    width: 512,
    height: 512,
  });
}
