"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "../lib/api";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    // sessao vive num cookie httpOnly (o JS nao consegue ler) -- so' da pra saber
    // se ha sessao valida perguntando pro backend.
    apiFetch("/auth/me")
      .then(() => router.replace("/dashboard"))
      .catch(() => router.replace("/login"));
  }, [router]);

  return null;
}
