import { clsx, type ClassValue } from "clsx";

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

export function formatNumber(value?: number | null, maximumFractionDigits = 0): string {
  if (value === undefined || value === null || Number.isNaN(Number(value))) return "—";
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits }).format(Number(value));
}

export function formatCompact(value?: number | null): string {
  if (value === undefined || value === null) return "—";
  return new Intl.NumberFormat("en-IN", { notation: "compact", maximumFractionDigits: 1 }).format(Number(value));
}

export function formatKm(value?: number | null): string {
  if (value === undefined || value === null) return "—";
  if (value >= 1000) return `${formatCompact(value)} km`;
  return `${formatNumber(value, 1)} km`;
}

export function formatScore(value?: number | null): string {
  if (value === undefined || value === null) return "—";
  return Number(value).toFixed(1);
}

export function formatDateTime(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDate(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

export function timeAgo(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value).getTime();
  if (Number.isNaN(date)) return "—";
  const seconds = Math.round((Date.now() - date) / 1000);
  if (seconds < 45) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days}d ago`;
  return formatDate(value);
}

export function initials(name?: string | null): string {
  if (!name) return "?";
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

export function titleCase(value?: string | null): string {
  if (!value) return "";
  return value
    .replace(/[_-]+/g, " ")
    .split(" ")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export function percent(value?: number | null, total?: number | null): number {
  if (!value || !total) return 0;
  return Math.round((value / total) * 100);
}

const TONE_CLASSES: Record<string, string> = {
  green: "bg-emerald-50 text-emerald-700 ring-emerald-600/20 dark:bg-emerald-500/10 dark:text-emerald-300",
  teal: "bg-brand-50 text-brand-700 ring-brand-600/20 dark:bg-brand-500/10 dark:text-brand-300",
  amber: "bg-amber-50 text-amber-700 ring-amber-600/20 dark:bg-amber-500/10 dark:text-amber-300",
  red: "bg-rose-50 text-rose-700 ring-rose-600/20 dark:bg-rose-500/10 dark:text-rose-300",
  slate: "bg-ink-100 text-ink-600 ring-ink-400/20 dark:bg-white/5 dark:text-ink-300",
  indigo: "bg-indigo-50 text-indigo-700 ring-indigo-600/20 dark:bg-indigo-500/10 dark:text-indigo-300",
};

export function severityTone(severity?: string | null): string {
  switch (severity) {
    case "critical":
      return TONE_CLASSES.red;
    case "high":
      return TONE_CLASSES.amber;
    case "medium":
    case "moderate":
      return TONE_CLASSES.indigo;
    case "low":
    case "minor":
      return TONE_CLASSES.green;
    default:
      return TONE_CLASSES.slate;
  }
}

export function riskTone(level?: string | null): string {
  switch (level) {
    case "critical":
      return TONE_CLASSES.red;
    case "high":
      return TONE_CLASSES.amber;
    case "moderate":
      return TONE_CLASSES.indigo;
    case "low":
      return TONE_CLASSES.green;
    default:
      return TONE_CLASSES.slate;
  }
}

export function statusTone(status?: string | null): string {
  switch (status) {
    case "active":
    case "resolved":
    case "verified":
    case "completed":
    case "online":
    case "succeeded":
      return TONE_CLASSES.green;
    case "under_maintenance":
    case "under_investigation":
    case "pending":
    case "scheduled":
      return TONE_CLASSES.amber;
    case "offline":
    case "inactive":
    case "overdue":
    case "new":
      return TONE_CLASSES.red;
    case "false_alert":
      return TONE_CLASSES.slate;
    default:
      return TONE_CLASSES.slate;
  }
}

export function scoreTone(score?: number | null): string {
  if (score === undefined || score === null) return TONE_CLASSES.slate;
  if (score >= 85) return TONE_CLASSES.green;
  if (score >= 70) return TONE_CLASSES.teal;
  if (score >= 55) return TONE_CLASSES.amber;
  return TONE_CLASSES.red;
}

export const ROLE_LABELS: Record<string, string> = {
  super_admin: "Super Admin",
  org_admin: "Organisation Admin",
  fleet_manager: "Fleet Manager",
  safety_officer: "Safety Officer",
  driver: "Driver",
};

export const EVENT_LABELS: Record<string, string> = {
  speeding: "Speeding",
  harsh_braking: "Harsh braking",
  rapid_acceleration: "Rapid acceleration",
  aggressive_cornering: "Aggressive cornering",
  excessive_duration: "Excessive duration",
  seatbelt_violation: "Seatbelt",
  possible_distraction: "Possible distraction",
  collision_suspected: "Possible collision",
  geofence_breach: "Geofence breach",
  route_deviation: "Route deviation",
  idle_excess: "Excessive idling",
};

export const VEHICLE_STATUS_LABELS: Record<string, string> = {
  active: "Active",
  inactive: "Inactive",
  under_maintenance: "Under maintenance",
  offline: "Offline",
};

export function downloadUrl(reportId: number): string {
  return `/api/v1/reports/${reportId}/download`;
}
