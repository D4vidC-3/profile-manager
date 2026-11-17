"use client";

import { ReactNode, useState } from "react";
import { api, cop, Expectations, Profile, ProfileView } from "@/lib/api";
import { languageLabel, LanguagesCard, ProjectsEditor, ProvenanceBadge, SkillsAccordion, SkillsEditor } from "@/components/forms";
import { ErrorBox, ScoreBar } from "@/components/ui";
import PreferencesForm from "@/components/PreferencesForm";

export interface SaveResult {
  stage: string;
  recalculated: boolean;
  changed: string[];
  view: ProfileView;
}

type Key = keyof Profile;

/* ---------------------------------------------------------------- sección con lápiz */
type Draft = Partial<Profile>;

function Section({
  title,
  fields,
  profile,
  render,
  editor,
  onSave,
}: {
  title: string;
  fields: Key[];
  profile: Profile;
  render: () => ReactNode;
  editor: (draft: Draft, set: (d: Draft) => void) => ReactNode;
  onSave: (patch: Draft) => Promise<void>;
}) {
  const pick = () => structuredClone(Object.fromEntries(fields.map((f) => [f, profile[f]])) as Draft);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Draft>(pick);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      await onSave(draft);
      setEditing(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="border-t border-slate-100 pt-4">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <h3 className="font-semibold">{title}</h3>
        <ProvenanceBadge source={profile.provenance[fields[0] as string]} />
        {!editing && (
          <button
            className="ml-auto text-sm text-sky-700 hover:underline"
            onClick={() => {
              setDraft(pick());
              setEditing(true);
            }}
          >
            ✏️ Editar
          </button>
        )}
      </div>
      {editing ? (
        <div className="space-y-3 rounded-lg bg-slate-50 p-3">
          {editor(draft, setDraft)}
          <ErrorBox msg={error} />
          <div className="flex gap-2">
            <button className="btn" disabled={busy} onClick={save}>
              {busy ? "Guardando…" : "Guardar"}
            </button>
            <button className="btn-secondary" onClick={() => setEditing(false)}>
              Cancelar
            </button>
          </div>
        </div>
      ) : (
        render()
      )}
    </section>
  );
}

function TextField({ label, value, onChange, area = false }: { label: string; value: string | null | undefined; onChange: (v: string | null) => void; area?: boolean }) {
  return (
    <label className={`text-sm ${area ? "sm:col-span-2" : ""}`}>
      <span className="label">{label}</span>
      {area ? (
        <textarea className="input" rows={3} maxLength={800} value={value ?? ""} onChange={(e) => onChange(e.target.value || null)} />
      ) : (
        <input className="input" value={value ?? ""} onChange={(e) => onChange(e.target.value || null)} />
      )}
    </label>
  );
}

/* ---------------------------------------------------------------- editores de listas */
function ListEditor<T extends object>({
  items,
  onChange,
  empty,
  fields,
}: {
  items: T[];
  onChange: (v: T[]) => void;
  empty: T;
  fields: { key: keyof T; label: string; type?: "text" | "checkbox" | "select" | "textarea"; options?: string[] }[];
}) {
  return (
    <div className="space-y-3">
      {items.map((it, i) => (
        <div key={i} className="grid gap-2 rounded-lg border border-slate-200 bg-white p-3 sm:grid-cols-2">
          {fields.map((f) => {
            const val = it[f.key] as unknown;
            const set = (v: unknown) => onChange(items.map((x, j) => (j === i ? { ...x, [f.key]: v } : x)));
            if (f.type === "checkbox")
              return (
                <label key={String(f.key)} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={!!val} onChange={(e) => set(e.target.checked)} /> {f.label}
                </label>
              );
            if (f.type === "select")
              return (
                <label key={String(f.key)} className="text-sm">
                  <span className="label">{f.label}</span>
                  <select className="input" value={(val as string) ?? ""} onChange={(e) => set(e.target.value || null)}>
                    <option value="">—</option>
                    {f.options?.map((o) => (
                      <option key={o}>{o}</option>
                    ))}
                  </select>
                </label>
              );
            if (f.type === "textarea")
              return (
                <label key={String(f.key)} className="text-sm sm:col-span-2">
                  <span className="label">{f.label}</span>
                  <textarea className="input" rows={2} value={(val as string) ?? ""} onChange={(e) => set(e.target.value || null)} />
                </label>
              );
            return (
              <label key={String(f.key)} className="text-sm">
                <span className="label">{f.label}</span>
                <input className="input" value={(val as string) ?? ""} onChange={(e) => set(e.target.value || null)} />
              </label>
            );
          })}
          <button
            type="button"
            className="justify-self-start text-xs text-slate-400 hover:text-red-600"
            onClick={() => onChange(items.filter((_, j) => j !== i))}
          >
            Eliminar
          </button>
        </div>
      ))}
      <button type="button" className="btn-secondary" onClick={() => onChange([...items, { ...empty }])}>
        + Agregar
      </button>
    </div>
  );
}

