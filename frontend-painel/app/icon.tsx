import { ImageResponse } from "next/og";

export const size = { width: 32, height: 32 };
export const contentType = "image/png";

const MARCA = {
  width: "100%",
  height: "100%",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  background: "linear-gradient(135deg, #631BF6 0%, #00B4D8 100%)",
  color: "#FFFFFF",
  fontWeight: 700,
  fontFamily: "sans-serif",
} as const;

export default function Icon() {
  return new ImageResponse(<div style={{ ...MARCA, fontSize: 22 }}>L</div>, { ...size });
}
