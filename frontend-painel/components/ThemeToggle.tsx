"use client";

import { useEffect, useState } from "react";

const STORAGE_KEY = "locufy-theme";

function aplicarTema(tema: "dark" | "light") {
  document.documentElement.setAttribute("data-theme", tema);
  try {
    localStorage.setItem(STORAGE_KEY, tema);
  } catch {
    // localStorage indisponivel (modo privado etc) -- so nao persiste a preferencia
  }
}

export default function ThemeToggle({ className = "" }: { className?: string }) {
  const [tema, setTema] = useState<"dark" | "light">("dark");

  useEffect(() => {
    const atual = document.documentElement.getAttribute("data-theme");
    setTema(atual === "light" ? "light" : "dark");
  }, []);

  function alternar() {
    const proximo = tema === "dark" ? "light" : "dark";
    setTema(proximo);
    aplicarTema(proximo);
  }

  return (
    <button
      type="button"
      onClick={alternar}
      aria-label={tema === "dark" ? "Mudar para tema claro" : "Mudar para tema escuro"}
      title={tema === "dark" ? "Tema claro" : "Tema escuro"}
      className={`flex h-8 w-8 items-center justify-center rounded-full border border-border-strong text-fg/65 hover:text-amber-text hover:border-amber/40 transition-colors ${className}`}
    >
      {tema === "dark" ? (
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.75} stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 3v1.5m0 15V21m9-9h-1.5M4.5 12H3m15.364-6.364-1.06 1.06M6.696 17.304l-1.06 1.06m12.728 0-1.06-1.06M6.696 6.696l-1.06-1.06M16.5 12a4.5 4.5 0 1 1-9 0 4.5 4.5 0 0 1 9 0Z"
          />
        </svg>
      ) : (
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.75} stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M21.752 15.002A9.72 9.72 0 0 1 18 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 0 0 3 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 0 0 9.002-5.998Z"
          />
        </svg>
      )}
    </button>
  );
}
