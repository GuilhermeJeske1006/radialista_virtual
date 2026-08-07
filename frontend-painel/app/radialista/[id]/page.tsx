"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import AppShell from "../../../components/AppShell";
import EditarRadialistaForm from "../../../components/EditarRadialistaForm";

export default function EditarRadialistaPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const radialistaId = Number(params.id);

  return (
    <AppShell title="Radialista" maxWidthClassName="max-w-4xl">
      <Link href="/radialista" className="text-sm text-amber hover:underline mb-4 inline-block">
        ← Todos os radialistas
      </Link>

      <EditarRadialistaForm radialistaId={radialistaId} onExcluido={() => router.push("/radialista")} />
    </AppShell>
  );
}
