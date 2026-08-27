"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import AppShell from "../../../components/AppShell";
import Modal from "../../../components/Modal";
import EditarRadialistaForm from "../../../components/EditarRadialistaForm";
import EditarProgramaForm from "../../../components/EditarProgramaForm";

export default function EditarRadialistaPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const radialistaId = Number(params.id);
  const [modalProgramaId, setModalProgramaId] = useState<number | null | "novo">(null);
  const [chaveProgramas, setChaveProgramas] = useState(0);

  return (
    <AppShell title="Radialista" maxWidthClassName="max-w-4xl">
      <Link href="/radialista" className="text-sm text-amber-text hover:underline mb-4 inline-block">
        ← Todos os radialistas
      </Link>

      <EditarRadialistaForm
        key={chaveProgramas}
        radialistaId={radialistaId}
        onExcluido={() => router.push("/radialista")}
        onAbrirPrograma={(programaId) => setModalProgramaId(programaId ?? "novo")}
      />

      <Modal
        open={modalProgramaId !== null}
        onClose={() => setModalProgramaId(null)}
        title={modalProgramaId === "novo" ? "Novo programa" : "Editar programa"}
        maxWidthClassName="max-w-4xl"
      >
        {modalProgramaId !== null && (
          <EditarProgramaForm
            programaId={modalProgramaId === "novo" ? null : modalProgramaId}
            radioConfigId={radialistaId}
            onSalvo={() => setChaveProgramas((k) => k + 1)}
            onExcluido={() => {
              setModalProgramaId(null);
              setChaveProgramas((k) => k + 1);
            }}
          />
        )}
      </Modal>
    </AppShell>
  );
}
