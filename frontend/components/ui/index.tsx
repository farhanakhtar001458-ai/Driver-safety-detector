"use client";

import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, X } from "lucide-react";
import { useEffect, useState } from "react";
import { cn } from "@/lib/format";

/* ------------------------------------------------------------------ Badge */
export function Badge({
  children,
  tone = "slate",
  className,
}: {
  children: React.ReactNode;
  tone?: string;
  className?: string;
}) {
  return <span className={cn("badge ring-1 ring-inset", tone, className)}>{children}</span>;
}

export function SeverityBadge({ severity }: { severity?: string | null }) {
  return <Badge tone={severityToneLocal(severity)}>{(severity ?? "unknown").replace("_", " ")}</Badge>;
}

export function SimulatedBadge({ label = "Simulated" }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-md border border-dashed border-amber-400/60 bg-amber-50 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-700 dark:bg-amber-500/10 dark:text-amber-300">
      <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
      {label}
    </span>
  );
}

/** Exported for unit tests so tone mapping stays covered without DOM. */
export function severityToneLocalForTest(severity?: string | null) {
  return severityToneLocal(severity);
}

function severityToneLocal(severity?: string | null) {
  switch (severity) {
    case "critical":
      return "bg-rose-50 text-rose-700 ring-rose-600/20 dark:bg-rose-500/10 dark:text-rose-300";
    case "high":
      return "bg-amber-50 text-amber-700 ring-amber-600/20 dark:bg-amber-500/10 dark:text-amber-300";
    case "medium":
    case "moderate":
      return "bg-indigo-50 text-indigo-700 ring-indigo-600/20 dark:bg-indigo-500/10 dark:text-indigo-300";
    case "low":
    case "minor":
      return "bg-emerald-50 text-emerald-700 ring-emerald-600/20 dark:bg-emerald-500/10 dark:text-emerald-300";
    default:
      return "bg-ink-100 text-ink-600 ring-ink-400/20 dark:bg-white/5 dark:text-ink-300";
  }
}

/* ----------------------------------------------------------------- Button */
type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md";
  loading?: boolean;
  href?: string;
};

export function Button({
  variant = "primary",
  size = "md",
  loading,
  className,
  children,
  href,
  ...props
}: ButtonProps) {
  const classes = cn(
    "inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition focus:outline-none focus:ring-4 disabled:cursor-not-allowed disabled:opacity-50",
    size === "sm" ? "px-3 py-1.5 text-xs" : "px-4 py-2.5 text-sm",
    variant === "primary" && "bg-brand-600 text-white shadow-sm hover:bg-brand-700 focus:ring-brand-500/20",
    variant === "secondary" &&
      "border border-ink-200 bg-white text-ink-800 hover:bg-ink-50 dark:border-white/10 dark:bg-white/5 dark:text-ink-100 dark:hover:bg-white/10",
    variant === "ghost" && "text-ink-600 hover:bg-ink-100 dark:text-ink-300 dark:hover:bg-white/5",
    variant === "danger" && "bg-rose-600 text-white hover:bg-rose-700 focus:ring-rose-500/20",
    className,
  );

  if (href) {
    return (
      <Link href={href} className={classes}>
        {children}
      </Link>
    );
  }

  return (
    <button className={classes} disabled={loading || props.disabled} {...props}>
      {loading && <Spinner className="h-3.5 w-3.5" />}
      {children}
    </button>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <svg className={cn("animate-spin", className)} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
    </svg>
  );
}

