"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import AppShell from "../../../components/AppShell";
import EditarRadialistaForm from "../../../components/EditarRadialistaForm";
import { Radialista } from "../../../lib/types";

export default function NovoRadialistaPage() {
  const router = useRouter();

  return (
    <AppShell title="Novo radialista" maxWidthClassName="max-w-4xl">
      <Link href="/radialista" className="text-sm text-amber-text hover:underline mb-4 inline-block">
        ← Todos os radialistas
      </Link>

      <EditarRadialistaForm
        radialistaId={null}
        onSalvo={(r: Radialista) => router.replace(`/radialista/${r.id}`)}
      />
    </AppShell>
  );
}
