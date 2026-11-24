"use client";

import Link from "next/link";
import { Compass, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui";

export default function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-ink-50 p-6 dark:bg-ink-950">
      <div className="text-center">
        <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-400 to-brand-600 text-white shadow-lg shadow-brand-500/25">
          <ShieldCheck className="h-6 w-6" />
        </span>
        <p className="mt-6 text-[11px] font-semibold uppercase tracking-[0.2em] text-brand-600 dark:text-brand-300">404</p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-ink-950 dark:text-white">This page does not exist</h1>
        <p className="mx-auto mt-2 max-w-sm text-sm leading-relaxed text-ink-500 dark:text-ink-400">
          The link may be outdated, or the page may belong to a module that is not part of this deployment.
        </p>
        <div className="mt-6 flex justify-center gap-2">
          <Button href="/overview">
            <Compass className="h-4 w-4" /> Back to overview
          </Button>
          <Button variant="secondary" href="/login">Sign in</Button>
        </div>
        <p className="mt-8 text-[10px] text-ink-400">
          <Link href="/overview" className="hover:underline">SafeWay AI</Link> · driving safety intelligence
        </p>
      </div>
    </div>
  );
}
