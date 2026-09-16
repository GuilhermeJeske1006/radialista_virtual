// Códigos de campanha, nunca conteúdo dos campos do cadastro.
const keys = ["utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"] as const;
const sent = new Set<string>();
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
function permitted() {
  return typeof window !== "undefined" && navigator.doNotTrack !== "1" && !(navigator as Navigator & { globalPrivacyControl?: boolean }).globalPrivacyControl;
}
export function captureCampaign(): Record<string, string> {
  if (!permitted()) return {};
  const params = new URLSearchParams(window.location.search);
  let campaign: Record<string, string> = {};
  try { campaign = JSON.parse(sessionStorage.getItem("locufy-campaign") || "{}"); } catch { /* Sem armazenamento. */ }
  if (!campaign || typeof campaign !== "object" || Array.isArray(campaign)) campaign = {};
  if (keys.some(key => params.has(key))) campaign = Object.fromEntries(keys.map(k => [k, params.get(k) || ""]));
  campaign = Object.fromEntries(keys.filter(k => typeof campaign[k] === "string" && /^[a-zA-Z0-9_-]{1,80}$/.test(campaign[k])).map(k => [k, campaign[k]]));
  try { sessionStorage.setItem("locufy-campaign", JSON.stringify(campaign)); } catch { /* O fluxo continua. */ }
  return campaign;
}
export function trackFunnel(evento: string, data: { plano?: string } = {}) {
  if (!permitted()) return;
  const key = `${evento}:${data.plano || ""}`;
  if (sent.has(key)) return;
  sent.add(key);
  void fetch(`${API}/funnel/events`, { method: "POST", credentials: "omit", keepalive: true,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id: crypto.randomUUID(), evento, local: "register", plano: data.plano || "", campanha: captureCampaign() }),
  }).catch(() => { sent.delete(key); });
}
