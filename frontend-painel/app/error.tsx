"use client";

import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";

export default function Error({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <div style={{ padding: "2rem", textAlign: "center" }}>
      <h2>Algo deu errado.</h2>
      <button onClick={() => retry()}>Tentar novamente</button>
    </div>
  );
}
