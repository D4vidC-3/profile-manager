"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { currentUsername, setSession } from "@/lib/api";

const LINKS = [
  { href: "/onboarding", label: "1. Perfil" },
  { href: "/matches", label: "2. Recomendaciones" },
  { href: "/board", label: "3. Tablero" },
  { href: "/trace", label: "Trazabilidad" },
];

export default function Nav() {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<string | null>(null);

  useEffect(() => setUser(currentUsername()), [pathname]);

  if (pathname === "/login") return null;

  return (
    <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
        <Link href="/" className="text-lg font-bold text-brand-dark">
          Profile<span className="text-brand">Manager</span>
        </Link>
        <nav className="flex flex-1 flex-wrap gap-1">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={`rounded-md px-3 py-1.5 text-sm ${
                pathname.startsWith(l.href) ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              {l.label}
            </Link>
          ))}
        </nav>
        {user && (
          <div className="flex items-center gap-3 text-sm text-slate-600">
            <span>{user}</span>
            <button
              className="text-slate-500 underline hover:text-slate-800"
              onClick={() => {
                setSession(null);
                router.push("/login");
              }}
            >
              Salir
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
