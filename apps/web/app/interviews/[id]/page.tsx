"use client";

import { use, useState } from "react";
import Link from "next/link";
import {
  api,
  type Question,
  type Scorecard,
  type Report,
} from "../../../lib/api";
import { useAuthGuard } from "../../../lib/auth";
import { Shell, PageHeading } from "../../../components/Shell";
import { Button } from "../../../components/ui/Button";
import { Card, CardBody, CardHeader, CardTitle } from "../../../components/ui/Card";
import { Badge } from "../../../components/ui/Badge";
import { Alert } from "../../../components/ui/Alert";
import { Spinner } from "../../../components/ui/Spinner";

const QUESTION_TYPES = ["intro", "behavioral", "technical"] as const;
type QType = (typeof QUESTION_TYPES)[number];

function typeTone(type: string): "emerald" | "blue" | "amber" | "neutral" {
  if (type === "technical") return "emerald";
  if (type === "behavioral") return "blue";
  if (type === "intro") return "amber";
  return "neutral";
}

function recTone(rec: string): "emerald" | "amber" | "red" | "neutral" {
  const r = rec.toLowerCase();
  if (r.includes("strong") || r.includes("hire") || r.includes("yes")) return "emerald";
  if (r.includes("no") || r.includes("reject")) return "red";
  if (r.includes("consider") || r.includes("maybe") || r.includes("lean")) return "amber";
  return "neutral";
}

