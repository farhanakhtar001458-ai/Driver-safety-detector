"use client";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { cn } from "@/lib/format";
import { scoreColour } from "@/lib/scoreDisplay";

const AXIS = { stroke: "#cbd5e1", fontSize: 11 };
const GRID = "#e2e8f0";

function useChartTheme() {
  if (typeof window !== "undefined" && document.documentElement.classList.contains("dark")) {
    return { axis: "#64748b", grid: "rgba(148,163,184,0.12)", tooltipBg: "#0f172a", tooltipText: "#e2e8f0" };
  }
  return { axis: "#94a3b8", grid: GRID, tooltipBg: "#ffffff", tooltipText: "#0f172a" };
}

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: { value: number; name: string; color: string }[]; label?: string }) {
  const theme = useChartTheme();
  if (!active || !payload?.length) return null;
  return (
    <div
      className="rounded-xl border border-ink-200/70 px-3 py-2 text-xs shadow-lg dark:border-white/10"
      style={{ background: theme.tooltipBg, color: theme.tooltipText }}
    >
      {label && <p className="mb-1 font-semibold opacity-70">{label}</p>}
      {payload.map((item) => (
        <p key={item.name} className="flex items-center gap-2 py-0.5">
          <span className="h-2 w-2 rounded-full" style={{ background: item.color }} />
          <span className="capitalize opacity-70">{item.name.replace("_", " ")}</span>
          <span className="ml-auto font-semibold">{item.value}</span>
        </p>
      ))}
    </div>
  );
}

