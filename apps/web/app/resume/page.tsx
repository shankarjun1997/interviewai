"use client";

import { useState } from "react";
import { api, type ResumeAnalysis } from "../../lib/api";
import { useAuthGuard } from "../../lib/auth";
import { Shell, PageHeading } from "../../components/Shell";
import { Button } from "../../components/ui/Button";
import { Card, CardBody, CardHeader, CardTitle } from "../../components/ui/Card";
import { Textarea } from "../../components/ui/Input";
import { Badge } from "../../components/ui/Badge";
import { Alert } from "../../components/ui/Alert";
import { Spinner } from "../../components/ui/Spinner";

function Tags({ items, tone }: { items: string[]; tone: "emerald" | "red" | "amber" | "neutral" }) {
  if (!items || items.length === 0) return <p className="text-sm text-neutral-500">None.</p>;
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((it, i) => (
        <Badge key={`${it}-${i}`} tone={tone}>
          {it}
        </Badge>
      ))}
    </div>
  );
}

export default function ResumePage() {
  const { ready } = useAuthGuard();
  const [resume, setResume] = useState("");
  const [jd, setJd] = useState("");
  const [result, setResult] = useState<ResumeAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  async function analyze(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      setResult(await api.analyzeResume({ resume_text: resume, job_description: jd || undefined }));
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "Failed to analyze resume");
    } finally {
      setLoading(false);
    }
  }

  if (!ready) {
    return (
      <div className="grid min-h-screen place-items-center">
        <Spinner />
      </div>
    );
  }

  return (
    <Shell>
      <PageHeading
        title="Resume analyzer"
        subtitle="Extract structured signals and an interview plan from a resume + job description."
      />

      <div className="grid gap-8 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Input</CardTitle>
          </CardHeader>
          <CardBody>
            <form onSubmit={analyze} className="space-y-4">
              <Textarea
                id="resume"
                label="Resume text"
                placeholder="Paste the candidate's resume…"
                value={resume}
                onChange={(e) => setResume(e.target.value)}
                className="min-h-[12rem]"
                required
              />
              <Textarea
                id="jd"
                label="Job description (optional)"
                placeholder="Paste the target role's JD…"
                value={jd}
                onChange={(e) => setJd(e.target.value)}
              />
              {err && <Alert tone="error">{err}</Alert>}
              <Button type="submit" loading={loading} disabled={!resume.trim()} className="w-full">
                Analyze resume
              </Button>
            </form>
          </CardBody>
        </Card>

        <Card>
          <CardHeader className="flex items-center justify-between">
            <CardTitle>Analysis</CardTitle>
            {result && <Badge tone="neutral">source: {result.source}</Badge>}
          </CardHeader>
          <CardBody className="space-y-6">
            {!result ? (
              <p className="text-sm text-neutral-500">Run an analysis to see results here.</p>
            ) : (
              <>
                <div>
                  <p className="mb-2 text-xs uppercase tracking-wide text-emerald-400">Skills</p>
                  <Tags items={result.skills} tone="emerald" />
                </div>
                <div>
                  <p className="mb-2 text-xs uppercase tracking-wide text-red-400">Missing skills</p>
                  <Tags items={result.missing_skills} tone="red" />
                </div>
                <div>
                  <p className="mb-2 text-xs uppercase tracking-wide text-amber-400">Risk areas</p>
                  <Tags items={result.risk_areas} tone="amber" />
                </div>
                {result.certifications.length > 0 && (
                  <div>
                    <p className="mb-2 text-xs uppercase tracking-wide text-neutral-400">
                      Certifications
                    </p>
                    <Tags items={result.certifications} tone="neutral" />
                  </div>
                )}

                <div>
                  <p className="mb-2 text-xs uppercase tracking-wide text-neutral-400">
                    Interview plan
                  </p>
                  {result.interview_plan.length === 0 ? (
                    <p className="text-sm text-neutral-500">No plan generated.</p>
                  ) : (
                    <ol className="space-y-2">
                      {result.interview_plan.map((p, i) => (
                        <li
                          key={i}
                          className="rounded-lg border border-neutral-800/70 bg-neutral-950/40 p-3"
                        >
                          <div className="flex items-center gap-2">
                            <Badge tone="blue">{p.round || `Round ${i + 1}`}</Badge>
                            <span className="text-sm font-medium text-neutral-200">{p.focus}</span>
                          </div>
                          {p.rationale && (
                            <p className="mt-1.5 text-sm text-neutral-400">{p.rationale}</p>
                          )}
                        </li>
                      ))}
                    </ol>
                  )}
                </div>

                <div>
                  <p className="mb-2 text-xs uppercase tracking-wide text-neutral-400">
                    Suggested questions
                  </p>
                  {result.suggested_questions.length === 0 ? (
                    <p className="text-sm text-neutral-500">No questions suggested.</p>
                  ) : (
                    <ul className="space-y-2">
                      {result.suggested_questions.map((q, i) => (
                        <li
                          key={i}
                          className="rounded-lg border border-neutral-800/70 bg-neutral-950/40 p-3"
                        >
                          <div className="mb-1.5 flex items-center gap-2">
                            <Badge tone="emerald">{q.type}</Badge>
                            {q.competencies?.map((c) => (
                              <Badge key={c} tone="neutral">
                                {c}
                              </Badge>
                            ))}
                          </div>
                          <p className="text-sm text-neutral-200">{q.text}</p>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </>
            )}
          </CardBody>
        </Card>
      </div>
    </Shell>
  );
}
