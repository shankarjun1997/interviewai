"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, type Interview } from "../../lib/api";
import { useAuthGuard } from "../../lib/auth";
import { Shell, PageHeading } from "../../components/Shell";
import { Button } from "../../components/ui/Button";
import { Card, CardBody, CardHeader, CardTitle } from "../../components/ui/Card";
import { Input, Textarea } from "../../components/ui/Input";
import { Badge } from "../../components/ui/Badge";
import { Alert } from "../../components/ui/Alert";
import { Spinner } from "../../components/ui/Spinner";

const DIFFICULTIES = ["easy", "medium", "hard"] as const;

function statusTone(status: string): "emerald" | "amber" | "neutral" {
  if (status === "completed") return "emerald";
  if (status === "in_progress" || status === "active") return "amber";
  return "neutral";
}

export default function DashboardPage() {
  const { ready } = useAuthGuard();
  const [interviews, setInterviews] = useState<Interview[]>([]);
  const [loading, setLoading] = useState(true);
  const [listErr, setListErr] = useState("");

  const [title, setTitle] = useState("");
  const [jd, setJd] = useState("");
  const [difficulty, setDifficulty] = useState<string>("medium");
  const [creating, setCreating] = useState(false);
  const [createErr, setCreateErr] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setListErr("");
    try {
      setInterviews(await api.listInterviews());
    } catch (e) {
      setListErr(e instanceof Error ? e.message : "Failed to load interviews");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (ready) void load();
  }, [ready, load]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setCreateErr("");
    setCreating(true);
    try {
      const iv = await api.createInterview({
        title,
        job_description: jd || undefined,
        difficulty,
      });
      setInterviews((prev) => [iv, ...prev]);
      setTitle("");
      setJd("");
      setDifficulty("medium");
    } catch (e) {
      setCreateErr(e instanceof Error ? e.message : "Failed to create interview");
    } finally {
      setCreating(false);
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
      <PageHeading title="Interviews" subtitle="Create interviews and generate AI questions from a job description." />

      <div className="grid gap-8 lg:grid-cols-[1fr_360px]">
        <section className="space-y-4">
          {listErr && <Alert tone="error">{listErr}</Alert>}

          {loading ? (
            <div className="flex items-center gap-3 py-12 text-sm text-neutral-400">
              <Spinner /> Loading interviews…
            </div>
          ) : interviews.length === 0 ? (
            <Card>
              <CardBody className="py-12 text-center text-sm text-neutral-400">
                No interviews yet. Create your first one to get started.
              </CardBody>
            </Card>
          ) : (
            <ul className="space-y-3">
              {interviews.map((iv) => (
                <li key={iv.id}>
                  <Link href={`/interviews/${iv.id}`} className="block">
                    <Card className="transition-colors hover:border-neutral-700 hover:bg-neutral-900/70">
                      <CardBody className="flex items-center justify-between gap-4">
                        <div className="min-w-0">
                          <p className="truncate font-medium text-neutral-100">{iv.title}</p>
                          <p className="mt-1 truncate text-sm text-neutral-500">
                            {iv.job_description || "No job description"}
                          </p>
                        </div>
                        <div className="flex shrink-0 items-center gap-2">
                          <Badge tone="blue">{iv.difficulty}</Badge>
                          <Badge tone={statusTone(iv.status)}>{iv.status}</Badge>
                        </div>
                      </CardBody>
                    </Card>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        <aside>
          <Card className="lg:sticky lg:top-20">
            <CardHeader>
              <CardTitle>New interview</CardTitle>
            </CardHeader>
            <CardBody>
              <form onSubmit={create} className="space-y-4">
                <Input
                  id="title"
                  label="Title"
                  placeholder="Senior Data Engineer"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  required
                />
                <Textarea
                  id="jd"
                  label="Job description"
                  placeholder="Spark, dbt, Airflow, GCP, Kafka…"
                  value={jd}
                  onChange={(e) => setJd(e.target.value)}
                />
                <label className="block space-y-1.5">
                  <span className="text-xs font-medium text-neutral-400">Difficulty</span>
                  <select
                    value={difficulty}
                    onChange={(e) => setDifficulty(e.target.value)}
                    className="w-full rounded-lg border border-neutral-800 bg-neutral-950/60 px-3.5 py-2.5 text-sm text-neutral-100 focus:border-emerald-500/70 focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
                  >
                    {DIFFICULTIES.map((d) => (
                      <option key={d} value={d}>
                        {d}
                      </option>
                    ))}
                  </select>
                </label>

                {createErr && <Alert tone="error">{createErr}</Alert>}

                <Button type="submit" loading={creating} className="w-full">
                  Create interview
                </Button>
              </form>
            </CardBody>
          </Card>
        </aside>
      </div>
    </Shell>
  );
}
