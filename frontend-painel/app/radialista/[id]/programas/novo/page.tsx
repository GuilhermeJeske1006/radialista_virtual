"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import AppShell from "../../../../../components/AppShell";
import EditarProgramaForm from "../../../../../components/EditarProgramaForm";
import { Programa } from "../../../../../lib/types";

export default function NovoProgramaPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const radialistaId = Number(params.id);

  return (
    <AppShell title="Novo programa" maxWidthClassName="max-w-4xl">
      <Link href={`/radialista/${radialistaId}`} className="text-sm text-amber hover:underline mb-4 inline-block">
        ← Voltar para o radialista
      </Link>

      <EditarProgramaForm
        programaId={null}
        radioConfigId={radialistaId}
        onSalvo={(p: Programa) => router.replace(`/radialista/${radialistaId}/programas/${p.id}`)}
      />
    </AppShell>
  );
}
