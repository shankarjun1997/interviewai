// Thin typed client for the InterviewAI API. All AI/feature pages build on this.
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---- auth ----
export type Token = {
  access_token: string;
  token_type?: string;
  role: string;
  organization_id: string;
};

// ---- interviews ----
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

// ---- scoring ----
export type Scorecard = {
  id: string;
  interview_id: string;
  candidate_id: string | null;
  overall_score: number;
  competency_scores: Record<string, number>;
  recommendation: string;
};

// ---- reports ----
export type Report = {
  id: string;
  interview_id: string;
  executive_summary: string;
  strengths: string[];
  weaknesses: string[];
  risk_indicators: string[];
  recommended_position: string;
  interview_highlights: string[];
  notable_quotes: string[];
  role_match_percent: number;
};

// ---- resume ----
export type ExperienceItem = {
  title: string;
  company: string;
  summary: string;
  years: number | null;
};
export type ProjectItem = { name: string; description: string };
export type PlanItem = { round: string; focus: string; rationale: string };
export type SuggestedQuestion = {
  type: string;
  text: string;
  competencies: string[];
};
export type ResumeAnalysis = {
  candidate_id: string | null;
  persisted: boolean;
  skills: string[];
  experience: ExperienceItem[];
  projects: ProjectItem[];
  certifications: string[];
  missing_skills: string[];
  risk_areas: string[];
  interview_plan: PlanItem[];
  suggested_questions: SuggestedQuestion[];
  source: string;
};

// ---- ranking ----
export type RankedEntry = {
  rank: number;
  interview_id: string;
  scorecard_id: string;
  candidate_id: string | null;
  candidate_name: string;
  score: number;
};
export type RankingResult = {
  count: number;
  overall: RankedEntry[];
  dimensions: Record<string, RankedEntry[]>;
  recommendation: string;
  dimension_names: string[];
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
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail) && body.detail.length > 0) {
        // FastAPI validation errors come back as a list of objects.
        const first = body.detail[0] as { msg?: string };
        if (first?.msg) detail = first.msg;
      }
    } catch {
      /* non-JSON body — keep statusText */
    }
    throw new Error(detail);
  }
  // 204 / empty bodies safeguard.
  const text = await res.text();
  return (text ? JSON.parse(text) : null) as T;
}

export const api = {
  // auth
  register: (body: {
    organization_name: string;
    email: string;
    password: string;
    full_name?: string;
  }) => req<Token>("/api/v1/auth/register", { method: "POST", body: JSON.stringify(body) }),
  login: (body: { email: string; password: string }) =>
    req<Token>("/api/v1/auth/login", { method: "POST", body: JSON.stringify(body) }),

  // interviews
  listInterviews: () => req<Interview[]>("/api/v1/interviews"),
  createInterview: (body: {
    title: string;
    job_description?: string;
    difficulty?: string;
    position_id?: string | null;
  }) => req<Interview>("/api/v1/interviews", { method: "POST", body: JSON.stringify(body) }),
  generateQuestions: (id: string, counts: Record<string, number>) =>
    req<Question[]>(`/api/v1/interviews/${id}/generate-questions`, {
      method: "POST",
      body: JSON.stringify({ counts }),
    }),

  // scoring
  computeScorecard: (interviewId: string) =>
    req<Scorecard>(`/api/v1/scoring/interviews/${interviewId}/compute`, { method: "POST" }),
  getScorecard: (interviewId: string) =>
    req<Scorecard>(`/api/v1/scoring/interviews/${interviewId}/scorecard`),

  // reports
  generateReport: (interviewId: string) =>
    req<Report>(`/api/v1/reports/interviews/${interviewId}/generate`, { method: "POST" }),
  getReport: (interviewId: string) =>
    req<Report>(`/api/v1/reports/interviews/${interviewId}`),

  // resume
  analyzeResume: (body: {
    resume_text: string;
    job_description?: string;
    candidate_id?: string | null;
  }) => req<ResumeAnalysis>("/api/v1/resume/analyze", { method: "POST", body: JSON.stringify(body) }),

  // ranking
  compareRanking: (body: { position_id?: string | null; interview_ids?: string[] | null }) =>
    req<RankingResult>("/api/v1/ranking/compare", { method: "POST", body: JSON.stringify(body) }),
};
