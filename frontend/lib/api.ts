export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Stage = "onboarding" | "cv_gaps" | "preferences" | "approval" | "skill_levels" | "identity" | "tracking";

export type LanguageLevel = "basico" | "intermedio" | "avanzado" | "nativo";

export type SkillKind = "herramienta" | "conocimiento" | "transversal";
export type SkillLevel = "basico" | "intermedio" | "avanzado";

export interface Skill {
  name: string;
  kind: SkillKind;
  level: SkillLevel | null;
  suggested: boolean;
  evidence: string | null;
}

export const SKILL_KINDS: { value: SkillKind; label: string; hint: string }[] = [
  { value: "herramienta", label: "Herramientas y tecnologías", hint: "Software y equipos: Excel, SAP, Python, Canva…" },
  { value: "conocimiento", label: "Conocimientos técnicos", hint: "Lo que sabes: Contabilidad, Inventarios, Estadística…" },
  { value: "transversal", label: "Habilidades transversales", hint: "Cómo trabajas: comunicación, trabajo en equipo… (sin nivel)" },
];

export const SKILL_LEVEL_LABEL: Record<SkillLevel, string> = {
  basico: "Básico",
  intermedio: "Intermedio",
  avanzado: "Avanzado",
};

export interface Language {
  name: string;
  level: LanguageLevel | null;
  cefr: string | null;
  suggested: boolean;
  evidence: string | null;
}

export interface Experience {
  title: string;
  company: string | null;
  city: string | null;
  start: string | null;
  end: string | null;
  current: boolean;
  description: string | null;
}

export interface Education {
  degree: string;
  institution: string | null;
  level: string | null;
  year: string | null;
  status: string | null;
  semester: number | null;
}

export interface Certification {
  name: string;
  issuer: string | null;
  year: string | null;
}

export interface Project {
  name: string;
  description: string | null;
  technologies: string[];
  role: string | null;
  url: string | null;
  evidence: "declarado" | "descrito" | "con_enlace" | "verificado";
  specificity: number | null;
  verified_languages: string[];
  note: string | null;
}

export interface Expectations {
  desired_roles: string[];
  sectors: string[];
  city: string | null;
  modality: string | null;
  workday: string[];
  contract_types: string[];
  salary_min_cop: number | null;
  salary_frequency: string;
  availability: string | null;
  willing_to_travel: boolean | null;
  willing_to_relocate: boolean | null;
}

export interface Profile {
  full_name: string | null;
  first_names: string | null;
  last_names: string | null;
  document_type: string | null;
  email: string | null;
  phone: string | null;
  city: string | null;
  department: string | null;
  linkedin: string | null;
  github: string | null;
  portfolio: string | null;
  headline: string | null;
  summary: string | null;
  profession: string | null;
  years_experience: number | null;
  seniority: string | null;
  skills: Skill[];
  demonstrated_skills: string[];
  languages: Language[];
  experiences: Experience[];
  projects: Project[];
  education: Education[];
  certifications: Certification[];
  expectations: Expectations;
  first_job: boolean;
  suggestions: { roles?: string[]; sectors?: string[]; projects_for?: string[] };
  provenance: Record<string, string>;
  edited_fields: string[];
}

export interface Gap {
  field: string;
  label: string;
  question: string;
  input_type: "text" | "number" | "select" | "multiselect" | "tags" | "skills" | "boolean" | "languages" | "projects" | "info";
  options: string[];
  critical: boolean;
  group: string;
  items: (Language | Skill)[];
}

export interface CvScore {
  score: number;
  mode: "experiencia" | "primer_empleo";
  reason: string;
  breakdown: { key: string; label: string; weight: number; got: number }[];
}

export interface ProfileView {
  profile: Profile;
  cv: CvScore;
  cv_gaps: Gap[];
  preferences: { score: number; missing: string[]; labels: Record<string, string> };
}

export interface Catalogs {
  sectors: string[];
  workdays: string[];
  contract_types: string[];
  availability: string[];
  salary_frequencies: string[];
  modalities: string[];
  document_types: string[];
  sex_options: string[];
  disability_types: string[];
  language_levels: { value: LanguageLevel; label: string }[];
  languages: string[];
}

export interface Vacancy {
  id: string;
  title: string;
  company: string;
  city: string | null;
  modality: string;
  salary_min_cop: number | null;
  salary_max_cop: number | null;
  seniority: string;
  must_have: string[];
  nice_to_have: string[];
  languages: Record<string, string>;
  skill_levels: Record<string, string>;
  sector: string | null;
  workday: string;
  contract: string;
  min_education: string | null;
  requires_travel: boolean;
  description: string;
  posted_at: string | null;
}

export interface SkillCheck {
  name: string;
  status: "ok" | "falta" | "nivel_menor" | "nivel_por_confirmar";
  required_level: string | null;
  have_level: string | null;
  demonstrated: boolean;
}

export interface MatchGap {
  kind: string;
  item: string;
  required: string | null;
  have: string | null;
  message: string;
}

export interface Match {
  vacancy: Vacancy;
  score: number;
  breakdown: Record<string, number>;
  reasons: string[];
  missing_skills: string[];
  pending_languages: string[];
  skills_detail: SkillCheck[];
  gaps: MatchGap[];
  not_applicable: string[];
}

