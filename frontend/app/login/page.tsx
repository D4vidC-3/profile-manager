"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { api, setSession } from "@/lib/api";
import { ErrorBox } from "@/components/ui";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("demo");
  const [password, setPassword] = useState("demo1234");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(e: FormEvent, mode: "login" | "register") {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const r = await api<{ access_token: string; username: string }>(`/api/auth/${mode}`, {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      setSession(r.access_token, r.username);
      router.push("/");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto mt-10 max-w-md">
      <h1 className="text-center text-3xl font-bold text-brand-dark">
        Profile<span className="text-brand">Manager</span>
      </h1>
      <p className="mt-2 text-center text-slate-600">
        “Dame tu hoja de vida y tus expectativas; nosotros gestionamos tu búsqueda.”
      </p>
      <form className="card mt-8 space-y-4" onSubmit={(e) => submit(e, "login")}>
        <div>
          <label className="label">Usuario</label>
          <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} />
        </div>
        <div>
          <label className="label">Contraseña</label>
          <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        <ErrorBox msg={error} />
        <div className="flex gap-2">
          <button className="btn flex-1" disabled={loading}>
            Ingresar
          </button>
          <button type="button" className="btn-secondary" disabled={loading} onClick={(e) => submit(e, "register")}>
            Crear cuenta
          </button>
        </div>
        <p className="text-xs text-slate-500">Usuario de demostración: demo / demo1234</p>
      </form>
    </div>
  );
}
