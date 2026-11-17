import { AGENT_META } from "@/lib/api";

export function ErrorBox({ msg }: { msg: string | null }) {
  if (!msg) return null;
  return <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{msg}</div>;
}

export function ModeBadge({ mode, provider }: { mode: string; provider?: string | null }) {
  const styles: Record<string, string> = {
    llm: "bg-fuchsia-600 text-white",
    rules: "bg-slate-700 text-white",
    human: "bg-pink-500 text-white",
    system: "bg-slate-300 text-slate-800",
  };
  const label: Record<string, string> = { llm: "IA", rules: "Reglas", human: "Humano", system: "Sistema" };
  return (
    <span className={`rounded px-1.5 py-0.5 text-[11px] font-semibold ${styles[mode] ?? styles.system}`}>
      {label[mode] ?? mode}
      {provider && mode === "llm" ? ` · ${provider}` : ""}
    </span>
  );
}

export function AgentBadge({ agent }: { agent: string }) {
  const meta = AGENT_META[agent] ?? { label: agent, color: "bg-slate-100 text-slate-700 border-slate-200" };
  return <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${meta.color}`}>{meta.label}</span>;
}

export function ScoreBar({ value, max = 100 }: { value: number; max?: number }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  const color = pct >= 75 ? "bg-emerald-500" : pct >= 55 ? "bg-sky-500" : "bg-amber-500";
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
      <div className={`h-full ${color}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function Spinner({ text }: { text: string }) {
  return (
    <div className="flex items-center gap-3 text-sm text-slate-600">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-800" />
      {text}
    </div>
  );
}