export function TrendAreaChart({
  data,
  height = 220,
}: {
  data: { label: string; events: number; high_risk: number; simulated?: number }[];
  height?: number;
}) {
  const theme = useChartTheme();
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 10, right: 8, left: -18, bottom: 0 }}>
        <defs>
          <linearGradient id="eventsFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#0dab99" stopOpacity={0.32} />
            <stop offset="100%" stopColor="#0dab99" stopOpacity={0.02} />
          </linearGradient>
          <linearGradient id="riskFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#f59e0b" stopOpacity={0.28} />
            <stop offset="100%" stopColor="#f59e0b" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke={theme.grid} vertical={false} />
        <XAxis dataKey="label" tick={AXIS} axisLine={{ stroke: theme.grid }} tickLine={false} />
        <YAxis tick={AXIS} axisLine={false} tickLine={false} width={40} />
        <Tooltip content={<ChartTooltip />} />
        <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11 }} />
        <Area type="monotone" dataKey="events" name="Events" stroke="#0dab99" strokeWidth={2} fill="url(#eventsFill)" />
        <Area type="monotone" dataKey="high_risk" name="High risk" stroke="#f59e0b" strokeWidth={2} fill="url(#riskFill)" />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function ActivityBarChart({
  data,
  height = 220,
  dataKey = "distance_km",
  color = "#6366f1",
}: {
  data: Record<string, string | number>[];
  height?: number;
  dataKey?: string;
  color?: string;
}) {
  const theme = useChartTheme();
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 10, right: 8, left: -18, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={theme.grid} vertical={false} />
        <XAxis dataKey="date" tick={AXIS} axisLine={false} tickLine={false} interval={1} />
        <YAxis tick={AXIS} axisLine={false} tickLine={false} width={40} />
        <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(99,102,241,0.06)" }} />
        <Bar dataKey={dataKey} name="Distance" fill={color} radius={[6, 6, 0, 0]} maxBarSize={26} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function EventTypeBarChart({
  data,
  height = 240,
}: {
  data: { type: string; count: number }[];
  height?: number;
}) {
  const theme = useChartTheme();
  const palette = ["#0dab99", "#6366f1", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#84cc16"];
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, left: 8, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={theme.grid} horizontal={false} />
        <XAxis type="number" tick={AXIS} axisLine={false} tickLine={false} />
        <YAxis
          type="category"
          dataKey="type"
          width={112}
          tick={{ ...AXIS, fill: theme.axis }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(value: string) => value.replace("_", " ").slice(0, 16)}
        />
        <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(13,171,153,0.06)" }} />
        <Bar dataKey="count" name="Events" radius={[0, 6, 6, 0]} maxBarSize={18}>
          {data.map((entry, index) => (
            <Cell key={entry.type} fill={palette[index % palette.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

const SEVERITY_COLORS: Record<string, string> = {
  low: "#10b981",
  medium: "#6366f1",
  high: "#f59e0b",
  critical: "#ef4444",
};

export function SeverityDonut({
  data,
  height = 220,
}: {
  data: { severity: string; count: number }[];
  height?: number;
}) {
  const total = data.reduce((sum, item) => sum + item.count, 0);
  return (
    <div className="flex items-center gap-4">
      <ResponsiveContainer width="60%" height={height}>
        <PieChart>
          <Pie
            data={data}
            dataKey="count"
            nameKey="severity"
            innerRadius="62%"
            outerRadius="88%"
            paddingAngle={2}
            strokeWidth={0}
          >
            {data.map((entry) => (
              <Cell key={entry.severity} fill={SEVERITY_COLORS[entry.severity] ?? "#94a3b8"} />
            ))}
          </Pie>
          <Tooltip content={<ChartTooltip />} />
        </PieChart>
      </ResponsiveContainer>
      <div className="flex-1 space-y-2">
        {data.map((entry) => (
          <div key={entry.severity} className="flex items-center gap-2 text-xs">
            <span className="h-2 w-2 rounded-full" style={{ background: SEVERITY_COLORS[entry.severity] ?? "#94a3b8" }} />
            <span className="capitalize text-ink-500 dark:text-ink-400">{entry.severity}</span>
            <span className="ml-auto font-semibold text-ink-800 dark:text-ink-100">
              {total ? Math.round((entry.count / total) * 100) : 0}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ScoreRing({
  score,
  size = 120,
  stroke = 10,
  label = "Safety score",
}: {
  score?: number | null;
  size?: number;
  stroke?: number;
  label?: string;
}) {
  const value = Math.max(0, Math.min(100, score ?? 0));
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (value / 100) * circumference;
  const band = scoreColour(score);
  const colour =
    band === "good" ? "#10b981" : band === "ok" ? "#0dab99" : band === "warn" ? "#f59e0b" : band === "bad" ? "#ef4444" : "#94a3b8";
  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="rgba(148,163,184,0.18)" strokeWidth={stroke} />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={colour}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            style={{ transition: "stroke-dashoffset 900ms cubic-bezier(.22,1,.36,1)" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-semibold tracking-tight" style={{ color: colour }}>
            {score === null || score === undefined ? "—" : score.toFixed(1)}
          </span>
          <span className="text-[10px] font-medium uppercase tracking-wide text-ink-400">/ 100</span>
        </div>
      </div>
      {label && <span className="text-xs font-medium text-ink-500 dark:text-ink-400">{label}</span>}
    </div>
  );
}

export function CategoryBars({
  categories,
}: {
  categories: { key: string; label: string; value: number | null | undefined }[];
}) {
  return (
    <div className="space-y-3">
      {categories.map((category) => (
        <div key={category.key}>
          <div className="mb-1 flex items-center justify-between text-xs">
            <span className="text-ink-600 dark:text-ink-300">{category.label}</span>
            <span className="font-semibold text-ink-900 dark:text-white">
              {category.value === null || category.value === undefined ? "No data" : category.value.toFixed(0)}
            </span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-ink-100 dark:bg-white/10">
            <div
              className={cn(
                "h-full rounded-full",
                (category.value ?? 0) >= 85
                  ? "bg-emerald-500"
                  : (category.value ?? 0) >= 70
                    ? "bg-brand-500"
                    : (category.value ?? 0) >= 55
                      ? "bg-amber-500"
                      : "bg-rose-500",
              )}
              style={{ width: `${Math.max(2, category.value ?? 0)}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

export function Sparkline({
  values,
  width = 96,
  height = 28,
  colour = "#0dab99",
}: {
  values: number[];
  width?: number;
  height?: number;
  colour?: string;
}) {
  if (!values.length) return <span className="text-xs text-ink-400">—</span>;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const points = values
    .map((value, index) => {
      const x = (index / Math.max(1, values.length - 1)) * (width - 4) + 2;
      const y = height - 2 - ((value - min) / range) * (height - 4);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg width={width} height={height} className="overflow-visible" aria-hidden="true">
      <polyline points={points} fill="none" stroke={colour} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