function List({ items, tone }: { items: string[]; tone?: "emerald" | "amber" | "red" }) {
  if (!items || items.length === 0) {
    return <p className="text-sm text-neutral-500">None reported.</p>;
  }
  const dot =
    tone === "emerald"
      ? "bg-emerald-400"
      : tone === "amber"
        ? "bg-amber-400"
        : tone === "red"
          ? "bg-red-400"
          : "bg-neutral-500";
  return (
    <ul className="space-y-2">
      {items.map((it, i) => (
        <li key={i} className="flex gap-2.5 text-sm text-neutral-300">
          <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${dot}`} />
          <span>{it}</span>
        </li>
      ))}
    </ul>
  );
}

export default function InterviewDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { ready } = useAuthGuard();

  // questions
  const [counts, setCounts] = useState<Record<QType, number>>({
    intro: 2,
    behavioral: 3,
    technical: 5,
  });
  const [questions, setQuestions] = useState<Question[]>([]);
  const [qLoading, setQLoading] = useState(false);
  const [qErr, setQErr] = useState("");

  // scorecard
  const [scorecard, setScorecard] = useState<Scorecard | null>(null);
  const [scLoading, setScLoading] = useState(false);
  const [scErr, setScErr] = useState("");

  // report
  const [report, setReport] = useState<Report | null>(null);
  const [rLoading, setRLoading] = useState(false);
  const [rErr, setRErr] = useState("");

  async function generate() {
    setQErr("");
    setQLoading(true);
    try {
      setQuestions(await api.generateQuestions(id, counts));
    } catch (e) {
      setQErr(e instanceof Error ? e.message : "Failed to generate questions");
    } finally {
      setQLoading(false);
    }
  }

  async function loadScorecard(compute: boolean) {
    setScErr("");
    setScLoading(true);
    try {
      setScorecard(compute ? await api.computeScorecard(id) : await api.getScorecard(id));
    } catch (e) {
      setScErr(e instanceof Error ? e.message : "Failed to load scorecard");
    } finally {
      setScLoading(false);
    }
  }

  async function loadReport(gen: boolean) {
    setRErr("");
    setRLoading(true);
    try {
      setReport(gen ? await api.generateReport(id) : await api.getReport(id));
    } catch (e) {
      setRErr(e instanceof Error ? e.message : "Failed to load report");
    } finally {
      setRLoading(false);
    }
  }

  if (!ready) {
    return (
      <div className="grid min-h-screen place-items-center">
        <Spinner />
      </div>
    );
  }

  const grouped = QUESTION_TYPES.map((t) => ({
    type: t,
    items: questions.filter((q) => q.type === t),
  })).filter((g) => g.items.length > 0);
  // Surface any types the backend returned that aren't in our known set.
  const known = new Set<string>(QUESTION_TYPES);
  const otherItems = questions.filter((q) => !known.has(q.type));

  return (
    <Shell>
      <div className="mb-4">
        <Link href="/dashboard" className="text-sm text-neutral-400 hover:text-neutral-200">
          ← Back to interviews
        </Link>
      </div>
      <PageHeading title="Interview" subtitle={`ID: ${id}`} />

      <div className="space-y-8">
        {/* Questions */}
        <Card>
          <CardHeader className="flex items-center justify-between">
            <CardTitle>Question generation</CardTitle>
            <Button onClick={generate} loading={qLoading} size="sm">
              Generate questions
            </Button>
          </CardHeader>
          <CardBody className="space-y-5">
            <div className="grid grid-cols-3 gap-4">
              {QUESTION_TYPES.map((t) => (
                <label key={t} className="block space-y-1.5">
                  <span className="text-xs font-medium capitalize text-neutral-400">{t}</span>
                  <input
                    type="number"
                    min={0}
                    max={20}
                    value={counts[t]}
                    onChange={(e) =>
                      setCounts((c) => ({ ...c, [t]: Math.max(0, Number(e.target.value) || 0) }))
                    }
                    className="w-full rounded-lg border border-neutral-800 bg-neutral-950/60 px-3.5 py-2.5 text-sm text-neutral-100 focus:border-emerald-500/70 focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
                  />
                </label>
              ))}
            </div>

            {qErr && <Alert tone="error">{qErr}</Alert>}

            {questions.length === 0 ? (
              <p className="text-sm text-neutral-500">
                Choose counts and generate questions tailored to this interview.
              </p>
            ) : (
              <div className="space-y-6">
                {[...grouped, ...(otherItems.length ? [{ type: "other" as const, items: otherItems }] : [])].map(
                  (group) => (
                    <div key={group.type}>
                      <div className="mb-2 flex items-center gap-2">
                        <Badge tone={typeTone(group.type)}>{group.type}</Badge>
                        <span className="text-xs text-neutral-500">{group.items.length}</span>
                      </div>
                      <ul className="space-y-2">
                        {group.items.map((q) => (
                          <li
                            key={q.id}
                            className="rounded-lg border border-neutral-800/70 bg-neutral-950/40 p-4"
                          >
                            <p className="text-sm text-neutral-200">{q.text}</p>
                            {q.competencies && q.competencies.length > 0 && (
                              <div className="mt-2 flex flex-wrap gap-1.5">
                                {q.competencies.map((c) => (
                                  <Badge key={c} tone="neutral">
                                    {c}
                                  </Badge>
                                ))}
                              </div>
                            )}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ),
                )}
              </div>
            )}
          </CardBody>
        </Card>

        {/* Scorecard */}
        <Card>
          <CardHeader className="flex items-center justify-between">
            <CardTitle>Scorecard</CardTitle>
            <div className="flex gap-2">
              <Button onClick={() => loadScorecard(false)} loading={scLoading} size="sm" variant="secondary">
                View
              </Button>
              <Button onClick={() => loadScorecard(true)} loading={scLoading} size="sm">
                Compute
              </Button>
            </div>
          </CardHeader>
          <CardBody className="space-y-4">
            {scErr && <Alert tone="error">{scErr}</Alert>}
            {!scorecard && !scErr && (
              <p className="text-sm text-neutral-500">
                Compute a role-weighted scorecard from this interview&apos;s evaluations.
              </p>
            )}
            {scorecard && (
              <div className="space-y-5">
                <div className="flex items-center gap-6">
                  <div>
                    <p className="text-xs uppercase tracking-wide text-neutral-500">Overall</p>
                    <p className="text-3xl font-semibold text-emerald-400">
                      {scorecard.overall_score.toFixed(1)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wide text-neutral-500">Recommendation</p>
                    <div className="mt-1">
                      <Badge tone={recTone(scorecard.recommendation)}>
                        {scorecard.recommendation || "n/a"}
                      </Badge>
                    </div>
                  </div>
                </div>

                <div>
                  <p className="mb-2 text-xs uppercase tracking-wide text-neutral-500">
                    Competency scores
                  </p>
                  {Object.keys(scorecard.competency_scores ?? {}).length === 0 ? (
                    <p className="text-sm text-neutral-500">No competency breakdown available.</p>
                  ) : (
                    <div className="space-y-2.5">
                      {Object.entries(scorecard.competency_scores).map(([k, v]) => {
                        const pct = Math.max(0, Math.min(100, (Number(v) / 5) * 100));
                        return (
                          <div key={k}>
                            <div className="mb-1 flex justify-between text-sm">
                              <span className="capitalize text-neutral-300">{k.replace(/_/g, " ")}</span>
                              <span className="tabular-nums text-neutral-400">{Number(v).toFixed(1)}</span>
                            </div>
                            <div className="h-1.5 overflow-hidden rounded-full bg-neutral-800">
                              <div
                                className="h-full rounded-full bg-emerald-500"
                                style={{ width: `${pct}%` }}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            )}
          </CardBody>
        </Card>

        {/* Report */}
        <Card>
          <CardHeader className="flex items-center justify-between">
            <CardTitle>Intelligence report</CardTitle>
            <div className="flex gap-2">
              <Button onClick={() => loadReport(false)} loading={rLoading} size="sm" variant="secondary">
                View
              </Button>
              <Button onClick={() => loadReport(true)} loading={rLoading} size="sm">
                Generate
              </Button>
            </div>
          </CardHeader>
          <CardBody className="space-y-6">
            {rErr && <Alert tone="error">{rErr}</Alert>}
            {!report && !rErr && (
              <p className="text-sm text-neutral-500">
                Generate a candidate intelligence report synthesizing transcript, evaluations, and
                scorecard.
              </p>
            )}
            {report && (
              <div className="space-y-6">
                <div className="flex flex-wrap items-center gap-4">
                  <div>
                    <p className="text-xs uppercase tracking-wide text-neutral-500">Role match</p>
                    <p className="text-2xl font-semibold text-emerald-400">
                      {report.role_match_percent}%
                    </p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wide text-neutral-500">Recommendation</p>
                    <div className="mt-1">
                      <Badge tone={recTone(report.recommended_position)}>
                        {report.recommended_position || "consider"}
                      </Badge>
                    </div>
                  </div>
                </div>

                {report.executive_summary && (
                  <div>
                    <p className="mb-1.5 text-xs uppercase tracking-wide text-neutral-500">
                      Executive summary
                    </p>
                    <p className="text-sm leading-relaxed text-neutral-300">
                      {report.executive_summary}
                    </p>
                  </div>
                )}

                <div className="grid gap-6 md:grid-cols-2">
                  <div>
                    <p className="mb-2 text-xs uppercase tracking-wide text-emerald-400">Strengths</p>
                    <List items={report.strengths} tone="emerald" />
                  </div>
                  <div>
                    <p className="mb-2 text-xs uppercase tracking-wide text-amber-400">Weaknesses</p>
                    <List items={report.weaknesses} tone="amber" />
                  </div>
                  <div>
                    <p className="mb-2 text-xs uppercase tracking-wide text-red-400">Risk indicators</p>
                    <List items={report.risk_indicators} tone="red" />
                  </div>
                  <div>
                    <p className="mb-2 text-xs uppercase tracking-wide text-neutral-400">Highlights</p>
                    <List items={report.interview_highlights} />
                  </div>
                </div>

                {report.notable_quotes && report.notable_quotes.length > 0 && (
                  <div>
                    <p className="mb-2 text-xs uppercase tracking-wide text-neutral-500">
                      Notable quotes
                    </p>
                    <div className="space-y-3">
                      {report.notable_quotes.map((q, i) => (
                        <blockquote
                          key={i}
                          className="border-l-2 border-emerald-500/50 pl-4 text-sm italic text-neutral-300"
                        >
                          “{q}”
                        </blockquote>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </CardBody>
        </Card>
      </div>
    </Shell>
  );
}
