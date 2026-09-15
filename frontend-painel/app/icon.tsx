import { ImageResponse } from "next/og";
import { MarcaIcone } from "./marca-icone";

export const size = { width: 32, height: 32 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(<MarcaIcone canvas={32} mark={24} />, { ...size });
}
