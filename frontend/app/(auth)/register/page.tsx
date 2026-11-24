"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { Button, Field, Input } from "@/components/ui";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();
  const [form, setForm] = useState({
    organisation_name: "",
    full_name: "",
    email: "",
    phone: "",
    password: "",
    accept_monitoring_policy: false,
  });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const update = (key: keyof typeof form, value: string | boolean) =>
    setForm((current) => ({ ...current, [key]: value }));

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    if (!form.accept_monitoring_policy) {
      setError("Please acknowledge the driver monitoring and consent policy.");
      return;
    }
    setLoading(true);
    try {
      await register(form);
      router.replace("/overview");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Registration failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-ink-50 p-6 dark:bg-ink-950 sm:p-10">
      <motion.div
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
        className="w-full max-w-lg"
      >
        <div className="mb-8 flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-brand-400 to-brand-600 text-white">
            <ShieldCheck className="h-5 w-5" />
          </span>
          <div>
            <p className="text-sm font-semibold text-ink-900 dark:text-white">SafeWay AI</p>
            <p className="text-[10px] uppercase tracking-[0.2em] text-brand-600">Start your safety workspace</p>
          </div>
        </div>

        <div className="card p-6 sm:p-8">
          <h1 className="text-2xl font-semibold tracking-tight text-ink-950 dark:text-white">Create your organisation</h1>
          <p className="mt-1.5 text-sm text-ink-500 dark:text-ink-400">
            You will start on a 14-day Professional trial with full analytics. No card required.
          </p>

          <form onSubmit={submit} className="mt-6 space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Organisation name" required>
                <Input
                  value={form.organisation_name}
                  onChange={(event) => update("organisation_name", event.target.value)}
                  placeholder="Meridian Logistics"
                  required
                  minLength={2}
                />
              </Field>
              <Field label="Your full name" required>
                <Input
                  value={form.full_name}
                  onChange={(event) => update("full_name", event.target.value)}
                  placeholder="Aditi Sharma"
                  required
                  minLength={2}
                />
              </Field>
            </div>
            <Field label="Work email" required>
              <Input
                type="email"
                value={form.email}
                onChange={(event) => update("email", event.target.value)}
                placeholder="you@company.com"
                required
              />
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Phone (optional)">
                <Input value={form.phone} onChange={(event) => update("phone", event.target.value)} placeholder="+91 98765 43210" />
              </Field>
              <Field label="Password" required hint="At least 8 characters.">
                <Input
                  type="password"
                  value={form.password}
                  onChange={(event) => update("password", event.target.value)}
                  placeholder="Create a strong password"
                  required
                  minLength={8}
                />
              </Field>
            </div>

            <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-ink-200 bg-ink-50/60 p-3.5 dark:border-white/10 dark:bg-white/5">
              <input
                type="checkbox"
                checked={form.accept_monitoring_policy}
                onChange={(event) => update("accept_monitoring_policy", event.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-ink-300 text-brand-600 focus:ring-brand-500"
              />
              <span className="text-xs leading-relaxed text-ink-600 dark:text-ink-300">
                I confirm that drivers will be informed about vehicle monitoring, that data is collected for safety
                purposes only, and that retention and access controls will be maintained.{" "}
                <span className="font-semibold">This is a demo environment with simulated telemetry.</span>
              </span>
            </label>

            {error && (
              <div className="rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-xs text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-200">
                {error}
              </div>
            )}

            <Button type="submit" loading={loading} className="w-full">
              Create workspace <ArrowRight className="h-4 w-4" />
            </Button>
          </form>
        </div>

        <p className="mt-5 text-center text-xs text-ink-500 dark:text-ink-400">
          Already have an account?{" "}
          <Link href="/login" className="font-semibold text-brand-600 hover:underline dark:text-brand-300">
            Sign in
          </Link>
        </p>
      </motion.div>
    </div>
  );
}
