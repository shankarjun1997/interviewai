// Thin typed client for the InterviewAI API. All AI/feature pages build on this.
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Token = { access_token: string; role: string; organization_id: string };
export type Interview = {
  id: string;
  title: string;
  job_description: string;
  difficulty: string;
  status: string;
};
export type Question = {
  id: string;
  type: string;
  text: string;
  difficulty: string;
  competencies: string[];
  order_index: number;
};

function authHeaders(): Record<string, string> {
  const t = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  return t ? { Authorization: `Bearer ${t}` } : {};
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...authHeaders(), ...(init?.headers ?? {}) },
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? res.statusText);
  return res.json() as Promise<T>;
}

export const api = {
  register: (body: { organization_name: string; email: string; password: string; full_name?: string }) =>
    req<Token>("/api/v1/auth/register", { method: "POST", body: JSON.stringify(body) }),
  login: (body: { email: string; password: string }) =>
    req<Token>("/api/v1/auth/login", { method: "POST", body: JSON.stringify(body) }),
  listInterviews: () => req<Interview[]>("/api/v1/interviews"),
  createInterview: (body: { title: string; job_description?: string; difficulty?: string }) =>
    req<Interview>("/api/v1/interviews", { method: "POST", body: JSON.stringify(body) }),
  generateQuestions: (id: string, counts: Record<string, number>) =>
    req<Question[]>(`/api/v1/interviews/${id}/generate-questions`, {
      method: "POST",
      body: JSON.stringify({ counts }),
    }),
};
