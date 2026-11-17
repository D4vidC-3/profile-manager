"use client";

import { FormEvent, useEffect, useState } from "react";
import { api, Catalogs, Expectations, Profile } from "@/lib/api";
import { ChipSelect, TagInput } from "@/components/forms";
import { ErrorBox } from "@/components/ui";

const MODALITY_LABEL: Record<string, string> = { presencial: "Presencial", hibrido: "Híbrido", remoto: "Remoto" };

export default function PreferencesForm({
  initial,
  suggestions,
  onSubmit,
  submitLabel = "Ver mis recomendaciones",
}: {
  initial: Expectations;
  suggestions?: Profile["suggestions"];
  onSubmit: (prefs: Expectations) => Promise<void>;
  submitLabel?: string;
}) {
  const [cat, setCat] = useState<Catalogs | null>(null);
  const [v, setV] = useState<Expectations>(initial);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<Catalogs>("/api/catalogs").then(setCat).catch((e) => setError(e.message));
  }, []);

  const set = <K extends keyof Expectations>(k: K, val: Expectations[K]) => setV((x) => ({ ...x, [k]: val }));
  const sRoles = (suggestions?.roles ?? []).filter((r) => !v.desired_roles.includes(r));
  const sSectors = (suggestions?.sectors ?? []).filter((r) => !v.sectors.includes(r));

  async function submit(e: FormEvent) {
    e.preventDefault();
    const missing = [
      !v.desired_roles.length && "cargos",
      !v.sectors.length && "sectores",
      !v.city && "ciudad",
      !v.modality && "modalidad",
      !v.workday.length && "jornada",
      !v.salary_min_cop && "salario",
    ].filter(Boolean);
    if (missing.length) return setError(`Completa: ${missing.join(", ")}`);
    setBusy(true);
    setError(null);
    try {
      await onSubmit(v);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!cat) return <ErrorBox msg={error} />;

  return (
    <form onSubmit={submit} className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold">¿Qué estás buscando?</h2>
        <p className="text-sm text-slate-600">
          Esto no está en tu hoja de vida: cuéntanos qué buscas para recomendarte vacantes. Los campos con * son
          necesarios.
        </p>
      </div>

      <div>
        <label className="label">Cargos que buscas *</label>
        <TagInput value={v.desired_roles} onChange={(x) => set("desired_roles", x.slice(0, 5))} placeholder="Ej. Analista de datos (Enter)" />
        {sRoles.length > 0 && (
          <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs">
            <span className="text-fuchsia-700">✨ Sugeridos según tu CV:</span>
            {sRoles.map((r) => (
              <button type="button" key={r} className="rounded-full border border-fuchsia-300 px-2 py-0.5 text-fuchsia-800 hover:bg-fuchsia-50" onClick={() => set("desired_roles", [...v.desired_roles, r])}>
                + {r}
              </button>
            ))}
          </div>
        )}
      </div>

      <div>
        <label className="label">Sectores laborales * (hasta 5)</label>
        <select className="input" value="" onChange={(e) => e.target.value && set("sectors", [...v.sectors, e.target.value].slice(0, 5))}>
          <option value="">Selecciona sectores…</option>
          {cat.sectors.filter((s) => !v.sectors.includes(s)).map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {v.sectors.map((s) => (
            <span key={s} className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-0.5 text-xs">
              {s}
              <button type="button" className="text-slate-400 hover:text-red-600" onClick={() => set("sectors", v.sectors.filter((x) => x !== s))}>
                ×
              </button>
            </span>
          ))}
          {sSectors.map((s) => (
            <button type="button" key={s} className="rounded-full border border-fuchsia-300 px-2 py-0.5 text-xs text-fuchsia-800 hover:bg-fuchsia-50" onClick={() => set("sectors", [...v.sectors, s])}>
              ✨ + {s}
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <label className="label">¿Dónde quieres trabajar? (ciudad) *</label>
          <input className="input" value={v.city ?? ""} onChange={(e) => set("city", e.target.value || null)} placeholder="Medellín" />
        </div>
        <div>
          <label className="label">Modalidad *</label>
          <ChipSelect multiple={false} options={cat.modalities} labels={MODALITY_LABEL} value={v.modality ? [v.modality] : []} onChange={(x) => set("modality", x[0] ?? null)} />
        </div>
      </div>

      <div>
        <label className="label">Jornada *</label>
        <ChipSelect options={cat.workdays} value={v.workday} onChange={(x) => set("workday", x)} />
      </div>

      <div className="grid gap-4 md:grid-cols-[1fr_180px]">
        <div>
          <label className="label">Salario mínimo aceptado (COP) *</label>
          <input
            className="input"
            inputMode="numeric"
            placeholder="3500000"
            value={v.salary_min_cop ?? ""}
            onChange={(e) => set("salary_min_cop", Number(e.target.value.replace(/\D/g, "")) || null)}
          />
          {v.salary_min_cop ? <p className="mt-1 text-xs text-slate-500">${v.salary_min_cop.toLocaleString("es-CO")} {v.salary_frequency}</p> : null}
        </div>
        <div>
          <label className="label">Frecuencia de pago</label>
          <select className="input" value={v.salary_frequency} onChange={(e) => set("salary_frequency", e.target.value)}>
            {cat.salary_frequencies.map((f) => (
              <option key={f}>{f}</option>
            ))}
          </select>
        </div>
      </div>

      <div>
        <label className="label">Disponible para (tipo de vinculación)</label>
        <ChipSelect options={cat.contract_types} value={v.contract_types} onChange={(x) => set("contract_types", x)} />
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div>
          <label className="label">¿Cuándo puedes empezar?</label>
          <select className="input" value={v.availability ?? ""} onChange={(e) => set("availability", e.target.value || null)}>
            <option value="">—</option>
            {cat.availability.map((a) => (
              <option key={a}>{a}</option>
            ))}
          </select>
        </div>
        <label className="flex items-center gap-2 self-end text-sm">
          <input type="checkbox" checked={!!v.willing_to_travel} onChange={(e) => set("willing_to_travel", e.target.checked)} />
          Disponible para viajar
        </label>
        <label className="flex items-center gap-2 self-end text-sm">
          <input type="checkbox" checked={!!v.willing_to_relocate} onChange={(e) => set("willing_to_relocate", e.target.checked)} />
          Disponible para cambio de domicilio
        </label>
      </div>

      <ErrorBox msg={error} />
      <button className="btn" disabled={busy}>
        {busy ? "Guardando…" : submitLabel}
      </button>
    </form>
  );
}
