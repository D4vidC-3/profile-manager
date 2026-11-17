"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, AppState, cop, FlowResponse, Match, SKILL_LEVEL_LABEL, SkillCheck, SkillLevel } from "@/lib/api";
import { ErrorBox, ScoreBar, Spinner } from "@/components/ui";
import IdentityForm from "@/components/IdentityForm";
import SkillLevelsForm from "@/components/SkillLevelsForm";

const COMPONENTS: { key: string; label: string; max: number }[] = [
  { key: "skills_obligatorias", label: "Habilidades obligatorias", max: 35 },
  { key: "skills_deseables", label: "Habilidades deseables", max: 8 },
  { key: "transversales", label: "Transversales", max: 2 },
  { key: "rol", label: "Cargo", max: 15 },
  { key: "seniority", label: "Nivel de experiencia", max: 12 },
  { key: "educacion", label: "Formación", max: 5 },
  { key: "salario", label: "Salario", max: 8 },
  { key: "modalidad", label: "Modalidad", max: 10 },
  { key: "sector", label: "Sector", max: 5 },
];

const lv = (x: string | null) => (x ? SKILL_LEVEL_LABEL[x as SkillLevel]?.toLowerCase() ?? x : "");

function SkillChip({ s }: { s: SkillCheck }) {
  const styles: Record<SkillCheck["status"], string> = {
    ok: "bg-emerald-100 text-emerald-800",
    falta: "bg-red-50 text-red-700 line-through decoration-red-300",
    nivel_menor: "bg-amber-100 text-amber-800",
    nivel_por_confirmar: "bg-amber-50 text-amber-700",
  };
  const title: Record<SkillCheck["status"], string> = {
    ok: s.demonstrated ? "La tienes (y la respalda tu experiencia o un proyecto)" : "La tienes",
    falta: "No está en tu perfil",
    nivel_menor: `Piden ${lv(s.required_level)} y tienes ${lv(s.have_level)}`,
    nivel_por_confirmar: `Piden ${lv(s.required_level)}: confirma tu nivel`,
  };
  return (
    <span title={title[s.status]} className={`rounded-full px-2.5 py-0.5 text-xs ${styles[s.status]}`}>
      {s.status === "ok" ? "✓ " : s.status === "falta" ? "" : "⚠ "}
      {s.name}
      {s.required_level && ` · ${lv(s.required_level)}`}
    </span>
  );
}

