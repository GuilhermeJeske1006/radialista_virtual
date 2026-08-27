const EMAIL_LEMBRADO_KEY = "radialista_email_lembrado";

export function getEmailLembrado(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(EMAIL_LEMBRADO_KEY);
}

export function setEmailLembrado(email: string): void {
  window.localStorage.setItem(EMAIL_LEMBRADO_KEY, email);
}

export function limparEmailLembrado(): void {
  window.localStorage.removeItem(EMAIL_LEMBRADO_KEY);
}
