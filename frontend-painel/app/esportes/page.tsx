import { redirect } from "next/navigation";

// Links antigos passam a abrir o fluxo existente de Programas.
export default function EsportesPage() {
  redirect("/programas");
}
