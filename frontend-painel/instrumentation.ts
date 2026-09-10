import * as Sentry from "@sentry/nextjs";

// A instrumentacao http do Sentry soma listener de 'close' em cada ServerResponse por cima
// dos que o proprio Next ja usa; com o painel fazendo polling pesado (metrics/ouvintes/live
// a cada poucos segundos), isso passa dos 10 default e spama MaxListenersExceededWarning.
// Nao e' vazamento entre requests (cada resposta e' descartada com a propria), so' precisa
// de um teto maior por resposta.
import { EventEmitter } from "node:events";
EventEmitter.defaultMaxListeners = 20;

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