/* ---------------------------------------------------------------- tarjeta principal */
export default function ProfileEditor({
  view,
  onSaved,
}: {
  view: ProfileView;
  onSaved: (r: SaveResult) => void;
}) {
  const p = view.profile;
  const [editPrefs, setEditPrefs] = useState(false);

  async function save(patch: Partial<Profile>) {
    const r = await api<SaveResult>("/api/profile", { method: "PUT", body: JSON.stringify(patch) });
    onSaved(r);
  }

  const cvMissing = view.cv_gaps.filter((g) => g.input_type !== "info" || g.field !== "projects");
  const e = p.expectations;

  return (
    <div className="space-y-4">
      {/* ------ dos indicadores separados ------ */}
      <div className="grid gap-4 md:grid-cols-2">
        <div className="card space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Tu hoja de vida</h2>
            <span className="text-xl font-bold">{view.cv.score}%</span>
          </div>
          <ScoreBar value={view.cv.score} />
          {view.cv.mode === "primer_empleo" && (
            <p className="rounded-md bg-sky-50 px-2 py-1 text-xs text-sky-800">
              🎓 Primer empleo ({view.cv.reason}): la experiencia no se exige; cuentan más tus estudios, habilidades y
              proyectos.
            </p>
          )}
          {cvMissing.length > 0 ? (
            <ul className="text-sm text-amber-800">
              {cvMissing.map((g) => (
                <li key={g.field}>
                  {g.critical ? "⛔" : "⚠"} {g.label}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-emerald-700">✅ Tu hoja de vida está completa.</p>
          )}
        </div>
        <div className="card space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Lo que buscas</h2>
            <span className="text-xl font-bold">{view.preferences.score}%</span>
          </div>
          <ScoreBar value={view.preferences.score} />
          <ul className="text-sm text-slate-700">
            <li>Cargos: {e.desired_roles.join(", ") || "—"}</li>
            <li>Sectores: {e.sectors.join(", ") || "—"}</li>
            <li>
              Modalidad: {e.modality ?? "—"} · Jornada: {e.workday.join(", ") || "—"}
            </li>
            <li>
              Salario mínimo: {cop(e.salary_min_cop)} {e.salary_min_cop ? e.salary_frequency : ""}
            </li>
          </ul>
          <button className="text-sm text-sky-700 hover:underline" onClick={() => setEditPrefs(!editPrefs)}>
            ✏️ {editPrefs ? "Cerrar" : "Editar preferencias"}
          </button>
        </div>
      </div>
      {editPrefs && (
        <div className="card">
          <PreferencesForm
            initial={e}
            suggestions={p.suggestions}
            submitLabel="Guardar preferencias"
            onSubmit={async (prefs: Expectations) => {
              await save({ expectations: prefs });
              setEditPrefs(false);
            }}
          />
        </div>
      )}

      {/* ------ hoja de vida por secciones ------ */}
      <div className="card space-y-4">
        <div>
          <h2 className="text-xl font-semibold">{p.full_name ?? "Sin nombre"}</h2>
          <p className="text-slate-600">{p.headline ?? "—"}</p>
          <p className="mt-1 text-xs text-slate-500">
            Cada dato muestra de dónde salió: 📄 del CV · ✨ sugerido por IA · ✏️ editado por ti. Lo que edites queda
            protegido aunque subas otro CV.
          </p>
        </div>

        <Section
          title="Contacto"
          fields={["full_name", "email", "phone", "city", "linkedin", "github", "portfolio"]}
          profile={p}
          onSave={save}
          render={() => (
            <p className="text-sm text-slate-700">
              {[p.full_name, p.email, p.phone, [p.city, p.department].filter(Boolean).join(", "), p.linkedin, p.github, p.portfolio]
                .filter(Boolean)
                .join(" · ") || "—"}
            </p>
          )}
          editor={(d, set) => (
            <div className="grid gap-2 sm:grid-cols-2">
              <TextField label="Nombre completo" value={d.full_name} onChange={(v) => set({ ...d, full_name: v })} />
              <TextField label="Correo" value={d.email} onChange={(v) => set({ ...d, email: v })} />
              <TextField label="Teléfono" value={d.phone} onChange={(v) => set({ ...d, phone: v })} />
              <TextField label="Ciudad" value={d.city} onChange={(v) => set({ ...d, city: v })} />
              <TextField label="LinkedIn" value={d.linkedin} onChange={(v) => set({ ...d, linkedin: v })} />
              <TextField label="GitHub" value={d.github} onChange={(v) => set({ ...d, github: v })} />
              <TextField label="Portafolio" value={d.portfolio} onChange={(v) => set({ ...d, portfolio: v })} />
            </div>
          )}
        />

        <Section
          title="Perfil profesional"
          fields={["headline", "summary"]}
          profile={p}
          onSave={save}
          render={() => <p className="text-sm text-slate-700">{p.summary ?? "—"}</p>}
          editor={(d, set) => (
            <div className="grid gap-2">
              <TextField label="Titular (ej. Auxiliar de soporte TI)" value={d.headline} onChange={(v) => set({ ...d, headline: v })} />
              <TextField label="Resumen profesional (2–3 líneas)" area value={d.summary} onChange={(v) => set({ ...d, summary: v })} />
            </div>
          )}
        />

        <Section
          title="Habilidades"
          fields={["skills"]}
          profile={p}
          onSave={save}
          render={() => <SkillsAccordion skills={p.skills} demonstrated={p.demonstrated_skills} />}
          editor={(d, set) => <SkillsEditor value={d.skills ?? []} onChange={(v) => set({ ...d, skills: v })} />}
        />

        <Section
          title={`Experiencia (${p.years_experience ?? 0} años · ${p.seniority ?? "?"})`}
          fields={["experiences"]}
          profile={p}
          onSave={save}
          render={() =>
            p.experiences.length ? (
              <ul className="space-y-1 text-sm text-slate-700">
                {p.experiences.map((x, i) => (
                  <li key={i}>
                    <b>{x.title}</b>
                    {x.company ? ` — ${x.company}` : ""} {x.city ? `· ${x.city}` : ""}{" "}
                    <span className="text-slate-400">
                      ({x.start ?? "?"} – {x.current ? "Actual" : x.end ?? "?"})
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate-500">{p.first_job ? "Primer empleo: no se exige experiencia." : "Sin experiencia registrada."}</p>
            )
          }
          editor={(d, set) => (
            <ListEditor
              items={d.experiences ?? []}
              onChange={(v) => set({ ...d, experiences: v })}
              empty={{ title: "", company: null, city: null, start: null, end: null, current: false, description: null }}
              fields={[
                { key: "title", label: "Cargo" },
                { key: "company", label: "Empresa" },
                { key: "city", label: "Ciudad" },
                { key: "start", label: "Inicio (ej. Feb 2024)" },
                { key: "end", label: "Fin (ej. Dic 2025)" },
                { key: "current", label: "Trabajo actual", type: "checkbox" },
                { key: "description", label: "Funciones y logros", type: "textarea" },
              ]}
            />
          )}
        />

        <Section
          title="Proyectos"
          fields={["projects"]}
          profile={p}
          onSave={save}
          render={() =>
            p.projects.length ? (
              <ul className="space-y-1 text-sm text-slate-700">
                {p.projects.map((x, i) => (
                  <li key={i}>
                    <b>{x.name}</b> {x.technologies.length ? `· ${x.technologies.join(", ")}` : ""}{" "}
                    <span className="text-xs text-slate-500">[{x.evidence.replace("_", " ")}]</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate-500">
                {p.first_job
                  ? "Aún no tienes experiencia laboral: agrega un proyecto para mostrar lo que sabes hacer."
                  : (p.suggestions.projects_for?.length ?? 0) > 0
                    ? `Sugerencia: agrega un proyecto donde uses ${p.suggestions.projects_for?.join(", ")} para respaldar tu cambio de carrera.`
                    : "Opcional: los proyectos te ayudan a destacar en el matching."}
              </p>
            )
          }
          editor={(d, set) => <ProjectsEditor value={d.projects ?? []} onChange={(v) => set({ ...d, projects: v })} />}
        />

        <Section
          title="Educación"
          fields={["education"]}
          profile={p}
          onSave={save}
          render={() => (
            <ul className="space-y-1 text-sm text-slate-700">
              {p.education.map((x, i) => (
                <li key={i}>
                  {x.degree}
                  {x.institution ? ` — ${x.institution}` : ""}{" "}
                  <span className="text-slate-400">
                    ({x.status === "en_curso" ? `en curso${x.semester ? `, semestre ${x.semester}` : ""}` : x.year ?? "año ?"})
                  </span>
                </li>
              ))}
              {p.education.length === 0 && <li className="text-slate-500">—</li>}
            </ul>
          )}
          editor={(d, set) => (
            <ListEditor
              items={d.education ?? []}
              onChange={(v) => set({ ...d, education: v })}
              empty={{ degree: "", institution: null, level: null, year: null, status: null, semester: null }}
              fields={[
                { key: "degree", label: "Título" },
                { key: "institution", label: "Institución" },
                {
                  key: "level",
                  label: "Nivel",
                  type: "select",
                  options: ["bachiller", "técnico", "tecnólogo", "profesional", "especialización", "maestría", "doctorado"],
                },
                { key: "status", label: "Estado", type: "select", options: ["finalizado", "en_curso"] },
                { key: "year", label: "Año de grado" },
              ]}
            />
          )}
        />

        <Section
          title="Cursos y certificaciones"
          fields={["certifications"]}
          profile={p}
          onSave={save}
          render={() => (
            <ul className="space-y-1 text-sm text-slate-700">
              {p.certifications.map((x, i) => (
                <li key={i}>
                  {x.name}
                  {x.issuer ? ` — ${x.issuer}` : ""} {x.year ? `(${x.year})` : ""}
                </li>
              ))}
              {p.certifications.length === 0 && <li className="text-slate-500">— (recomendado)</li>}
            </ul>
          )}
          editor={(d, set) => (
            <ListEditor
              items={d.certifications ?? []}
              onChange={(v) => set({ ...d, certifications: v })}
              empty={{ name: "", issuer: null, year: null }}
              fields={[
                { key: "name", label: "Nombre" },
                { key: "issuer", label: "Entidad" },
                { key: "year", label: "Año" },
              ]}
            />
          )}
        />

        <Section
          title="Idiomas"
          fields={["languages"]}
          profile={p}
          onSave={save}
          render={() => (
            <ul className="text-sm text-slate-700">
              {p.languages.map((l) => (
                <li key={l.name}>
                  {l.name}:{" "}
                  {l.level || l.cefr ? <b>{languageLabel(l)}</b> : <span className="text-amber-700">nivel pendiente</span>}{" "}
                  {l.suggested && <span className="text-xs text-fuchsia-700">✨ sugerido, confírmalo</span>}
                </li>
              ))}
              {p.languages.length === 0 && <li className="text-slate-500">—</li>}
            </ul>
          )}
          editor={(d, set) => <LanguagesCard value={d.languages ?? []} onChange={(v) => set({ ...d, languages: v })} />}
        />
      </div>
    </div>
  );
}

