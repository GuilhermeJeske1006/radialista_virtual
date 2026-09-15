import { ImageResponse } from "next/og";
import { MarcaIcone } from "./marca-icone";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(<MarcaIcone canvas={180} mark={124} />, { ...size });
}
