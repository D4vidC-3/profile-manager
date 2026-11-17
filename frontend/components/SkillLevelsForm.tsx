"use client";

import { FormEvent, useState } from "react";
import { api, FlowResponse, SKILL_KINDS, SKILL_LEVEL_LABEL, SkillLevel, SkillLevelsPending } from "@/lib/api";
import { ErrorBox } from "@/components/ui";

const LEVELS: SkillLevel[] = ["basico", "intermedio", "avanzado"];

export default function SkillLevelsForm({ pending, onDone }: { pending: SkillLevelsPending; onDone: (r: FlowResponse) => void }) {
  const [levels, setLevels] = useState<Record<string, SkillLevel | null>>(
    Object.fromEntries(pending.skills.map((s) => [s.name, s.level])),  // los sugeridos por la IA vienen marcados
  );
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const missing = pending.skills.filter((s) => !levels[s.name]).length;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (missing) return setError(`Falta el nivel de ${missing} habilidad(es)`);
    setBusy(true);
    setError(null);
    try {
      onDone(
        await api<FlowResponse>("/api/applications/skill-levels", {
          method: "POST",
          body: JSON.stringify({ levels }),
        }),
      );
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="card space-y-4 border-sky-300">
      <div>
        <h2 className="text-lg font-semibold">Antes de postular: ¿qué nivel tienes en cada habilidad?</h2>
        <p className="text-sm text-slate-600">
          Es obligatorio para postular: las empresas necesitan saber qué tan bien manejas cada herramienta y
          conocimiento. Las habilidades transversales no llevan nivel. Lo que marques se guarda en tu perfil.
        </p>
      </div>
      {SKILL_KINDS.filter((k) => k.value !== "transversal").map((k) => {
        const items = pending.skills.filter((s) => s.kind === k.value);
        if (!items.length) return null;
        return (
          <div key={k.value} className="space-y-1.5">
            <h3 className="text-sm font-semibold text-slate-700">{k.label}</h3>
            {items.map((s) => (
              <div key={s.name} className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 px-3 py-2">
                <span className="min-w-[160px] font-medium">{s.name}</span>
                {LEVELS.map((lv) => (
                  <button
                    type="button"
                    key={lv}
                    onClick={() => setLevels({ ...levels, [s.name]: lv })}
                    className={`rounded-md border px-3 py-1 text-xs ${
                      levels[s.name] === lv ? "border-slate-900 bg-slate-900 text-white" : "border-slate-300 bg-white text-slate-600 hover:bg-slate-50"
                    }`}
                  >
                    {SKILL_LEVEL_LABEL[lv]}
                  </button>
                ))}
                {s.suggested && s.evidence && levels[s.name] === s.level && (
                  <span className="text-xs text-fuchsia-700">✨ sugerido: {s.evidence}</span>
                )}
              </div>
            ))}
          </div>
        );
      })}
      <ErrorBox msg={error} />
      <button className="btn" disabled={busy}>
        {busy ? "Guardando…" : missing ? `Faltan ${missing} nivel(es)` : "Confirmar niveles y continuar"}
      </button>
    </form>
  );
}
