"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, Application, AppState, Reminder, STATUS_LABEL } from "@/lib/api";
import { ErrorBox, ModeBadge, Spinner } from "@/components/ui";

const COLUMNS: { key: Application["status"]; color: string }[] = [
  { key: "postulado", color: "border-t-sky-400" },
  { key: "en_revision", color: "border-t-amber-400" },
  { key: "entrevista", color: "border-t-emerald-500" },
  { key: "descartado", color: "border-t-slate-400" },
];

export default function BoardPage() {
  const [state, setState] = useState<AppState | null>(null);
  const [apps, setApps] = useState<Application[]>([]);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [open, setOpen] = useState<Application | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [lastRun, setLastRun] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [s, a, r] = await Promise.all([
      api<AppState>("/api/state"),
      api<Application[]>("/api/applications"),
      api<Reminder[]>("/api/reminders"),
    ]);
    setState(s);
    setApps(a);
    setReminders(r);
  }, []);

  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [load]);

  async function advance(days: number) {
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ sim_day: number; status_changes: number; reminders_created: number }>(
        "/api/simulate/advance",
        { method: "POST", body: JSON.stringify({ days }) },
      );
      setLastRun(
        `Día ${r.sim_day}: ${r.status_changes} cambio(s) de estado y ${r.reminders_created} recordatorio(s) nuevo(s).`,
      );
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function toggleReminder(r: Reminder) {
    await api(`/api/reminders/${r.id}`, { method: "PATCH", body: JSON.stringify({ done: !r.done }) });
    await load();
  }

  if (!state) return <Spinner text="Cargando…" />;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">3. Tablero de procesos</h1>
          <p className="text-slate-600">
            Estados de tus postulaciones. El <b>Agente de Seguimiento</b> genera recordatorios y próximos pasos.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded-md bg-slate-900 px-3 py-1.5 text-sm text-white">Día simulado {state.sim_day}</span>
          <button className="btn" disabled={busy || state.stage !== "tracking"} onClick={() => advance(3)}>
            {busy ? "Simulando…" : "Simular +3 días"}
          </button>
          <button className="btn-secondary" disabled={busy || state.stage !== "tracking"} onClick={() => advance(7)}>
            +7 días
          </button>
        </div>
      </div>
      <ErrorBox msg={error} />
      {lastRun && <div className="rounded-lg bg-sky-50 px-4 py-2 text-sm text-sky-800">{lastRun}</div>}
      {state.stage !== "tracking" && (
        <div className="card text-slate-600">
          Aún no hay postulaciones. Completa el <Link className="text-brand underline" href="/onboarding">perfil</Link> y
          aprueba vacantes en <Link className="text-brand underline" href="/matches">Recomendaciones</Link>.
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {COLUMNS.map((c) => {
            const items = apps.filter((a) => a.status === c.key);
            return (
              <div key={c.key} className={`rounded-xl border border-t-4 border-slate-200 bg-slate-50 p-3 ${c.color}`}>
                <h2 className="mb-2 flex justify-between text-sm font-semibold">
                  {STATUS_LABEL[c.key]} <span className="text-slate-400">{items.length}</span>
                </h2>
                <div className="space-y-2">
                  {items.map((a) => (
                    <button
                      key={a.id}
                      onClick={() => setOpen(a)}
                      className="w-full rounded-lg border border-slate-200 bg-white p-3 text-left text-sm shadow-sm hover:border-sky-300"
                    >
                      <p className="font-medium">{a.vacancy_title}</p>
                      <p className="text-xs text-slate-500">{a.company}</p>
                      <p className="mt-1 text-xs text-slate-500">
                        Match {a.score} · act. día {a.updated_day}
                        {a.interview_day != null && a.status === "entrevista" ? ` · entrevista día ${a.interview_day}` : ""}
                      </p>
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        <aside className="card h-fit space-y-3">
          <h2 className="font-semibold">Recordatorios</h2>
          {reminders.length === 0 && <p className="text-sm text-slate-500">Sin recordatorios por ahora.</p>}
          {reminders.map((r) => (
            <div key={r.id} className={`rounded-lg border p-3 text-sm ${r.done ? "opacity-50" : ""}`}>
              <div className="flex items-start justify-between gap-2">
                <p className="font-medium">{r.title}</p>
                <ModeBadge mode={r.mode} />
              </div>
              <p className="mt-1 text-slate-600">{r.message}</p>
              <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
                <span>Para el día {r.due_day}</span>
                <button className="underline" onClick={() => toggleReminder(r)}>
                  {r.done ? "Reabrir" : "Hecho"}
                </button>
              </div>
            </div>
          ))}
        </aside>
      </div>

      {open && <ApplicationModal app={open} onClose={() => setOpen(null)} />}
    </div>
  );
}

function ApplicationModal({ app, onClose }: { app: Application; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-20 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="card max-h-[85vh] w-full max-w-2xl overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold">{app.vacancy_title}</h2>
            <p className="text-sm text-slate-600">
              {app.company} · {STATUS_LABEL[app.status]} · match {app.score}
            </p>
          </div>
          <button className="btn-secondary" onClick={onClose}>
            Cerrar
          </button>
        </div>
        <h3 className="mt-4 text-sm font-semibold">Próximos pasos</h3>
        <ul className="mt-1 list-disc pl-5 text-sm text-slate-700">
          {app.next_steps.map((s, i) => (
            <li key={i}>{s}</li>
          ))}
        </ul>
        <h3 className="mt-4 text-sm font-semibold">Historial</h3>
        <ol className="mt-1 space-y-1 text-sm text-slate-700">
          {app.history.map((h, i) => (
            <li key={i}>
              Día {h.day}: <b>{STATUS_LABEL[h.status as Application["status"]] ?? h.status}</b>{" "}
              <span className="text-slate-400">({h.by})</span>
            </li>
          ))}
        </ol>
        <h3 className="mt-4 text-sm font-semibold">Evidencia de la postulación</h3>
        <p className="text-xs text-slate-500">
          Comprobante {app.evidence.receipt.receipt_id} · {app.evidence.receipt.received_at} · SHA-256{" "}
          {app.evidence.receipt.payload_sha256?.slice(0, 16)}…
        </p>
        <pre className="mt-2 max-h-64 overflow-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100">
          {JSON.stringify(app.evidence.form, null, 2)}
        </pre>
      </div>
    </div>
  );
}
