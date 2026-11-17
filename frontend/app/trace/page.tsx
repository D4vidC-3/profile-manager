"use client";

import { useEffect, useMemo, useState } from "react";
import { AGENT_META, api, TraceEvent } from "@/lib/api";
import { AgentBadge, ErrorBox, ModeBadge, Spinner } from "@/components/ui";

const FILTERS = ["todos", "perfil", "vacantes", "postulacion", "seguimiento", "candidato", "portal", "orquestador"];

export default function TracePage() {
  const [events, setEvents] = useState<TraceEvent[] | null>(null);
  const [filter, setFilter] = useState("todos");
  const [expanded, setExpanded] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<TraceEvent[]>("/api/trace")
      .then(setEvents)
      .catch((e) => setError(e.message));
  }, []);

  const shown = useMemo(
    () => (events ?? []).filter((e) => filter === "todos" || e.agent === filter).slice().reverse(),
    [events, filter],
  );

  const stats = useMemo(() => {
    const s = { llm: 0, rules: 0, human: 0, system: 0 } as Record<string, number>;
    (events ?? []).forEach((e) => (s[e.mode] = (s[e.mode] ?? 0) + 1));
    return s;
  }, [events]);

  if (!events) return error ? <ErrorBox msg={error} /> : <Spinner text="Cargando trazas…" />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Panel de trazabilidad</h1>
        <p className="text-slate-600">Qué hizo cada agente, cuándo y <b>por qué</b>. Incluye si usó IA o reglas.</p>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          ["Eventos", events.length],
          ["Decisiones con IA", stats.llm],
          ["Decisiones por reglas", stats.rules],
          ["Acciones del candidato", stats.human],
        ].map(([label, value]) => (
          <div key={label} className="card py-3">
            <p className="text-xs text-slate-500">{label}</p>
            <p className="text-2xl font-bold">{value}</p>
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`rounded-full border px-3 py-1 text-sm ${
              filter === f ? "border-slate-900 bg-slate-900 text-white" : "border-slate-300 bg-white text-slate-700"
            }`}
          >
            {f === "todos" ? "Todos" : AGENT_META[f]?.label ?? f}
          </button>
        ))}
      </div>
      {shown.length === 0 && <div className="card text-slate-500">No hay eventos todavía.</div>}
      <ol className="relative space-y-3 border-l-2 border-slate-200 pl-6">
        {shown.map((e) => (
          <li key={e.id} className="relative">
            <span className="absolute -left-[31px] top-4 h-3 w-3 rounded-full border-2 border-white bg-slate-400" />
            <div className="card py-3">
              <div className="flex flex-wrap items-center gap-2">
                <AgentBadge agent={e.agent} />
                <ModeBadge mode={e.mode} provider={e.provider} />
                <span className="text-xs text-slate-400">
                  día {e.sim_day} · {new Date(e.created_at).toLocaleTimeString("es-CO")}
                  {e.duration_ms ? ` · ${e.duration_ms} ms` : ""}
                </span>
              </div>
              <p className="mt-2 font-medium">{e.action}</p>
              <p className="text-sm text-slate-600">
                <span className="font-semibold text-slate-700">Por qué: </span>
                {e.reason}
              </p>
              {Object.keys(e.details ?? {}).length > 0 && (
                <button className="mt-1 text-xs text-sky-700 underline" onClick={() => setExpanded(expanded === e.id ? null : e.id)}>
                  {expanded === e.id ? "Ocultar detalles" : "Ver detalles"}
                </button>
              )}
              {expanded === e.id && (
                <pre className="mt-2 max-h-72 overflow-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100">
                  {JSON.stringify(e.details, null, 2)}
                </pre>
              )}
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
