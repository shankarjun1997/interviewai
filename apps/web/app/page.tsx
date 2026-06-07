"use client";

import { useState } from "react";
import { api, type Question } from "../lib/api";

// Minimal but real walking-skeleton UI: sign up, create an interview from a JD,
// and generate AI questions. The richer copilot/scorecard UIs layer on later.
export default function Home() {
  const [authed, setAuthed] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [org, setOrg] = useState("");
  const [title, setTitle] = useState("Senior Data Engineer");
  const [jd, setJd] = useState("Spark, dbt, Airflow, GCP, Kafka");
  const [questions, setQuestions] = useState<Question[]>([]);
  const [err, setErr] = useState("");

  async function signup() {
    setErr("");
    try {
      const t = await api.register({ organization_name: org, email, password });
      localStorage.setItem("token", t.access_token);
      setAuthed(true);
    } catch (e) {
      setErr(String(e));
    }
  }

  async function generate() {
    setErr("");
    try {
      const iv = await api.createInterview({ title, job_description: jd, difficulty: "hard" });
      const qs = await api.generateQuestions(iv.id, { intro: 2, behavioral: 3, technical: 5 });
      setQuestions(qs);
    } catch (e) {
      setErr(String(e));
    }
  }

  return (
    <main className="mx-auto max-w-2xl p-8 space-y-6">
      <h1 className="text-3xl font-semibold tracking-tight">InterviewAI</h1>
      <p className="text-neutral-400">JD → AI-generated interview questions. Walking skeleton.</p>

      {!authed ? (
        <div className="space-y-3 rounded-xl border border-neutral-800 p-6">
          <input className="input" placeholder="Organization" value={org} onChange={(e) => setOrg(e.target.value)} />
          <input className="input" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
          <input className="input" type="password" placeholder="Password (8+ chars)" value={password} onChange={(e) => setPassword(e.target.value)} />
          <button className="btn" onClick={signup}>Create account</button>
        </div>
      ) : (
        <div className="space-y-3 rounded-xl border border-neutral-800 p-6">
          <input className="input" placeholder="Interview title" value={title} onChange={(e) => setTitle(e.target.value)} />
          <textarea className="input h-28" placeholder="Job description" value={jd} onChange={(e) => setJd(e.target.value)} />
          <button className="btn" onClick={generate}>Generate questions</button>
        </div>
      )}

      {err && <p className="text-red-400 text-sm">{err}</p>}

      <ul className="space-y-2">
        {questions.map((q) => (
          <li key={q.id} className="rounded-lg border border-neutral-800 p-4">
            <span className="text-xs uppercase tracking-wide text-emerald-400">{q.type}</span>
            <p className="mt-1">{q.text}</p>
          </li>
        ))}
      </ul>

      <style>{`
        .input { width:100%; background:#0a0a0a; border:1px solid #262626; border-radius:0.5rem; padding:0.6rem 0.8rem; color:#fafafa; }
        .btn { background:#10b981; color:#04130c; font-weight:600; border-radius:0.5rem; padding:0.6rem 1rem; }
      `}</style>
    </main>
  );
}
