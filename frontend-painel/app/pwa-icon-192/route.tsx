import { ImageResponse } from "next/og";

export const dynamic = "force-static";

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
          fontSize: 130,
          fontWeight: 700,
          fontFamily: "sans-serif",
        }}
      >
        O
      </div>
    ),
    { width: 192, height: 192 }
  );
}
