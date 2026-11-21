/** Links persistidos no programa; também aceita os domínios dos cadastros antigos. */
export function linkFonte(fonte: string): string | null {
  try {
    const valor = fonte.trim();
    const url = new URL(valor.includes("://") ? valor : `https://${valor}`);
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password
      || !/^(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$/i.test(url.hostname)) return null;
    return url.href;
  } catch {
    return null;
  }
}

export function dominioFonte(fonte: string): string | null {
  const url = linkFonte(fonte);
  return url ? new URL(url).hostname.replace(/^www\./, "") : null;
}
