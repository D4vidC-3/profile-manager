"use client";

import { FormEvent, useState } from "react";
import { CvScore, Gap, Language, Project, Skill } from "@/lib/api";
import { LanguagesCard, ProjectsEditor, SkillsEditor } from "@/components/forms";
import { ErrorBox, ScoreBar } from "@/components/ui";

export default function CvGapsForm({
  gaps,
  cv,
  onSubmit,
}: {
  gaps: Gap[];
  cv: CvScore;
  onSubmit: (answers: Record<string, unknown>) => Promise<void>;
}) {
  const [text, setText] = useState<Record<string, string>>({});
  const skillGap = gaps.find((g) => g.field === "skills");
  const [skills, setSkills] = useState<Skill[]>((skillGap?.items as Skill[]) ?? []);
  const langGap = gaps.find((g) => g.input_type === "languages");
  const [languages, setLanguages] = useState<Language[]>((langGap?.items as Language[]) ?? []);
  const projGap = gaps.find((g) => g.input_type === "projects");
  const [projects, setProjects] = useState<Project[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const critical = gaps.filter((g) => g.critical);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const answers: Record<string, unknown> = { ...Object.fromEntries(Object.entries(text).filter(([, v]) => v.trim())) };
    if (skillGap && skills.length) answers.skills = skills; // lista completa con tipo y nivel
    if (langGap) answers.languages = languages;
    if (projects.some((p) => p.name.trim())) answers.projects = projects.filter((p) => p.name.trim());
    setBusy(true);
    setError(null);
    try {
      await onSubmit(answers);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="card space-y-5 border-amber-300">
      <div>
        <h2 className="text-lg font-semibold">Revisemos tu hoja de vida</h2>
        <p className="text-sm text-slate-600">
          Completitud: <b>{cv.score}%</b>
          {cv.mode === "primer_empleo" && " · 🎓 Primer empleo: no se exige experiencia"}.{" "}
          {critical.length ? "Los campos con * son necesarios para continuar." : "Todo lo de aquí es opcional, pero mejora tus resultados."}
        </p>
        <div className="mt-2">
          <ScoreBar value={cv.score} />
        </div>
      </div>

      {gaps
        .filter((g) => ["text", "number"].includes(g.input_type))
        .map((g) => (
          <div key={g.field}>
            <label className="label">
              {g.question} {g.critical && <span className="text-red-600">*</span>}
            </label>
            {g.field === "summary" ? (
              <textarea className="input" rows={2} value={text[g.field] ?? ""} onChange={(e) => setText({ ...text, [g.field]: e.target.value })} />
            ) : (
              <input className="input" value={text[g.field] ?? ""} onChange={(e) => setText({ ...text, [g.field]: e.target.value })} />
            )}
          </div>
        ))}

      {gaps.some((g) => g.field === "skills") && (
        <div>
          <label className="label">
            {gaps.find((g) => g.field === "skills")?.question}{" "}
            {gaps.find((g) => g.field === "skills")?.critical && <span className="text-red-600">*</span>}
          </label>
          <SkillsEditor value={skills} onChange={setSkills} />
        </div>
      )}

      {langGap && (
        <div>
          <label className="label">Idiomas — {langGap.question}</label>
          <LanguagesCard value={languages} onChange={setLanguages} />
        </div>
      )}

      {projGap && (
        <div>
          <label className="label">Proyectos (opcional) — {projGap.question}</label>
          <ProjectsEditor value={projects} onChange={setProjects} />
        </div>
      )}

      <ErrorBox msg={error} />
      <button className="btn" disabled={busy}>
        {busy ? "Guardando…" : critical.length ? "Guardar y continuar" : "Continuar"}
      </button>
    </form>
  );
}
