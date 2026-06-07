"use client";

import { useState } from "react";
import { api, type RankingResult, type RankedEntry } from "../../lib/api";
import { useAuthGuard } from "../../lib/auth";
import { Shell, PageHeading } from "../../components/Shell";
import { Button } from "../../components/ui/Button";
import { Card, CardBody, CardHeader, CardTitle } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { Badge } from "../../components/ui/Badge";
import { Alert } from "../../components/ui/Alert";
import { Spinner } from "../../components/ui/Spinner";
import { cn } from "../../lib/cn";

type Mode = "position" | "interviews";

function RankTable({ entries }: { entries: RankedEntry[] }) {
  if (!entries || entries.length === 0) {
    return <p className="px-6 py-4 text-sm text-neutral-500">No entries.</p>;
  }
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-neutral-800/70 text-left text-xs uppercase tracking-wide text-neutral-500">
          <th className="px-4 py-2.5 font-medium">#</th>
          <th className="px-4 py-2.5 font-medium">Candidate</th>
          <th className="px-4 py-2.5 text-right font-medium">Score</th>
        </tr>
      </thead>
      <tbody>
        {entries.map((e) => (
          <tr key={e.scorecard_id} className="border-b border-neutral-800/40 last:border-0">
            <td className="px-4 py-2.5">
              <span
                className={cn(
                  "grid h-6 w-6 place-items-center rounded-full text-xs font-semibold",
                  e.rank === 1
                    ? "bg-emerald-500 text-emerald-950"
                    : "bg-neutral-800 text-neutral-300",
                )}
              >
                {e.rank}
              </span>
            </td>
            <td className="px-4 py-2.5 text-neutral-200">{e.candidate_name}</td>
            <td className="px-4 py-2.5 text-right tabular-nums text-neutral-300">
              {e.score.toFixed(2)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function RankingPage() {
  const { ready } = useAuthGuard();
  const [mode, setMode] = useState<Mode>("position");
  const [positionId, setPositionId] = useState("");
  const [interviewIds, setInterviewIds] = useState("");
  const [result, setResult] = useState<RankingResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  async function compare(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      const body =
        mode === "position"
          ? { position_id: positionId.trim() }
          : {
              interview_ids: interviewIds
                .split(/[\s,]+/)
                .map((s) => s.trim())
                .filter(Boolean),
            };
      setResult(await api.compareRanking(body));
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "Failed to compare candidates");
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
        title="Candidate ranking"
        subtitle="Compare scorecards across a position or an explicit set of interviews."
      />

      <div className="grid gap-8 lg:grid-cols-[360px_1fr]">
        <Card className="lg:sticky lg:top-20 self-start">
          <CardHeader>
            <CardTitle>Compare</CardTitle>
          </CardHeader>
          <CardBody>
            <form onSubmit={compare} className="space-y-4">
              <div className="grid grid-cols-2 gap-1 rounded-lg bg-neutral-950/60 p-1">
                {(["position", "interviews"] as const).map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => setMode(m)}
                    className={cn(
                      "rounded-md py-1.5 text-sm font-medium capitalize transition-colors",
                      mode === m
                        ? "bg-neutral-800 text-neutral-100"
                        : "text-neutral-400 hover:text-neutral-200",
                    )}
                  >
                    {m === "position" ? "By position" : "By interviews"}
                  </button>
                ))}
              </div>

              {mode === "position" ? (
                <Input
                  id="positionId"
                  label="Position ID"
                  placeholder="position uuid"
                  value={positionId}
                  onChange={(e) => setPositionId(e.target.value)}
                  required
                />
              ) : (
                <Input
                  id="interviewIds"
                  label="Interview IDs"
                  hint="Comma or space separated"
                  placeholder="id1, id2, id3"
                  value={interviewIds}
                  onChange={(e) => setInterviewIds(e.target.value)}
                  required
                />
              )}

              {err && <Alert tone="error">{err}</Alert>}

              <Button type="submit" loading={loading} className="w-full">
                Compare
              </Button>
            </form>
          </CardBody>
        </Card>

        <div className="space-y-6">
          {!result ? (
            <Card>
              <CardBody className="py-12 text-center text-sm text-neutral-500">
                Run a comparison to see ranked candidates.
              </CardBody>
            </Card>
          ) : (
            <>
              {result.recommendation && (
                <Alert tone="info">{result.recommendation}</Alert>
              )}

              <Card>
                <CardHeader className="flex items-center justify-between">
                  <CardTitle>Overall ranking</CardTitle>
                  <Badge tone="neutral">{result.count} candidates</Badge>
                </CardHeader>
                <RankTable entries={result.overall} />
              </Card>

              {result.dimension_names
                .filter((dim) => (result.dimensions[dim]?.length ?? 0) > 0)
                .map((dim) => (
                  <Card key={dim}>
                    <CardHeader>
                      <CardTitle className="capitalize">{dim.replace(/_/g, " ")}</CardTitle>
                    </CardHeader>
                    <RankTable entries={result.dimensions[dim] ?? []} />
                  </Card>
                ))}
            </>
          )}
        </div>
      </div>
    </Shell>
  );
}