export default function MatchesPage() {
  const router = useRouter();
  const [state, setState] = useState<AppState | null>(null);
  const [matches, setMatches] = useState<Match[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    const s = await api<AppState>("/api/state");
    setState(s);
    const m = s.pending?.type === "approval" ? s.pending.matches : await api<Match[]>("/api/matches");
    setMatches(m);
    setSelected(new Set(s.stage === "approval" ? m.slice(0, 3).map((x) => x.vacancy.id) : []));
  }, []);

  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [load]);

  function toggle(id: string) {
    setSelected((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  }

  async function refresh() {
    setBusy("El Agente de Vacantes está recalculando…");
    setError(null);
    try {
      await api<FlowResponse>("/api/matches/refresh", { method: "POST" });
      await load();
      setNotice("Recomendaciones actualizadas con tu perfil y preferencias actuales.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function approve() {
    setBusy("Postulando…");
    setError(null);
    try {
      const r = await api<FlowResponse>("/api/applications/approve", {
        method: "POST",
        body: JSON.stringify({ vacancy_ids: [...selected] }),
      });
      if (r.stage === "identity" || r.stage === "skill_levels") await load();
      else router.push("/board");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  if (!state) return error ? <ErrorBox msg={error} /> : <Spinner text="Cargando…" />;
  const canApprove = state.stage === "approval" || state.stage === "tracking";
  const pendingLangs = [...new Set(matches.flatMap((m) => m.pending_languages ?? []))];

  if (state.stage === "skill_levels" && state.pending?.type === "skill_levels")
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold">2. Postular</h1>
        <SkillLevelsForm pending={state.pending} onDone={(r) => (r.stage === "tracking" ? router.push("/board") : load())} />
      </div>
    );

  if (state.stage === "identity" && state.pending?.type === "identity")
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold">2. Postular</h1>
        <IdentityForm pending={state.pending} onDone={(r) => (r.stage === "tracking" ? router.push("/board") : load())} />
      </div>
    );

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">2. Vacantes recomendadas</h1>
          <p className="text-slate-600">
            El <b>Agente de Vacantes</b> recomienda aunque no cumplas todo: lo que te falta aparece en{" "}
            <b>&ldquo;Para prepararte&rdquo;</b> y, si te postulas, el <b>Agente de Seguimiento</b> lo convierte en un
            plan de preparación.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {canApprove && (
            <button className="btn-secondary" disabled={!!busy} onClick={refresh}>
              🔄 Actualizar recomendaciones
            </button>
          )}
          {canApprove && (
            <button className="btn" disabled={!!busy || selected.size === 0} onClick={approve}>
              {`Postular a ${selected.size} vacante(s)`}
            </button>
          )}
        </div>
      </div>
      <ErrorBox msg={error} />
      {busy && <Spinner text={busy} />}
      {notice && <div className="rounded-lg bg-emerald-50 px-4 py-2 text-sm text-emerald-800">{notice}</div>}
      {pendingLangs.length > 0 && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-800">
          Algunas vacantes piden <b>{pendingLangs.join(", ")}</b> y tu nivel está pendiente.{" "}
          <Link className="underline" href="/onboarding">
            Confírmalo en tu perfil
          </Link>{" "}
          y luego pulsa &ldquo;Actualizar recomendaciones&rdquo;.
        </div>
      )}
      {["onboarding", "cv_gaps", "preferences"].includes(state.stage) ? (
        <div className="card text-slate-600">
          Primero completa tu perfil en <Link className="text-brand underline" href="/onboarding">Perfil</Link>.
        </div>
      ) : matches.length === 0 ? (
        <div className="card text-slate-600">
          No hay vacantes que cumplan tus condiciones. Revisa en Trazabilidad por qué se descartaron.
        </div>
      ) : null}

      <div className="grid gap-4">
        {matches.map((m) => {
          const v = m.vacancy;
          const checked = selected.has(v.id);
          return (
            <article key={v.id} className={`card ${checked ? "ring-2 ring-sky-400" : ""}`}>
              <div className="flex flex-wrap items-start gap-4">
                {canApprove && (
                  <input type="checkbox" className="mt-1.5 h-5 w-5" checked={checked} onChange={() => toggle(v.id)} />
                )}
                <div className="min-w-0 flex-1 space-y-3">
                  <div>
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <h2 className="text-lg font-semibold">{v.title}</h2>
                      <span className="text-2xl font-bold text-brand-dark">{m.score}</span>
                    </div>
                    <p className="text-sm text-slate-600">
                      {v.company} · {v.city ?? "—"} · {v.modality} · {v.workday} · {v.contract} ·{" "}
                      {cop(v.salary_min_cop)} – {cop(v.salary_max_cop)} · publicada {v.posted_at}
                      {v.min_education && ` · formación mínima: ${v.min_education}`}
                      {Object.keys(v.languages ?? {}).length > 0 &&
                        ` · pide ${Object.entries(v.languages).map(([l, c]) => `${l} ${c}`).join(", ")}`}
                      {v.requires_travel && " · requiere viajar"}
                    </p>
                  </div>

                  {(m.skills_detail ?? []).length > 0 && (
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="text-xs font-semibold text-slate-500">Habilidades que pide:</span>
                      {(m.skills_detail ?? []).map((s) => (
                        <SkillChip key={s.name} s={s} />
                      ))}
                    </div>
                  )}

                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-3">
                      <div>
                        <h3 className="text-sm font-semibold">¿Por qué te la recomendamos?</h3>
                        <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm text-slate-700">
                          {m.reasons.map((r, i) => (
                            <li key={i}>{r}</li>
                          ))}
                        </ul>
                      </div>
                      {(m.gaps ?? []).length > 0 && (
                        <div className="rounded-lg bg-amber-50 p-2">
                          <h3 className="text-sm font-semibold text-amber-900">Para prepararte</h3>
                          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm text-amber-900">
                            {(m.gaps ?? []).map((g, i) => (
                              <li key={i}>{g.message}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                    <div className="space-y-1.5">
                      {COMPONENTS.map((c) => {
                        const val = m.breakdown[c.key] ?? 0;
                        const na = m.not_applicable?.includes(c.key);
                        return (
                          <div key={c.key} className="grid grid-cols-[130px_1fr_56px] items-center gap-2 text-xs">
                            <span className="text-slate-600">{c.label}</span>
                            {na ? <span className="text-slate-400">No aplica (la vacante no lo pide)</span> : <ScoreBar value={val} max={c.max} />}
                            <span className="text-right text-slate-500">{na ? "—" : `${val}/${c.max}`}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