/* ------------------------------------------------------------------- Card */
export function Card({
  children,
  className,
  title,
  subtitle,
  action,
  padded = true,
}: {
  children: React.ReactNode;
  className?: string;
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  action?: React.ReactNode;
  padded?: boolean;
}) {
  return (
    <section className={cn("card", className)}>
      {(title || action) && (
        <header className="flex items-start justify-between gap-4 border-b border-ink-100 px-5 py-4 dark:border-white/5">
          <div>
            {title && <h3 className="text-sm font-semibold text-ink-900 dark:text-white">{title}</h3>}
            {subtitle && <p className="mt-0.5 text-xs text-ink-500 dark:text-ink-400">{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      <div className={cn(padded && "p-5")}>{children}</div>
    </section>
  );
}

/* -------------------------------------------------------------- StatCard */
export function StatCard({
  label,
  value,
  icon,
  hint,
  tone = "teal",
  index = 0,
}: {
  label: string;
  value: React.ReactNode;
  icon?: React.ReactNode;
  hint?: React.ReactNode;
  tone?: "teal" | "indigo" | "amber" | "rose" | "slate";
  index?: number;
}) {
  const tones: Record<string, string> = {
    teal: "bg-brand-500/10 text-brand-600 dark:text-brand-300",
    indigo: "bg-indigo-500/10 text-indigo-600 dark:text-indigo-300",
    amber: "bg-amber-500/10 text-amber-600 dark:text-amber-300",
    rose: "bg-rose-500/10 text-rose-600 dark:text-rose-300",
    slate: "bg-ink-100 text-ink-600 dark:bg-white/10 dark:text-ink-200",
  };
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04, duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      className="card card-hover relative overflow-hidden p-5"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-xs font-medium uppercase tracking-wide text-ink-500 dark:text-ink-400">{label}</p>
          <p className="mt-2 text-2xl font-semibold tracking-tight text-ink-950 dark:text-white">{value}</p>
          {hint && <div className="mt-1.5 text-xs text-ink-500 dark:text-ink-400">{hint}</div>}
        </div>
        {icon && (
          <div className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-xl", tones[tone])}>
            {icon}
          </div>
        )}
      </div>
    </motion.div>
  );
}

/* ------------------------------------------------------------------ Modal */
export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  size = "md",
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  size?: "sm" | "md" | "lg" | "xl";
}) {
  useEffect(() => {
    if (!open) return;
    const handler = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    document.addEventListener("keydown", handler);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handler);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  const sizes = { sm: "max-w-md", md: "max-w-lg", lg: "max-w-2xl", xl: "max-w-4xl" };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 flex items-end justify-center p-0 sm:items-center sm:p-6"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <div className="absolute inset-0 bg-ink-950/60 backdrop-blur-sm" onClick={onClose} />
          <motion.div
            role="dialog"
            aria-modal="true"
            initial={{ opacity: 0, y: 24, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={{ type: "spring", damping: 28, stiffness: 320 }}
            className={cn(
              "relative z-10 max-h-[92vh] w-full overflow-y-auto rounded-t-3xl bg-white shadow-pop dark:bg-ink-900 sm:rounded-3xl",
              sizes[size],
            )}
          >
            <div className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-ink-100 bg-white/95 px-6 py-4 backdrop-blur dark:border-white/10 dark:bg-ink-900/95">
              <div>
                <h2 className="text-base font-semibold text-ink-950 dark:text-white">{title}</h2>
                {description && <p className="mt-0.5 text-xs text-ink-500 dark:text-ink-400">{description}</p>}
              </div>
              <button
                onClick={onClose}
                className="rounded-lg p-1.5 text-ink-500 transition hover:bg-ink-100 hover:text-ink-800 dark:hover:bg-white/10 dark:hover:text-white"
                aria-label="Close dialog"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="px-6 py-5">{children}</div>
            {footer && (
              <div className="sticky bottom-0 flex justify-end gap-2 border-t border-ink-100 bg-ink-50/80 px-6 py-4 backdrop-blur dark:border-white/10 dark:bg-ink-950/60">
                {footer}
              </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function ConfirmDialog({
  open,
  onCancel,
  onConfirm,
  title,
  message,
  confirmLabel = "Confirm",
  danger = false,
  loading,
}: {
  open: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  title: string;
  message: string;
  confirmLabel?: string;
  danger?: boolean;
  loading?: boolean;
}) {
  return (
    <Modal
      open={open}
      onClose={onCancel}
      title={title}
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
          <Button variant={danger ? "danger" : "primary"} onClick={onConfirm} loading={loading}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      <div className="flex gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-rose-50 text-rose-600 dark:bg-rose-500/10 dark:text-rose-300">
          <AlertTriangle className="h-5 w-5" />
        </div>
        <p className="text-sm leading-relaxed text-ink-600 dark:text-ink-300">{message}</p>
      </div>
    </Modal>
  );
}

/* ----------------------------------------------------------------- Fields */
export function Field({
  label,
  hint,
  error,
  children,
  required,
}: {
  label: string;
  hint?: string;
  error?: string;
  children: React.ReactNode;
  required?: boolean;
}) {
  return (
    <label className="block">
      <span className="label">
        {label}
        {required && <span className="text-rose-500"> *</span>}
      </span>
      {children}
      {error ? (
        <span className="mt-1 block text-xs text-rose-600">{error}</span>
      ) : hint ? (
        <span className="mt-1 block text-xs text-ink-400 dark:text-ink-500">{hint}</span>
      ) : null}
    </label>
  );
}

export const Input = (props: React.InputHTMLAttributes<HTMLInputElement>) => <input {...props} className={cn("input", props.className)} />;

export const Textarea = (props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) => (
  <textarea {...props} className={cn("input min-h-[90px]", props.className)} />
);

export function Select({
  children,
  className,
  ...props
}: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select {...props} className={cn("input", className)}>
      {children}
    </select>
  );
}

/* ------------------------------------------------------------ PageHeader */
export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div>
        {eyebrow && <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-brand-600 dark:text-brand-300">{eyebrow}</p>}
        <h1 className="text-2xl font-semibold tracking-tight text-ink-950 dark:text-white">{title}</h1>
        {description && <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-ink-500 dark:text-ink-400">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

/* ------------------------------------------------------------- EmptyState */
export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
      {icon && (
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-ink-100 text-ink-500 dark:bg-white/5 dark:text-ink-400">
          {icon}
        </div>
      )}
      <p className="text-sm font-semibold text-ink-800 dark:text-ink-100">{title}</p>
      {description && <p className="mt-1 max-w-sm text-xs leading-relaxed text-ink-500 dark:text-ink-400">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

/* ---------------------------------------------------------------- Avatar */
export function Avatar({
  name,
  color = "#0dab99",
  size = "md",
}: {
  name?: string | null;
  color?: string;
  size?: "sm" | "md" | "lg";
}) {
  const dimensions = size === "sm" ? "h-7 w-7 text-[10px]" : size === "lg" ? "h-12 w-12 text-sm" : "h-9 w-9 text-xs";
  return (
    <span
      className={cn("inline-flex shrink-0 items-center justify-center rounded-full font-semibold text-white ring-2 ring-white dark:ring-ink-900", dimensions)}
      style={{ backgroundColor: color }}
    >
      {(name ?? "?")
        .split(/\s+/)
        .filter(Boolean)
        .slice(0, 2)
        .map((part) => part[0]?.toUpperCase())
        .join("")}
    </span>
  );
}

/* ------------------------------------------------------------ ProgressBar */
export function ProgressBar({
  value,
  tone = "teal",
  className,
}: {
  value: number;
  tone?: "teal" | "amber" | "rose" | "indigo";
  className?: string;
}) {
  const colours = {
    teal: "bg-brand-500",
    amber: "bg-amber-500",
    rose: "bg-rose-500",
    indigo: "bg-indigo-500",
  };
  return (
    <div className={cn("h-1.5 w-full overflow-hidden rounded-full bg-ink-100 dark:bg-white/10", className)}>
      <div
        className={cn("h-full rounded-full transition-all duration-700", colours[tone])}
        style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
      />
    </div>
  );
}

/* ------------------------------------------------------------------ Tabs */
export function Tabs({
  tabs,
  value,
  onChange,
}: {
  tabs: { id: string; label: string; count?: number }[];
  value: string;
  onChange: (id: string) => void;
}) {
  return (
    <div className="flex gap-1 overflow-x-auto rounded-xl bg-ink-100/70 p-1 dark:bg-white/5">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={cn(
            "flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition",
            value === tab.id
              ? "bg-white text-ink-900 shadow-sm dark:bg-white/10 dark:text-white"
              : "text-ink-500 hover:text-ink-800 dark:text-ink-400 dark:hover:text-ink-100",
          )}
        >
          {tab.label}
          {tab.count !== undefined && (
            <span className="rounded-full bg-ink-100 px-1.5 py-0.5 text-[10px] text-ink-500 dark:bg-white/10">{tab.count}</span>
          )}
        </button>
      ))}
    </div>
  );
}


/* ---------------------------------------------------------------- Switch */
export function Switch({
  checked,
  onChange,
  disabled,
  label,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  disabled?: boolean;
  label?: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition focus:outline-none focus:ring-4 focus:ring-brand-500/20 disabled:cursor-not-allowed disabled:opacity-50",
        checked ? "bg-brand-600" : "bg-ink-300 dark:bg-white/20",
      )}
    >
      <span
        className={cn(
          "inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition",
          checked ? "translate-x-[18px]" : "translate-x-[3px]",
        )}
      />
    </button>
  );
}

/* ---------------------------------------------------------------- Toasts */
interface Toast {
  id: number;
  message: string;
  type: "success" | "error" | "info";
}

let toastId = 0;
const listeners = new Set<(toasts: Toast[]) => void>();
let toasts: Toast[] = [];

function emit() {
  listeners.forEach((listener) => listener([...toasts]));
}

export function toast(message: string, type: Toast["type"] = "success") {
  toasts = [...toasts, { id: ++toastId, message, type }];
  emit();
  setTimeout(() => {
    toasts = toasts.filter((item) => item.id !== toastId);
    emit();
  }, 4200);
}

export function ToastHost() {
  const [items, setItems] = useState<Toast[]>([]);
  useEffect(() => {
    listeners.add(setItems);
    return () => {
      listeners.delete(setItems);
    };
  }, []);

  return (
    <div className="pointer-events-none fixed bottom-5 right-5 z-[60] flex w-80 flex-col gap-2">
      <AnimatePresence>
        {items.map((item) => (
          <motion.div
            key={item.id}
            initial={{ opacity: 0, y: 12, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8 }}
            className={cn(
              "pointer-events-auto rounded-xl border px-4 py-3 text-sm shadow-pop backdrop-blur",
              item.type === "error" &&
                "border-rose-200 bg-rose-50/95 text-rose-800 dark:border-rose-500/30 dark:bg-rose-950/80 dark:text-rose-200",
              item.type === "success" &&
                "border-emerald-200 bg-emerald-50/95 text-emerald-800 dark:border-emerald-500/30 dark:bg-emerald-950/80 dark:text-emerald-200",
              item.type === "info" &&
                "border-ink-200 bg-white/95 text-ink-800 dark:border-white/10 dark:bg-ink-900/95 dark:text-ink-100",
            )}
          >
            {item.message}
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}

/* ------------------------------------------------------------ DemoBanner */
export function DemoBanner({ message }: { message?: string }) {
  return (
    <div className="mb-5 flex items-start gap-2.5 rounded-xl border border-dashed border-amber-300/70 bg-amber-50/70 px-3.5 py-2.5 text-xs text-amber-800 dark:border-amber-400/30 dark:bg-amber-500/5 dark:text-amber-200/90">
      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
      <span>
        <strong className="font-semibold">Demo environment.</strong>{" "}
        {message ||
          "Telemetry on this page is simulated and labelled. It does not represent real vehicles or drivers."}
      </span>
    </div>
  );
}

/* ------------------------------------------------------------- Skeleton */
export function PageSkeleton({ cards = 4 }: { cards?: number }) {
  return (
    <div className="space-y-5">
      <div className="skeleton h-8 w-64" />
      <div className="skeleton h-4 w-96" />
      <div className="page-grid">
        {Array.from({ length: cards }).map((_, index) => (
          <div key={index} className="card p-5">
            <div className="skeleton mb-3 h-3 w-24" />
            <div className="skeleton h-7 w-32" />
          </div>
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="card p-5">
          <div className="skeleton h-56 w-full" />
        </div>
        <div className="card p-5">
          <div className="skeleton h-56 w-full" />
        </div>
      </div>
    </div>
  );
}
