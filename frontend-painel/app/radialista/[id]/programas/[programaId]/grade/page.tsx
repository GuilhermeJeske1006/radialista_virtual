"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import AppShell from "../../../../../../components/AppShell";
import GradeProgramacaoForm from "../../../../../../components/GradeProgramacaoForm";

export default function GradeProgramacaoPage() {
  const params = useParams<{ id: string; programaId: string }>();
  const radialistaId = Number(params.id);
  const programaId = Number(params.programaId);

  return (
    <AppShell title="Montagem de blocos" maxWidthClassName="max-w-6xl">
      <Link
        href={`/radialista/${radialistaId}/programas/${programaId}`}
        className="text-sm text-amber hover:underline mb-4 inline-block"
      >
        ← Voltar para o programa
      </Link>

      <GradeProgramacaoForm programaId={programaId} />
    </AppShell>
  );
}
