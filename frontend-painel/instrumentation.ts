import * as Sentry from "@sentry/nextjs";

// mesmo DSN do instrumentation-client.ts (NEXT_PUBLIC_ pra estar disponivel tanto no
// server quanto no browser) -- vazio desativa o SDK nos runtimes node/edge tambem.
export function register() {
  const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;
  if (!dsn) return;

  Sentry.init({
    dsn,
    environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || "development",
    tracesSampleRate: 0,
  });
}

export const onRequestError = Sentry.captureRequestError;
