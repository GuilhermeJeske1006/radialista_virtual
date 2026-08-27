"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import AppShell from "../../../../../components/AppShell";
import EditarProgramaForm from "../../../../../components/EditarProgramaForm";

export default function EditarProgramaPage() {
  const params = useParams<{ id: string; programaId: string }>();
  const router = useRouter();
  const radialistaId = Number(params.id);
  const programaId = Number(params.programaId);

  return (
    <AppShell title="Programa" maxWidthClassName="max-w-4xl">
      <Link href={`/radialista/${radialistaId}`} className="text-sm text-amber-text hover:underline mb-4 inline-block">
        ← Voltar para o radialista
      </Link>

      <EditarProgramaForm programaId={programaId} onExcluido={() => router.push(`/radialista/${radialistaId}`)} />
    </AppShell>
  );
}
