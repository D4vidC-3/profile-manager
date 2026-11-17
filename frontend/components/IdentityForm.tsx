"use client";

import { FormEvent, useState } from "react";
import { api, FlowResponse, IdentityPending } from "@/lib/api";
import { ErrorBox } from "@/components/ui";

export default function IdentityForm({ pending, onDone }: { pending: IdentityPending; onDone: (r: FlowResponse) => void }) {
  const [v, setV] = useState<Record<string, string>>(
    Object.fromEntries(pending.fields.map((f) => [f.field, (pending.values[f.field] as string) ?? ""])),
  );
  const [consent, setConsent] = useState(false);
  const [sex, setSex] = useState("");
  const [birth, setBirth] = useState("");
  const [disability, setDisability] = useState<"" | "si" | "no">("");
  const [disType, setDisType] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const body: Record<string, unknown> = Object.fromEntries(Object.entries(v).filter(([, x]) => x.trim()));
    if (consent) {
      body.sensitive = {
        consent: true,
        sex: sex || null,
        birth_date: birth || null,
        disability: disability === "" ? null : disability === "si",
        disability_type: disability === "si" ? disType || null : null,
      };
    }
    try {
      onDone(await api<FlowResponse>("/api/applications/identity", { method: "POST", body: JSON.stringify(body) }));
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="card space-y-4 border-sky-300">
      <div>
        <h2 className="text-lg font-semibold">Antes de postular: tus datos de identidad</h2>
        <p className="text-sm text-slate-600">
          Las empresas exigen documento de identidad para evitar postulaciones duplicadas. Solo lo pedimos ahora que vas
          a postular, y no se guarda en la evidencia de la postulación.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {pending.fields.map((f) => (
          <label key={f.field} className="text-sm">
            <span className="label">
              {f.label} {pending.missing.includes(f.field) && <span className="text-red-600">*</span>}
            </span>
            {f.input_type === "select" ? (
              <select className="input" value={v[f.field]} onChange={(e) => setV({ ...v, [f.field]: e.target.value })}>
                <option value="">—</option>
                {f.options.map((o) => (
                  <option key={o}>{o}</option>
                ))}
              </select>
            ) : (
              <input className="input" value={v[f.field]} onChange={(e) => setV({ ...v, [f.field]: e.target.value })} />
            )}
          </label>
        ))}
      </div>

      <details className="rounded-lg border border-slate-200 p-3 text-sm">
        <summary className="cursor-pointer font-medium">Datos adicionales opcionales (Servicio Público de Empleo)</summary>
        <p className="mt-2 text-xs text-slate-500">
          Son datos sensibles (Ley 1581 de 2012). Son opcionales, solo se guardan con tu autorización y{" "}
          <b>nunca se usan para calcular tus recomendaciones</b>. La discapacidad solo serviría para destacarte vacantes
          de inclusión.
        </p>
        <label className="mt-2 flex items-center gap-2">
          <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} /> Autorizo el
          tratamiento de estos datos
        </label>
        {consent && (
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <label>
              <span className="label">Sexo registrado en el documento</span>
              <select className="input" value={sex} onChange={(e) => setSex(e.target.value)}>
                <option value="">—</option>
                {pending.sensitive.sex_options.map((o) => (
                  <option key={o}>{o}</option>
                ))}
              </select>
            </label>
            <label>
              <span className="label">Fecha de nacimiento</span>
              <input type="date" className="input" value={birth} onChange={(e) => setBirth(e.target.value)} />
            </label>
            <label>
              <span className="label">¿Tienes alguna discapacidad?</span>
              <select className="input" value={disability} onChange={(e) => setDisability(e.target.value as "" | "si" | "no")}>
                <option value="">Prefiero no decir</option>
                <option value="si">Sí</option>
                <option value="no">No</option>
              </select>
            </label>
            {disability === "si" && (
              <label>
                <span className="label">Tipo</span>
                <select className="input" value={disType} onChange={(e) => setDisType(e.target.value)}>
                  <option value="">—</option>
                  {pending.sensitive.disability_types.map((o) => (
                    <option key={o}>{o}</option>
                  ))}
                </select>
              </label>
            )}
          </div>
        )}
      </details>

      <ErrorBox msg={error} />
      <button className="btn" disabled={busy}>
        {busy ? "Postulando…" : "Confirmar y postular"}
      </button>
    </form>
  );
}
