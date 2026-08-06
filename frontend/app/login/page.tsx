"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const res = await fetch(`${API_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });
    if (!res.ok) {
      setError((await res.json())?.error?.message ?? "Login failed");
      return;
    }
    const body = await res.json();
    localStorage.setItem("conductor_access_token", body.access_token);
    localStorage.setItem("conductor_refresh_token", body.refresh_token);
    router.push("/chat");
  }

  return (
    <main className="mx-auto mt-24 max-w-sm rounded-xl border border-slate-800 bg-slate-900 p-8">
      <h1 className="text-xl font-semibold">Sign in to Conductor</h1>
      <form onSubmit={onSubmit} className="mt-6 flex flex-col gap-4">
        <input
          className="rounded-md border border-slate-700 bg-slate-800 px-3 py-2"
          type="email"
          placeholder="you@company.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <input
          className="rounded-md border border-slate-700 bg-slate-800 px-3 py-2"
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        {error && <p className="text-sm text-red-400">{error}</p>}
        <button
          type="submit"
          className="rounded-md bg-indigo-600 py-2 font-medium text-white hover:bg-indigo-500"
        >
          Sign in
        </button>
      </form>
    </main>
  );
}