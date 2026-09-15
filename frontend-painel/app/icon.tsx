import { ImageResponse } from "next/og";
import { MarcaIconeFavicon } from "./marca-icone";

export const size = { width: 32, height: 32 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(<MarcaIconeFavicon canvas={32} mark={27} />, { ...size });
}
