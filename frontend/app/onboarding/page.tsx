"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { api, AppState, FlowResponse, ProfileView } from "@/lib/api";
import { ErrorBox, Spinner } from "@/components/ui";
import CvGapsForm from "@/components/CvGapsForm";
import PreferencesForm from "@/components/PreferencesForm";
import ProfileEditor, { SaveResult } from "@/components/ProfileEditor";

const STEPS = [
  { key: "onboarding", label: "Sube tu CV" },
  { key: "cv_gaps", label: "Revisa tu hoja de vida" },
  { key: "preferences", label: "¿Qué buscas?" },
  { key: "approval", label: "Recomendaciones" },
];

export default function OnboardingPage() {
  const router = useRouter();
  const [state, setState] = useState<AppState | null>(null);
  const [view, setView] = useState<ProfileView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [reupload, setReupload] = useState(false);

  const refresh = useCallback(async () => {
    setState(await api<AppState>("/api/state"));
    try {
      setView(await api<ProfileView>("/api/profile"));
    } catch {
      setView(null);
    }
  }, []);

  useEffect(() => {
    refresh().catch((e) => setError(e.message));
  }, [refresh]);

  function handleFlow(r: FlowResponse) {
    setReupload(false);
    if (r.stage === "approval") router.push("/matches");
    else refresh();
  }

  function onSaved(r: SaveResult) {
    setView(r.view);
    if (r.recalculated && r.stage === "approval") setNotice("Recomendaciones recalculadas con tu perfil corregido.");
    else if (r.changed.length && r.stage === "tracking")
      setNotice(`Guardado: ${r.changed.join(", ")}. Ve a Recomendaciones y pulsa "Actualizar recomendaciones" para verlas con estos cambios.`);
    else if (r.changed.length) setNotice(`Guardado: ${r.changed.join(", ")}`);
    api<AppState>("/api/state").then(setState);
  }

  if (!state) return error ? <ErrorBox msg={error} /> : <Spinner text="Cargando…" />;
  const stepIdx = Math.max(0, STEPS.findIndex((s) => s.key === state.stage));
  const pending = state.pending;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">1. Tu perfil</h1>
        <p className="text-slate-600">
          El <b>Agente de Perfil</b> lee tu hoja de vida (reglas + IA), te pregunta solo lo necesario y separa lo que es
          de tu CV de lo que buscas.
        </p>
        <ol className="mt-3 flex flex-wrap gap-2 text-xs">
          {STEPS.map((s, i) => (
            <li
              key={s.key}
              className={`rounded-full px-3 py-1 ${
                i < stepIdx || ["approval", "identity", "tracking"].includes(state.stage)
                  ? "bg-emerald-100 text-emerald-800"
                  : i === stepIdx
                    ? "bg-slate-900 text-white"
                    : "bg-slate-100 text-slate-500"
              }`}
            >
              {i + 1}. {s.label}
            </li>
          ))}
        </ol>
      </div>
      <ErrorBox msg={error} />
      {busy && <Spinner text={busy} />}
      {notice && (
        <div className="rounded-lg bg-emerald-50 px-4 py-2 text-sm text-emerald-800">
          {notice}{" "}
          {state.stage === "approval" && (
            <Link className="underline" href="/matches">
              Ver recomendaciones
            </Link>
          )}
        </div>
      )}

      {view && !reupload && (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm">
          <span className="text-slate-600">¿Subiste el CV equivocado o tienes uno más reciente?</span>
          <button className="btn-secondary" onClick={() => setReupload(true)}>
            📄 Subir otro CV
          </button>
        </div>
      )}

      {reupload || state.stage === "onboarding" || state.stage === "tracking" || state.stage === "approval" || state.stage === "identity" ? (
        <UploadForm
          onDone={handleFlow}
          setError={setError}
          setBusy={setBusy}
          hasProfile={!!view}
          onCancel={view ? () => setReupload(false) : undefined}
          visible={reupload || !view}
        />
      ) : state.stage === "cv_gaps" && pending?.type === "cv_gaps" ? (
        <CvGapsForm
          gaps={pending.gaps}
          cv={pending.cv}
          onSubmit={async (answers) => {
            setError(null);
            handleFlow(await api<FlowResponse>("/api/onboarding/cv", { method: "POST", body: JSON.stringify({ answers }) }));
          }}
        />
      ) : state.stage === "preferences" && pending?.type === "preferences" ? (
        <div className="card">
          <PreferencesForm
            initial={pending.values}
            suggestions={pending.suggestions}
            onSubmit={async (prefs) => {
              setBusy("El Agente de Vacantes está buscando opciones…");
              try {
                handleFlow(await api<FlowResponse>("/api/onboarding/preferences", { method: "POST", body: JSON.stringify(prefs) }));
              } finally {
                setBusy(null);
              }
            }}
          />
        </div>
      ) : null}

      {view && <ProfileEditor key={JSON.stringify(view.profile.provenance) + view.cv.score} view={view} onSaved={onSaved} />}
    </div>
  );
}

function UploadForm({
  onDone,
  setError,
  setBusy,
  hasProfile,
  onCancel,
  visible,
}: {
  onDone: (r: FlowResponse) => void;
  setError: (s: string | null) => void;
  setBusy: (s: string | null) => void;
  hasProfile: boolean;
  onCancel?: () => void;
  visible: boolean;
}) {
  const [file, setFile] = useState<File | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!file) return setError("Selecciona tu hoja de vida (PDF o TXT)");
    if (hasProfile && !confirm("Subir un CV nuevo reinicia tus recomendaciones, postulaciones y \"Lo que buscas\" (te lo volveremos a preguntar). Si el CV es tuyo, conservamos lo que editaste a mano y te sugerimos tus respuestas anteriores. ¿Continuar?"))
      return;
    setError(null);
    setBusy("Los agentes están analizando tu hoja de vida…");
    const fd = new FormData();
    fd.append("cv", file);
    try {
      onDone(await api<FlowResponse>("/api/onboarding", { method: "POST", body: fd }));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  if (!visible) return null;
  return (
    <form onSubmit={submit} className="card space-y-3">
      <label className="label">Hoja de vida (PDF o TXT, máx. 5 MB)</label>
      <input type="file" accept=".pdf,.txt" className="input" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      <p className="text-xs text-slate-500">
        Tu CV debe tener: datos de contacto, perfil, experiencia (o proyectos si es tu primer empleo), educación,
        habilidades e idiomas. No pongas cédula ni expectativas salariales: eso te lo preguntamos aparte. Plantilla de
        ejemplo en <code>samples/plantilla_hoja_de_vida.pdf</code>.
      </p>
      <div className="flex gap-2">
        <button className="btn">{hasProfile ? "Subir este CV" : "Analizar mi hoja de vida"}</button>
        {onCancel && (
          <button type="button" className="btn-secondary" onClick={onCancel}>
            Cancelar
          </button>
        )}
      </div>
    </form>
  );
}
