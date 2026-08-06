import Link from "next/link";

export default function HomePage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-20">
      <h1 className="text-4xl font-bold text-white">Conductor</h1>
      <p className="mt-4 text-slate-300">
        Four specialized agents — Planner, Researcher, Tool Executor, Critic —
        orchestrated by LangGraph to answer deep research questions over your
        documents and live tools.
      </p>
      <div className="mt-8 flex gap-4">
        <Link
          href="/login"
          className="rounded-lg bg-indigo-600 px-4 py-2 font-medium text-white hover:bg-indigo-500"
        >
          Sign in
        </Link>
        <Link
          href="/chat"
          className="rounded-lg border border-slate-700 px-4 py-2 font-medium text-slate-200 hover:bg-slate-800"
        >
          Open chat
        </Link>
      </div>
    </main>
  );
}