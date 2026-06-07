"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "../../lib/api";
import { setToken } from "../../lib/auth";
import { Button } from "../../components/ui/Button";
import { Card, CardBody } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { Alert } from "../../components/ui/Alert";
import { cn } from "../../lib/cn";

type Tab = "login" | "register";

export default function LoginPage() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("login");
  const [org, setOrg] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      const token =
        tab === "login"
          ? await api.login({ email, password })
          : await api.register({
              organization_name: org,
              email,
              password,
              full_name: fullName || undefined,
            });
      setToken(token.access_token);
      router.replace("/dashboard");
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid min-h-screen place-items-center px-6">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          <span className="grid h-11 w-11 place-items-center rounded-xl bg-emerald-500 text-lg font-bold text-emerald-950">
            IA
          </span>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">InterviewAI</h1>
            <p className="mt-1 text-sm text-neutral-400">AI-powered interview assessment</p>
          </div>
        </div>

        <Card>
          <CardBody className="space-y-5">
            <div className="grid grid-cols-2 gap-1 rounded-lg bg-neutral-950/60 p-1">
              {(["login", "register"] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => {
                    setTab(t);
                    setErr("");
                  }}
                  className={cn(
                    "rounded-md py-1.5 text-sm font-medium transition-colors",
                    tab === t
                      ? "bg-neutral-800 text-neutral-100"
                      : "text-neutral-400 hover:text-neutral-200",
                  )}
                >
                  {t === "login" ? "Sign in" : "Create account"}
                </button>
              ))}
            </div>

            <form onSubmit={submit} className="space-y-4">
              {tab === "register" && (
                <>
                  <Input
                    id="org"
                    label="Organization"
                    placeholder="Acme Inc"
                    value={org}
                    onChange={(e) => setOrg(e.target.value)}
                    required
                  />
                  <Input
                    id="fullName"
                    label="Full name"
                    placeholder="Jane Doe"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                  />
                </>
              )}
              <Input
                id="email"
                type="email"
                label="Email"
                placeholder="you@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
              <Input
                id="password"
                type="password"
                label="Password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                hint={tab === "register" ? "At least 8 characters" : undefined}
                required
                autoComplete={tab === "login" ? "current-password" : "new-password"}
              />

              {err && <Alert tone="error">{err}</Alert>}

              <Button type="submit" loading={loading} className="w-full">
                {tab === "login" ? "Sign in" : "Create account"}
              </Button>
            </form>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
