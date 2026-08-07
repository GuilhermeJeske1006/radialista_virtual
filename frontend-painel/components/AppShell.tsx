"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import Sidebar from "./Sidebar";
import { clearToken } from "../lib/auth";

const MOBILE_LINKS = [
  { href: "/dashboard", label: "Radialistas" },
  { href: "/onboarding", label: "WhatsApp" },
  { href: "/live", label: "Ao Vivo" },
  { href: "/billing", label: "Assinatura" },
];

export default function AppShell({
  title,
  children,
  maxWidthClassName = "max-w-4xl",
}: {
  title: string;
  children: React.ReactNode;
  maxWidthClassName?: string;
}) {
  const pathname = usePathname();
  const router = useRouter();

  function sair() {
    clearToken();
    router.push("/login");
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Sidebar />
      <div className="md:pl-72.5 flex flex-col min-h-screen">
        <header className="sticky top-0 z-10 bg-white border-b border-gray-200 shadow-theme-xs">
          <div className="flex items-center justify-between h-16 px-4 sm:px-6">
            <h1 className="text-xl font-semibold text-gray-800">{title}</h1>
            <button
              onClick={sair}
              className="flex items-center gap-2 text-sm font-medium text-gray-500 hover:text-gray-800"
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-50 text-brand-600 text-xs font-semibold">
                RV
              </span>
              <span className="hidden sm:inline">Sair</span>
            </button>
          </div>
          <nav className="md:hidden flex gap-4 overflow-x-auto px-4 sm:px-6 pb-3 -mt-1">
            {MOBILE_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={`text-sm font-medium whitespace-nowrap pb-1 border-b-2 ${
                  pathname === link.href
                    ? "border-brand-500 text-brand-600"
                    : "border-transparent text-gray-500"
                }`}
              >
                {link.label}
              </Link>
            ))}
          </nav>
        </header>
        <main className="flex-1 px-4 sm:px-6 py-6">
          <div className={`${maxWidthClassName} mx-auto`}>{children}</div>
        </main>
      </div>
    </div>
  );
}
