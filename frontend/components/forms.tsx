"use client";

import { KeyboardEvent, useEffect, useState } from "react";
import {
  api,
  EVIDENCE_LABEL,
  Language,
  LanguageLevel,
  LEVEL_LABEL,
  Project,
  PROVENANCE,
  Skill,
  SKILL_KINDS,
  SKILL_LEVEL_LABEL,
  SkillKind,
  SkillLevel,
} from "@/lib/api";

/* ---------------------------------------------------------------- etiquetas con "×" y "+ agregar" */
export function TagInput({
  value,
  onChange,
  placeholder = "Escribe y presiona Enter",
  highlight = [],
}: {
  value: string[];
  onChange: (v: string[]) => void;
  placeholder?: string;
  highlight?: string[];
}) {
  const [draft, setDraft] = useState("");
  const hl = new Set(highlight.map((h) => h.toLowerCase()));

  function add() {
    const items = draft.split(",").map((s) => s.trim()).filter(Boolean);
    const lower = new Set(value.map((v) => v.toLowerCase()));
    const next = [...value, ...items.filter((i) => !lower.has(i.toLowerCase()))];
    onChange(next);
    setDraft("");
  }

  function onKey(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      add();
    }
  }

  return (
    <div className="rounded-lg border border-slate-300 bg-white p-2">
      <div className="flex flex-wrap gap-1.5">
        {value.map((t) => (
          <span
            key={t}
            className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs ${
              hl.has(t.toLowerCase()) ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-700"
            }`}
            title={hl.has(t.toLowerCase()) ? "Demostrada en tu experiencia o proyectos" : undefined}
          >
            {hl.has(t.toLowerCase()) && "✓ "}
            {t}
            <button
              type="button"
              aria-label={`Quitar ${t}`}
              className="text-slate-400 hover:text-red-600"
              onClick={() => onChange(value.filter((v) => v !== t))}
            >
              ×
            </button>
          </span>
        ))}
        <input
          className="min-w-[160px] flex-1 px-1 text-sm outline-none"
          value={draft}
          placeholder={placeholder}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKey}
          onBlur={() => draft.trim() && add()}
        />
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- selección con chips */
export function ChipSelect({
  options,
  value,
  onChange,
  multiple = true,
  labels,
}: {
  options: string[];
  value: string[];
  onChange: (v: string[]) => void;
  multiple?: boolean;
  labels?: Record<string, string>;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((o) => {
        const on = value.includes(o);
        return (
          <button
            type="button"
            key={o}
            onClick={() =>
              onChange(multiple ? (on ? value.filter((v) => v !== o) : [...value, o]) : on ? [] : [o])
            }
            className={`rounded-lg border px-3 py-1.5 text-sm transition ${
              on ? "border-slate-900 bg-slate-900 text-white" : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
            }`}
          >
            {labels?.[o] ?? o}
          </button>
        );
      })}
    </div>
  );
}

/* ---------------------------------------------------------------- procedencia del dato */
export function ProvenanceBadge({ source }: { source?: string }) {
  if (!source || !PROVENANCE[source]) return null;
  const p = PROVENANCE[source];
  return <span className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${p.color}`}>{p.label}</span>;
}

/* ---------------------------------------------------------------- idiomas con nivel (MCER) */
const CEFR = [
  { value: "A1", hint: "Básico: frases muy sencillas" },
  { value: "A2", hint: "Básico: temas cotidianos" },
  { value: "B1", hint: "Intermedio: te defiendes en el trabajo" },
  { value: "B2", hint: "Intermedio alto: reuniones y correos con fluidez" },
  { value: "C1", hint: "Avanzado: presentaciones y documentos complejos" },
  { value: "C2", hint: "Dominio: como un nativo culto" },
  { value: "nativo", hint: "Lengua materna" },
];
const CEFR_TO_LEVEL: Record<string, LanguageLevel> = {
  A1: "basico",
  A2: "basico",
  B1: "intermedio",
  B2: "intermedio",
  C1: "avanzado",
  C2: "avanzado",
};
const COMMON_LANGUAGES = ["Español", "Inglés", "Portugués", "Francés", "Alemán", "Italiano"];

export function languageLabel(l: Language): string {
  if (l.level === "nativo") return "Nativo";
  return l.cefr ?? (l.level ? LEVEL_LABEL[l.level] : "nivel pendiente");
}

export function LanguagesCard({ value, onChange }: { value: Language[]; onChange: (v: Language[]) => void }) {
  const [adding, setAdding] = useState("");

  function setLevel(i: number, v: string) {
    onChange(
      value.map((l, j) =>
        j !== i
          ? l
          : v === "nativo"
            ? { ...l, level: "nativo", cefr: null, suggested: false }
            : { ...l, level: CEFR_TO_LEVEL[v], cefr: v, suggested: false },
      ),
    );
  }

  function add(name: string) {
    if (!name || value.some((l) => l.name.toLowerCase() === name.toLowerCase())) return;
    onChange([...value, { name, level: null, cefr: null, suggested: false, evidence: null }]);
    setAdding("");
  }

  return (
    <div className="space-y-2">
      {value.length === 0 && <p className="text-sm text-slate-500">Aún no hay idiomas. Agrega los que hablas.</p>}
      {value.map((l, i) => {
        const current = l.level === "nativo" ? "nativo" : l.cefr;
        return (
          <div key={l.name} className="grid items-center gap-2 rounded-lg border border-slate-200 p-2 sm:grid-cols-[110px_1fr_auto]">
            <span className="font-medium">{l.name}</span>
            <div className="flex flex-wrap gap-1.5">
              {CEFR.map((c) => (
                <button
                  type="button"
                  key={c.value}
                  title={c.hint}
                  onClick={() => setLevel(i, c.value)}
                  className={`min-w-[44px] rounded-md border px-2 py-1 text-xs ${
                    current === c.value
                      ? l.suggested
                        ? "border-fuchsia-400 bg-fuchsia-50 text-fuchsia-800"
                        : "border-slate-900 bg-slate-900 text-white"
                      : "border-slate-300 bg-white text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  {c.value === "nativo" ? "Nativo" : c.value}
                </button>
              ))}
            </div>
            <button type="button" className="text-xs text-slate-400 hover:text-red-600" onClick={() => onChange(value.filter((_, j) => j !== i))}>
              Quitar
            </button>
            {l.suggested && l.evidence && (
              <p className="text-xs text-fuchsia-700 sm:col-span-3">✨ Sugerido: {l.evidence}. Confírmalo con un clic.</p>
            )}
            {!current && <p className="text-xs text-amber-700 sm:col-span-3">Nivel pendiente: elige uno.</p>}
          </div>
        );
      })}
      <div className="flex flex-wrap items-center gap-2">
        <select className="input max-w-[200px]" value={adding} onChange={(e) => setAdding(e.target.value)}>
          <option value="">+ Agregar idioma…</option>
          {COMMON_LANGUAGES.filter((n) => !value.some((l) => l.name === n)).map((n) => (
            <option key={n}>{n}</option>
          ))}
        </select>
        <button type="button" className="btn-secondary" disabled={!adding} onClick={() => add(adding)}>
          Agregar
        </button>
      </div>
      <p className="text-xs text-slate-500">
        Escala internacional (MCER): <b>A1–A2</b> básico · <b>B1–B2</b> intermedio · <b>C1–C2</b> avanzado. Es la que usan
        las vacantes (por ejemplo, &ldquo;Inglés B2&rdquo;). Pasa el cursor sobre cada nivel para ver qué significa.
      </p>
    </div>
  );
}

/* ---------------------------------------------------------------- proyectos con evidencia */
const EMPTY_PROJECT: Project = {
  name: "",
  description: "",
  technologies: [],
  role: "individual",
  url: "",
  evidence: "declarado",
  specificity: null,
  verified_languages: [],
  note: null,
};

export function ProjectsEditor({ value, onChange }: { value: Project[]; onChange: (v: Project[]) => void }) {
  function update(i: number, patch: Partial<Project>) {
    onChange(value.map((p, j) => (j === i ? { ...p, ...patch } : p)));
  }

  return (
    <div className="space-y-3">
      {value.map((p, i) => (
        <div key={i} className="space-y-2 rounded-lg border border-slate-200 p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${EVIDENCE_LABEL[p.evidence].color}`}>
              {EVIDENCE_LABEL[p.evidence].label}
            </span>
            <button
              type="button"
              className="text-xs text-slate-400 hover:text-red-600"
              onClick={() => onChange(value.filter((_, j) => j !== i))}
            >
              Eliminar
            </button>
          </div>
          {p.note && <p className="text-xs text-slate-500">{p.note}</p>}
          <input className="input" placeholder="Nombre del proyecto" value={p.name} onChange={(e) => update(i, { name: e.target.value })} />
          <textarea
            className="input"
            maxLength={300}
            rows={2}
            placeholder="¿Qué hiciste y qué resultado obtuviste? (máx. 300 caracteres)"
            value={p.description ?? ""}
            onChange={(e) => update(i, { description: e.target.value })}
          />
          <TagInput value={p.technologies} onChange={(t) => update(i, { technologies: t })} placeholder="Tecnologías (Enter para agregar)" />
          <div className="flex flex-wrap items-center gap-3">
            <ChipSelect
              multiple={false}
              options={["individual", "equipo"]}
              labels={{ individual: "Individual", equipo: "En equipo" }}
              value={p.role ? [p.role] : []}
              onChange={(v) => update(i, { role: v[0] ?? null })}
            />
            <input
              className="input flex-1"
              placeholder="Enlace opcional (github.com/usuario/repo)"
              value={p.url ?? ""}
              onChange={(e) => update(i, { url: e.target.value })}
            />
          </div>
        </div>
      ))}
      <button type="button" className="btn-secondary" onClick={() => onChange([...value, { ...EMPTY_PROJECT }])}>
        + Agregar proyecto
      </button>
    </div>
  );
}

/* ---------------------------------------------------------------- secciones plegables */
export function Collapsible({
  title,
  count,
  hint,
  defaultOpen = true,
  children,
}: {
  title: string;
  count: number;
  hint?: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="rounded-lg border border-slate-200">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm font-medium hover:bg-slate-50"
      >
        <span className={`inline-block transition-transform ${open ? "rotate-90" : ""}`}>▶</span>
        {title}
        <span className="rounded-full bg-slate-100 px-2 text-xs text-slate-600">{count}</span>
        {hint && <span className="ml-auto hidden text-xs font-normal text-slate-400 sm:inline">{hint}</span>}
      </button>
      {open && <div className="border-t border-slate-100 p-3">{children}</div>}
    </div>
  );
}

/* ---------------------------------------------------------------- habilidades: vista */
export function SkillsAccordion({ skills, demonstrated }: { skills: Skill[]; demonstrated: string[] }) {
  const shown = new Set(demonstrated.map((d) => d.toLowerCase()));
  return (
    <div className="space-y-2">
      {SKILL_KINDS.map((k) => {
        const items = skills.filter((s) => s.kind === k.value);
        return (
          <Collapsible key={k.value} title={k.label} count={items.length} hint={k.hint} defaultOpen={k.value !== "transversal"}>
            {items.length === 0 ? (
              <p className="text-sm text-slate-500">Ninguna todavía.</p>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {items.map((s) => {
                  const ok = shown.has(s.name.toLowerCase());
                  return (
                    <span
                      key={s.name}
                      title={ok ? "Demostrada en tu experiencia o proyectos" : s.suggested && s.evidence ? `Sugerido: ${s.evidence}` : undefined}
                      className={`rounded-full px-2.5 py-0.5 text-xs ${
                        k.value !== "transversal" && !s.level
                          ? "bg-amber-50 text-amber-800 ring-1 ring-amber-300"
                          : ok
                            ? "bg-emerald-100 text-emerald-800"
                            : "bg-slate-100 text-slate-700"
                      }`}
                    >
                      {ok && "✓ "}
                      {s.name}
                      {s.level && <b className="ml-1 font-semibold">· {SKILL_LEVEL_LABEL[s.level]}</b>}
                      {k.value !== "transversal" && !s.level && <span className="ml-1">· ⚠ sin nivel</span>}
                      {s.suggested && <span className="ml-1 text-fuchsia-700">✨</span>}
                    </span>
                  );
                })}
              </div>
            )}
          </Collapsible>
        );
      })}
      <p className="text-xs text-slate-500">
        ✓ = respaldada por tu experiencia o un proyecto · ✨ = nivel sugerido por IA · ⚠ = falta el nivel (obligatorio
        para postular)
      </p>
    </div>
  );
}

/* ---------------------------------------------------------------- habilidades: edición */
export function SkillsEditor({ value, onChange }: { value: Skill[]; onChange: (v: Skill[]) => void }) {
  const [drafts, setDrafts] = useState<Record<SkillKind, string>>({ herramienta: "", conocimiento: "", transversal: "" });
  const [options, setOptions] = useState<Record<SkillKind, string[]> | null>(null);
  const [showAll, setShowAll] = useState<Record<SkillKind, boolean>>({ herramienta: false, conocimiento: false, transversal: false });

  useEffect(() => {
    // Hasta 30 opciones por tipo, ordenadas por lo que piden las vacantes de los cargos que busca
    api<Record<SkillKind, string[]>>("/api/skills/options").then(setOptions).catch(() => setOptions(null));
  }, []);

  function pick(kind: SkillKind, name: string) {
    if (value.some((s) => s.name.toLowerCase() === name.toLowerCase())) return;
    onChange([...value, { name, kind, level: null, suggested: false, evidence: null }]);
  }

  function update(name: string, patch: Partial<Skill>) {
    onChange(
      value.map((s) => {
        if (s.name !== name) return s;
        const next = { ...s, ...patch, suggested: false };
        if (next.kind === "transversal") next.level = null; // las transversales no tienen nivel
        return next;
      }),
    );
  }

  function add(kind: SkillKind) {
    const names = drafts[kind].split(",").map((x) => x.trim()).filter(Boolean);
    const existing = new Set(value.map((s) => s.name.toLowerCase()));
    const added = names
      .filter((n) => !existing.has(n.toLowerCase()))
      .map((n) => ({ name: n, kind, level: null, suggested: false, evidence: null }) as Skill);
    onChange([...value, ...added]);
    setDrafts({ ...drafts, [kind]: "" });
  }

  return (
    <div className="space-y-2">
      {SKILL_KINDS.map((k) => {
        const items = value.filter((s) => s.kind === k.value);
        return (
          <Collapsible key={k.value} title={k.label} count={items.length} hint={k.hint} defaultOpen={k.value !== "transversal" || items.length > 0}>
            <div className="space-y-1.5">
              {items.map((s) => (
                <div key={s.name} className="flex flex-wrap items-center gap-2 rounded-md bg-white px-2 py-1 text-sm">
                  <span className="min-w-[140px] font-medium">{s.name}</span>
                  {k.value !== "transversal" && (
                    <select
                      className={`rounded border px-1.5 py-0.5 text-xs ${
                        s.level ? "border-slate-300" : "border-amber-400 bg-amber-50 text-amber-800"
                      }`}
                      value={s.level ?? ""}
                      onChange={(e) => update(s.name, { level: (e.target.value || null) as SkillLevel | null })}
                      aria-label={`Nivel de ${s.name}`}
                    >
                      <option value="">⚠ Elige nivel</option>
                      {(Object.keys(SKILL_LEVEL_LABEL) as SkillLevel[]).map((lv) => (
                        <option key={lv} value={lv}>
                          {SKILL_LEVEL_LABEL[lv]}
                        </option>
                      ))}
                    </select>
                  )}
                  {s.suggested && s.level && <span className="text-xs text-fuchsia-700">✨ sugerido</span>}
                  <button
                    type="button"
                    className="ml-auto text-xs text-slate-400 hover:text-red-600"
                    onClick={() => onChange(value.filter((x) => x.name !== s.name))}
                    aria-label={`Quitar ${s.name}`}
                  >
                    Quitar
                  </button>
                </div>
              ))}
              {options && (() => {
                const chosen = new Set(value.map((x) => x.name.toLowerCase()));
                const available = options[k.value].filter((o) => !chosen.has(o.toLowerCase()));
                const visible = showAll[k.value] ? available : available.slice(0, 12);
                return available.length > 0 ? (
                  <div className="rounded-md border border-dashed border-slate-300 p-2">
                    <p className="mb-1.5 text-xs text-slate-500">Elige con un clic (las más pedidas en lo que buscas aparecen primero):</p>
                    <div className="flex flex-wrap gap-1.5">
                      {visible.map((o) => (
                        <button
                          type="button"
                          key={o}
                          onClick={() => pick(k.value, o)}
                          className="rounded-full border border-slate-300 bg-white px-2.5 py-0.5 text-xs text-slate-700 hover:border-sky-400 hover:bg-sky-50"
                        >
                          + {o}
                        </button>
                      ))}
                      {available.length > 12 && (
                        <button
                          type="button"
                          className="px-1 text-xs text-sky-700 underline"
                          onClick={() => setShowAll({ ...showAll, [k.value]: !showAll[k.value] })}
                        >
                          {showAll[k.value] ? "Ver menos" : `Ver ${available.length - 12} más`}
                        </button>
                      )}
                    </div>
                  </div>
                ) : null;
              })()}
              <div className="flex gap-2">
                <input
                  className="input"
                  placeholder="¿No está en la lista? Escríbela y presiona Enter"
                  value={drafts[k.value]}
                  onChange={(e) => setDrafts({ ...drafts, [k.value]: e.target.value })}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      add(k.value);
                    }
                  }}
                />
                <button type="button" className="btn-secondary" disabled={!drafts[k.value].trim()} onClick={() => add(k.value)}>
                  Agregar
                </button>
              </div>
            </div>
          </Collapsible>
        );
      })}
      <p className="text-xs text-slate-500">
        El nivel aplica a herramientas y conocimientos y es <b>obligatorio para postular</b> (si no lo pones ahora,
        te lo pediremos al postular). Las transversales no llevan nivel.
      </p>
    </div>
  );
}
