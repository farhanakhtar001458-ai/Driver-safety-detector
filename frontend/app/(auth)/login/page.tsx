"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowRight, Eye, EyeOff, Loader2, ShieldCheck } from "lucide-react";
import { Button, Field, Input } from "@/components/ui";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";

function LoginForm() {
  const { login, isAuthenticated } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") || "/overview";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isAuthenticated) router.replace(next);
  }, [isAuthenticated, next, router]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      router.replace(next);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Sign in failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid min-h-screen bg-ink-50 dark:bg-ink-950 lg:grid-cols-[1.05fr_1fr]">
      <div className="relative hidden overflow-hidden bg-ink-950 p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(13,171,153,0.28),transparent_45%),radial-gradient(circle_at_80%_80%,rgba(79,70,229,0.22),transparent_40%)]" />
        <div className="relative flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-brand-400 to-brand-600">
            <ShieldCheck className="h-5 w-5" />
          </span>
          <div>
            <p className="text-sm font-semibold">SafeWay AI</p>
            <p className="text-[10px] uppercase tracking-[0.2em] text-brand-300/80">Safety intelligence</p>
          </div>
        </div>

        <div className="relative max-w-md">
          <h1 className="text-4xl font-semibold leading-tight tracking-tight">
            See risk before it becomes a <span className="text-brand-300">report</span>.
          </h1>
          <p className="mt-4 text-sm leading-relaxed text-ink-300">
            Live tracking, explainable driver scoring, incident workflow and predictive maintenance — in one
            workspace for fleets, schools and logistics operators.
          </p>

          <div className="mt-8 grid gap-3">
            {[
              ["Explainable scoring", "Every point is traceable to an event rate, not a black box."],
              ["Risk triage, not prophecy", "AI prioritises review; humans make the safety decision."],
              ["Tenant-isolated", "Organisation data is scoped at every query."],
            ].map(([title, body]) => (
              <div key={title} className="flex gap-3 rounded-2xl bg-white/5 p-3.5 ring-1 ring-white/10">
                <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-400" />
                <div>
                  <p className="text-xs font-semibold text-white">{title}</p>
                  <p className="mt-0.5 text-[11px] leading-relaxed text-ink-400">{body}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <p className="relative text-[10px] leading-relaxed text-ink-500">
          Safety scores support human review; they do not predict accidents and should not be used as the sole basis for disciplinary action.
        </p>
      </div>

      <div className="flex items-center justify-center p-6 sm:p-10">
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
          className="w-full max-w-md"
        >
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-brand-400 to-brand-600 text-white">
              <ShieldCheck className="h-5 w-5" />
            </span>
            <div>
              <p className="text-sm font-semibold text-ink-900 dark:text-white">SafeWay AI</p>
              <p className="text-[10px] uppercase tracking-[0.2em] text-brand-600">Safety intelligence</p>
            </div>
          </div>

          <h2 className="text-2xl font-semibold tracking-tight text-ink-950 dark:text-white">Welcome back</h2>
          <p className="mt-1.5 text-sm text-ink-500 dark:text-ink-400">Sign in to your safety workspace.</p>

          <form onSubmit={submit} className="mt-6 space-y-4">
            <Field label="Work email" required>
              <Input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@company.com"
                autoComplete="email"
                required
              />
            </Field>
            <Field label="Password" required>
              <div className="relative">
                <Input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="••••••••"
                  autoComplete="current-password"
                  className="pr-11"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((value) => !value)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-400 hover:text-ink-700"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </Field>

            {error && (
              <div className="rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-xs text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-200">
                {error}
              </div>
            )}

            <Button type="submit" loading={loading} className="w-full">
              Sign in <ArrowRight className="h-4 w-4" />
            </Button>
          </form>

          <p className="mt-6 text-center text-xs text-ink-500 dark:text-ink-400">
            New organisation?{" "}
            <Link href="/register" className="font-semibold text-brand-600 hover:underline dark:text-brand-300">
              Create an account
            </Link>
          </p>
        </motion.div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-ink-50 dark:bg-ink-950">
          <span className="h-10 w-10 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
