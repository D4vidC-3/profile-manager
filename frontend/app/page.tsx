"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { api, AppState } from "@/lib/api";
import { Spinner } from "@/components/ui";

const ROUTE: Record<string, string> = {
  onboarding: "/onboarding",
  cv_gaps: "/onboarding",
  preferences: "/onboarding",
  approval: "/matches",
  skill_levels: "/matches",
  identity: "/matches",
  tracking: "/board",
};

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    api<AppState>("/api/state")
      .then((s) => router.replace(ROUTE[s.stage] ?? "/onboarding"))
      .catch(() => router.replace("/login"));
  }, [router]);
  return <Spinner text="Cargando…" />;
}