export interface PreferencesPending {
  type: "preferences";
  values: Expectations;
  suggestions: Profile["suggestions"];
  required: string[];
  missing: string[];
  labels: Record<string, string>;
  completeness: number;
  catalogs: Catalogs;
}

export interface IdentityPending {
  type: "identity";
  approve_ids?: string[];
  values: Record<string, string | null>;
  missing: string[];
  fields: { field: string; label: string; input_type: string; options: string[] }[];
  sensitive: { sex_options: string[]; disability_types: string[]; values: Record<string, unknown> };
}

export interface SkillLevelsPending {
  type: "skill_levels";
  skills: Skill[];
  levels: { value: SkillLevel; label: string }[];
  approve_ids?: string[];
}

export type Pending =
  | { type: "cv_gaps"; gaps: Gap[]; cv: CvScore }
  | PreferencesPending
  | { type: "approval"; matches: Match[] }
  | SkillLevelsPending
  | IdentityPending;

export interface FlowResponse {
  stage: Stage;
  pending: Pending | null;
}

export interface AppState {
  stage: Stage;
  sim_day: number;
  pending: Pending | null;
  llm_providers: string[];
}

export interface Application {
  id: number;
  vacancy_id: string;
  vacancy_title: string;
  company: string;
  score: number;
  status: "postulado" | "en_revision" | "entrevista" | "descartado";
  created_day: number;
  updated_day: number;
  interview_day: number | null;
  evidence: { form: Record<string, unknown>; receipt: Record<string, string>; match_reasons: string[] };
  history: { status: string; day: number; by: string }[];
  next_steps: string[];
}

export interface Reminder {
  id: number;
  application_id: number | null;
  kind: string;
  title: string;
  message: string;
  due_day: number;
  mode: string;
  done: boolean;
}

export interface TraceEvent {
  id: number;
  run_id: string;
  agent: string;
  action: string;
  reason: string;
  details: Record<string, unknown>;
  mode: "llm" | "rules" | "human" | "system";
  provider: string | null;
  duration_ms: number;
  sim_day: number;
  created_at: string;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

function token(): string | null {
  try {
    return localStorage.getItem("pm_token");
  } catch {
    return null;
  }
}

export function setSession(t: string | null, username?: string) {
  try {
    if (t) {
      localStorage.setItem("pm_token", t);
      if (username) localStorage.setItem("pm_user", username);
    } else {
      localStorage.removeItem("pm_token");
      localStorage.removeItem("pm_user");
    }
  } catch {
    /* almacenamiento no disponible */
  }
}

export function currentUsername(): string | null {
  try {
    return localStorage.getItem("pm_user");
  } catch {
    return null;
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const t = token();
  if (t) headers.set("Authorization", `Bearer ${t}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "No se pudo conectar con el backend. ¿Está corriendo en " + API_URL + "?");
  }
  if (res.status === 401 && !path.startsWith("/api/auth")) {
    setSession(null);
    if (typeof window !== "undefined") window.location.href = "/login";
  }
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const body = await res.json();
      msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* sin cuerpo */
    }
    throw new ApiError(res.status, msg);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const cop = (v: number | null | undefined) =>
  v == null ? "a convenir" : "$" + v.toLocaleString("es-CO", { maximumFractionDigits: 0 });

export const LEVEL_LABEL: Record<LanguageLevel, string> = {
  basico: "Básico",
  intermedio: "Intermedio",
  avanzado: "Avanzado",
  nativo: "Nativo",
};

export const PROVENANCE: Record<string, { label: string; color: string }> = {
  reglas: { label: "📄 del CV", color: "bg-slate-100 text-slate-600" },
  ia: { label: "✨ sugerido por IA", color: "bg-fuchsia-50 text-fuchsia-700" },
  usuario: { label: "✏️ editado por ti", color: "bg-emerald-50 text-emerald-700" },
};

export const EVIDENCE_LABEL: Record<Project["evidence"], { label: string; color: string }> = {
  declarado: { label: "Declarado", color: "bg-slate-100 text-slate-600" },
  descrito: { label: "Descrito", color: "bg-sky-50 text-sky-700" },
  con_enlace: { label: "Con enlace", color: "bg-indigo-50 text-indigo-700" },
  verificado: { label: "✅ Repositorio verificado", color: "bg-emerald-50 text-emerald-700" },
};

export const STATUS_LABEL: Record<Application["status"], string> = {
  postulado: "Postulado",
  en_revision: "En revisión",
  entrevista: "Entrevista",
  descartado: "Descartado",
};

export const AGENT_META: Record<string, { label: string; color: string }> = {
  perfil: { label: "Agente de Perfil", color: "bg-violet-100 text-violet-800 border-violet-200" },
  vacantes: { label: "Agente de Vacantes", color: "bg-sky-100 text-sky-800 border-sky-200" },
  postulacion: { label: "Agente de Postulación", color: "bg-emerald-100 text-emerald-800 border-emerald-200" },
  seguimiento: { label: "Agente de Seguimiento", color: "bg-amber-100 text-amber-800 border-amber-200" },
  candidato: { label: "Candidato", color: "bg-pink-100 text-pink-800 border-pink-200" },
  portal: { label: "Portal (simulado)", color: "bg-slate-100 text-slate-700 border-slate-200" },
  orquestador: { label: "Orquestador", color: "bg-indigo-100 text-indigo-800 border-indigo-200" },
};
