"use client";

import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";

// Erro fatal no root layout (React 19 error boundary usa `retry`, nao `reset`,
// nesta versao do Next). error.tsx cobre erros dentro de rotas; este cobre o
// resto -- por isso precisa dos proprios <html>/<body>.
export default function GlobalError({
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
    <html lang="pt-BR" data-theme="dark">
      <body className="bg-bg text-fg antialiased">
        <div style={{ padding: "2rem", textAlign: "center" }}>
          <h2>Algo deu errado.</h2>
          <button onClick={() => retry()}>Tentar novamente</button>
        </div>
      </body>
    </html>
  );
}
