import { ImageResponse } from "next/og";

export const dynamic = "force-static";

// Maskable: OS applies its own shape mask, so keep the glyph inside the
// center ~80% safe zone and let the background bleed to the full canvas.
export async function GET() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#15130f",
          color: "#e8a33d",
          fontSize: 220,
          fontWeight: 700,
          fontFamily: "sans-serif",
        }}
      >
        O
      </div>
    ),
    { width: 512, height: 512 }
  );
}
