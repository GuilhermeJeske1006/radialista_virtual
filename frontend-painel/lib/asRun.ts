import { apiFetch } from "./api";

// F11 item 1: o player relata se o bloco que o /proxima entregou foi ao ar ("confirmado", fim natural do audio)
// ou deu erro ("falhou"). Sem esse relato o evento fica "enviado" e não conta como ao ar.
export type StatusAsRunPlayer = "confirmado" | "falhou";

export async function relatarAsRun(
  radialistaId: number,
  programaId: number,
  eventoId: number | null | undefined,
  status: StatusAsRunPlayer,
) {
  if (!eventoId) return null;
  return apiFetch<{ id: number; status: string }>(
    `/live/${radialistaId}/programas/${programaId}/as-run/${eventoId}`,
    { method: "POST", body: JSON.stringify({ status }) },
  );
}
