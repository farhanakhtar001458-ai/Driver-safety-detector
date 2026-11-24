"use client";

import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui";

export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-ink-50 p-6 dark:bg-ink-950">
      <div className="card w-full max-w-md p-8 text-center">
        <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-rose-50 text-rose-600 dark:bg-rose-500/10 dark:text-rose-300">
          <AlertTriangle className="h-5 w-5" />
        </span>
        <h1 className="mt-4 text-lg font-semibold tracking-tight text-ink-950 dark:text-white">Something went wrong</h1>
        <p className="mt-2 text-xs leading-relaxed text-ink-500 dark:text-ink-400">
          The interface hit an unexpected error. Your data is not affected. Try again, and if the problem persists check
          the API connection.
        </p>
        {error.digest && <p className="mt-2 font-mono text-[10px] text-ink-400">Reference: {error.digest}</p>}
        <Button className="mt-5" onClick={reset}>
          <RefreshCw className="h-4 w-4" /> Try again
        </Button>
      </div>
    </div>
  );
}
