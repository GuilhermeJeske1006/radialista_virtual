import * as Sentry from "@sentry/nextjs";

// DSN nao e' segredo (e' feito pra ir no bundle do browser) -- so' identifica o
// projeto no Sentry. Vazio (dev local sem Sentry configurado) desativa o SDK.
const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;

if (dsn) {
  Sentry.init({
    dsn,
    environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || "development",
    tracesSampleRate: 0,
  });
}
